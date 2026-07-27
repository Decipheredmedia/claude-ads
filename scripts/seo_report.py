"""SEO report generator — JSON + Markdown output.

Takes the raw output from ``seo_scanner.scan_directory()`` and produces:
  - A structured JSON report suitable for programmatic consumption
  - A Markdown report suitable for client delivery

Scoring
-------
Per-file scores (0–100) are averaged to produce a site-level score.
Grade bands mirror the ads-audit style:
  A  90–100   Excellent — minimal issues
  B  80–89    Good — a few improvements needed
  C  70–79    Fair — notable gaps, schedule fixes
  D  60–69    Poor — significant SEO problems
  F  0–59     Critical — immediate attention required

Usage
-----
>>> from seo_report import generate_report, write_report
>>> results = scan_directory("./public_html")
>>> report = generate_report(results, site_url="https://example.com")
>>> write_report(report, output_dir="./seo-report")

CLI
---
$ python seo_report.py ./seo-results.json --output-dir ./report
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Severity ordering (for prioritized fix list) ─────────────────────────────
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ─── Main report builder ──────────────────────────────────────────────────────


def generate_report(
    scan_results: list[dict],
    site_url: str = "",
    scan_root: str = "",
) -> dict:
    """Build a structured report from scan results.

    Args:
        scan_results: List of dicts returned by ``scan_directory()``.
        site_url:     Optional site URL for the report header.
        scan_root:    Optional path of the scanned directory.

    Returns:
        A report dict with keys: meta, summary, files, top_issues, recommendations.
    """
    if not scan_results:
        return _empty_report(site_url, scan_root)

    total_files = len(scan_results)
    error_files = [r for r in scan_results if r.get("error")]
    valid_results = [r for r in scan_results if not r.get("error")]

    scores = [r["score"] for r in valid_results] if valid_results else [0]
    site_score = round(sum(scores) / len(scores)) if scores else 0
    site_grade = _score_to_grade(site_score)

    # Collect all failed/warning checks across all files
    all_issues: list[dict] = []
    for result in scan_results:
        for check in result.get("checks", []):
            if check["status"] in ("fail", "warning"):
                all_issues.append({
                    **check,
                    "file": result["path"],
                })

    # Group issues by severity
    issues_by_severity: dict[str, list[dict]] = {
        "critical": [], "high": [], "medium": [], "low": []
    }
    for issue in all_issues:
        sev = issue.get("severity", "medium")
        issues_by_severity.setdefault(sev, []).append(issue)

    # Top issues (sorted by severity, then by frequency)
    top_issues = sorted(all_issues, key=lambda x: _SEVERITY_ORDER.get(x.get("severity", "medium"), 2))

    # Per-check aggregation: how many files are affected by each check ID?
    check_counts: dict[str, dict] = {}
    for issue in all_issues:
        cid = issue["id"]
        if cid not in check_counts:
            check_counts[cid] = {
                "id": cid,
                "category": issue["category"],
                "message": issue["message"],
                "severity": issue.get("severity", "medium"),
                "affected_files": 0,
                "fix_hint": issue.get("fix_hint"),
            }
        check_counts[cid]["affected_files"] += 1

    most_common = sorted(
        check_counts.values(),
        key=lambda x: (
            _SEVERITY_ORDER.get(x["severity"], 2),
            -x["affected_files"],
        ),
    )

    # Per-file summary (path, score, grade, issue counts)
    file_summaries = [
        {
            "path": r["path"],
            "score": r["score"],
            "grade": r["grade"],
            "critical": sum(1 for c in r.get("checks", []) if c.get("severity") == "critical" and c["status"] == "fail"),
            "high": sum(1 for c in r.get("checks", []) if c.get("severity") == "high" and c["status"] in ("fail", "warning")),
            "medium": sum(1 for c in r.get("checks", []) if c.get("severity") == "medium" and c["status"] in ("fail", "warning")),
            "low": sum(1 for c in r.get("checks", []) if c.get("severity") == "low" and c["status"] in ("fail", "warning")),
            "title": r.get("title", ""),
            "is_php": r.get("is_php", False),
            "error": r.get("error"),
        }
        for r in scan_results
    ]
    file_summaries.sort(key=lambda x: x["score"])

    # Quick wins: critical/high issues that appear across many files
    quick_wins = [
        c for c in most_common[:10]
        if c["severity"] in ("critical", "high")
    ]

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "site_url": site_url,
            "scan_root": scan_root,
            "tool": "claude-ads/seo-skill",
        },
        "summary": {
            "site_score": site_score,
            "site_grade": site_grade,
            "total_files": total_files,
            "error_files": len(error_files),
            "score_distribution": _score_distribution(scores),
            "issues": {
                "critical": len(issues_by_severity["critical"]),
                "high": len(issues_by_severity["high"]),
                "medium": len(issues_by_severity["medium"]),
                "low": len(issues_by_severity["low"]),
            },
        },
        "files": file_summaries,
        "top_issues": top_issues[:50],
        "most_common_issues": most_common[:20],
        "quick_wins": quick_wins,
    }


# ─── Markdown renderer ────────────────────────────────────────────────────────


def to_markdown(report: dict) -> str:
    """Convert a report dict to a Markdown string for client delivery."""
    lines: list[str] = []
    meta = report.get("meta", {})
    summary = report.get("summary", {})
    site_score = summary.get("site_score", 0)
    site_grade = summary.get("site_grade", "F")
    generated_at = meta.get("generated_at", "")
    site_url = meta.get("site_url", "")

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append("# SEO Audit Report")
    lines.append("")
    if site_url:
        lines.append(f"**Site:** {site_url}  ")
    lines.append(f"**Generated:** {generated_at[:19].replace('T', ' ')} UTC  ")
    lines.append(f"**Tool:** claude-ads SEO skill (Venice AI powered)")
    lines.append("")

    # ── Score card ──────────────────────────────────────────────────────────
    grade_bar = _grade_bar(site_score)
    lines.append("## Overall SEO Score")
    lines.append("")
    lines.append(f"```")
    lines.append(f"  Score:  {site_score}/100   Grade: {site_grade}")
    lines.append(f"  {grade_bar}")
    lines.append(f"")
    lines.append(f"  Files scanned:  {summary.get('total_files', 0)}")
    lines.append(f"  Parse errors:   {summary.get('error_files', 0)}")
    lines.append(f"```")
    lines.append("")

    # ── Issue summary ────────────────────────────────────────────────────────
    issues = summary.get("issues", {})
    lines.append("## Issue Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for sev in ("critical", "high", "medium", "low"):
        count = issues.get(sev, 0)
        lines.append(f"| {sev.capitalize()} | {count} |")
    lines.append("")

    # ── Most common issues ───────────────────────────────────────────────────
    most_common = report.get("most_common_issues", [])
    if most_common:
        lines.append("## Most Common Issues (by affected file count)")
        lines.append("")
        lines.append("| # | Check | Severity | Affected Files | Recommended Fix |")
        lines.append("|---|-------|----------|---------------|-----------------|")
        for i, issue in enumerate(most_common[:15], 1):
            fix = (issue.get("fix_hint") or "")[:80].replace("|", "\\|")
            lines.append(
                f"| {i} | [{issue['id']}] {issue['message'][:60]} "
                f"| {issue['severity'].capitalize()} "
                f"| {issue['affected_files']} "
                f"| {fix} |"
            )
        lines.append("")

    # ── Quick wins ───────────────────────────────────────────────────────────
    quick_wins = report.get("quick_wins", [])
    if quick_wins:
        lines.append("## Quick Wins")
        lines.append("")
        lines.append("High-impact fixes that improve many pages at once:")
        lines.append("")
        for qw in quick_wins[:8]:
            lines.append(
                f"- **[{qw['severity'].upper()}]** {qw['message']} "
                f"({qw['affected_files']} files)"
            )
            if qw.get("fix_hint"):
                lines.append(f"  > {qw['fix_hint']}")
        lines.append("")

    # ── Per-file scores ──────────────────────────────────────────────────────
    file_summaries = report.get("files", [])
    if file_summaries:
        lines.append("## File Scores")
        lines.append("")
        lines.append("| File | Score | Grade | Critical | High | Medium |")
        lines.append("|------|-------|-------|----------|------|--------|")
        for f in file_summaries:
            path_short = f["path"]
            if len(path_short) > 50:
                path_short = "…" + path_short[-47:]
            error_note = " ⚠ parse error" if f.get("error") else ""
            lines.append(
                f"| `{path_short}` | {f['score']} | {f['grade']}"
                f" | {f.get('critical', 0)} | {f.get('high', 0)} | {f.get('medium', 0)}"
                f"{error_note} |"
            )
        lines.append("")

    # ── Footer ───────────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("*Generated by [claude-ads](https://github.com/Decipheredmedia/claude-ads) SEO skill "
                 "powered by Venice AI.*")
    lines.append("")
    lines.append("**Next steps:** Run `/seo fix` to auto-apply safe fixes, or `/seo fix --dry-run` to preview changes first.")
    lines.append("")

    return "\n".join(lines)


# ─── File writers ─────────────────────────────────────────────────────────────


def write_report(
    report: dict,
    output_dir: str | Path = ".",
    prefix: str = "seo-report",
) -> dict[str, Path]:
    """Write JSON and Markdown reports to ``output_dir``.

    Args:
        report:     Report dict from ``generate_report()``.
        output_dir: Directory to write files into.
        prefix:     Filename prefix (e.g. "seo-report").

    Returns:
        Dict with keys "json" and "markdown" pointing to written Paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / f"{prefix}.json"
    md_path = out / f"{prefix}.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")

    return {"json": json_path, "markdown": md_path}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _score_to_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _grade_bar(score: int, width: int = 40) -> str:
    filled = round(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score}%"


def _score_distribution(scores: list[int]) -> dict[str, int]:
    dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for s in scores:
        dist[_score_to_grade(s)] += 1
    return dist


def _empty_report(site_url: str, scan_root: str) -> dict:
    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "site_url": site_url,
            "scan_root": scan_root,
            "tool": "claude-ads/seo-skill",
        },
        "summary": {
            "site_score": 0,
            "site_grade": "F",
            "total_files": 0,
            "error_files": 0,
            "score_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
            "issues": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        },
        "files": [],
        "top_issues": [],
        "most_common_issues": [],
        "quick_wins": [],
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate SEO report from scan results JSON")
    parser.add_argument("results_json", help="Path to scan results JSON file")
    parser.add_argument("--output-dir", default=".", help="Output directory")
    parser.add_argument("--site-url", default="", help="Site URL for report header")
    args = parser.parse_args()

    data = json.loads(Path(args.results_json).read_text(encoding="utf-8"))
    report = generate_report(data, site_url=args.site_url)
    paths = write_report(report, output_dir=args.output_dir)
    print(f"✓ JSON:     {paths['json']}")
    print(f"✓ Markdown: {paths['markdown']}")
    print(f"  Score:    {report['summary']['site_score']}/100 ({report['summary']['site_grade']})")


if __name__ == "__main__":
    _cli()
