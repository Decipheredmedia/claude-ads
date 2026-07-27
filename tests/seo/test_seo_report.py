"""Tests for SEO report generator (seo_report.py).

Covers:
- generate_report() with empty and populated scan results
- Scoring and grade calculation
- Markdown rendering (structural checks)
- write_report() file output
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from seo_report import (  # noqa: E402
    generate_report,
    to_markdown,
    write_report,
    _score_to_grade,
    _score_distribution,
)


# ─── Helper ───────────────────────────────────────────────────────────────────


def _make_result(
    path: str = "./index.html",
    score: int = 75,
    grade: str = "C",
    checks: list | None = None,
    title: str = "Test Page",
    meta_description: str = "",
    is_php: bool = False,
) -> dict:
    return {
        "path": path,
        "is_php": is_php,
        "score": score,
        "grade": grade,
        "checks": checks or [],
        "php_blocks": [],
        "raw_html": "",
        "title": title,
        "meta_description": meta_description,
    }


# ─── generate_report ──────────────────────────────────────────────────────────


def test_generate_report_empty():
    report = generate_report([])
    assert report["summary"]["total_files"] == 0
    assert report["summary"]["site_score"] == 0
    assert report["files"] == []


def test_generate_report_single_file():
    results = [_make_result(score=80, grade="B")]
    report = generate_report(results, site_url="https://example.com")
    assert report["summary"]["site_score"] == 80
    assert report["summary"]["site_grade"] == "B"
    assert report["summary"]["total_files"] == 1
    assert report["meta"]["site_url"] == "https://example.com"


def test_generate_report_averages_scores():
    results = [
        _make_result(score=60, grade="D"),
        _make_result(score=80, grade="B"),
        _make_result(score=100, grade="A"),
    ]
    report = generate_report(results)
    assert report["summary"]["site_score"] == 80  # (60+80+100)//3


def test_generate_report_collects_issues():
    fail_check = {
        "id": "C01",
        "category": "title",
        "status": "fail",
        "message": "Missing title",
        "severity": "critical",
    }
    results = [_make_result(checks=[fail_check])]
    report = generate_report(results)
    assert report["summary"]["issues"]["critical"] == 1


def test_generate_report_with_error_files():
    ok = _make_result(score=90, grade="A")
    err = {**_make_result(score=0, grade="F"), "error": "Could not parse"}
    report = generate_report([ok, err])
    assert report["summary"]["error_files"] == 1
    assert report["summary"]["total_files"] == 2


def test_generate_report_quick_wins_are_high_severity():
    high_fail = {
        "id": "C06",
        "category": "canonical",
        "status": "fail",
        "message": "Missing canonical",
        "severity": "high",
        "fix_hint": "Add canonical tag",
    }
    results = [_make_result(checks=[high_fail])]
    report = generate_report(results)
    assert any(qw["severity"] in ("critical", "high") for qw in report["quick_wins"])


def test_generate_report_most_common_issues_sorted_by_severity():
    checks = [
        {"id": "C01", "category": "title", "status": "fail", "message": "Missing title", "severity": "critical"},
        {"id": "C12", "category": "lazy", "status": "warning", "message": "No lazy", "severity": "low"},
    ]
    results = [_make_result(checks=checks)]
    report = generate_report(results)
    most_common = report["most_common_issues"]
    # Critical should come before low
    severities = [i["severity"] for i in most_common]
    assert severities.index("critical") < severities.index("low")


# ─── _score_to_grade ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("score,grade", [
    (100, "A"), (90, "A"),
    (89, "B"),  (80, "B"),
    (79, "C"),  (70, "C"),
    (69, "D"),  (60, "D"),
    (59, "F"),  (0, "F"),
])
def test_score_to_grade(score, grade):
    assert _score_to_grade(score) == grade


# ─── _score_distribution ─────────────────────────────────────────────────────


def test_score_distribution():
    scores = [95, 85, 75, 65, 55]
    dist = _score_distribution(scores)
    assert dist["A"] == 1
    assert dist["B"] == 1
    assert dist["C"] == 1
    assert dist["D"] == 1
    assert dist["F"] == 1


# ─── to_markdown ──────────────────────────────────────────────────────────────


def test_to_markdown_contains_score():
    results = [_make_result(score=82, grade="B")]
    report = generate_report(results, site_url="https://mysite.com")
    md = to_markdown(report)
    assert "82" in md
    assert "B" in md


def test_to_markdown_contains_site_url():
    results = [_make_result()]
    report = generate_report(results, site_url="https://example.com")
    md = to_markdown(report)
    assert "https://example.com" in md


def test_to_markdown_is_string():
    report = generate_report([])
    md = to_markdown(report)
    assert isinstance(md, str)
    assert len(md) > 100


def test_to_markdown_contains_file_scores_section():
    results = [_make_result(path="./index.html", score=90, grade="A")]
    report = generate_report(results)
    md = to_markdown(report)
    assert "index.html" in md


# ─── write_report ─────────────────────────────────────────────────────────────


def test_write_report_creates_json_and_md(tmp_path):
    results = [_make_result()]
    report = generate_report(results)
    paths = write_report(report, output_dir=tmp_path)
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    # JSON should be valid
    data = json.loads(paths["json"].read_text())
    assert "summary" in data
    # Markdown should start with a heading
    md = paths["markdown"].read_text()
    assert md.startswith("# SEO Audit Report")


def test_write_report_custom_prefix(tmp_path):
    report = generate_report([])
    paths = write_report(report, output_dir=tmp_path, prefix="my-audit")
    assert paths["json"].name == "my-audit.json"
    assert paths["markdown"].name == "my-audit.md"


def test_write_report_creates_output_dir(tmp_path):
    new_dir = tmp_path / "nested" / "output"
    report = generate_report([])
    write_report(report, output_dir=new_dir)
    assert new_dir.is_dir()
