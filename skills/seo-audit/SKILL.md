---
name: seo-audit
description: "SEO audit sub-skill — scans HTML/PHP files and generates a JSON+Markdown report. Calculates per-file and site-level SEO scores (0-100) with grade bands A–F. Groups issues by severity (critical/high/medium/low). Venice AI powered for generative analysis. Use when user says seo audit, generate seo report, check seo score, analyze my seo, website health check, or seo analysis."
user-invokable: true
tested_date: 2026-07-27
tested_with: claude-code v2.x
---

# SEO Audit

Generate a comprehensive SEO audit report for HTML/PHP website files.

## Process

1. **Collect context**: Ask for the path to scan (default: current directory) and the site URL
2. **Scan files**: Run `seo_scanner.py <path> --json` to collect all check results
3. **Generate report**: Run `seo_report.py results.json --site-url <url> --output-dir .`
4. **Present findings**:
   - Display overall site score and grade
   - List top issues by severity
   - Highlight quick wins (high-impact, easy fixes)
   - Show per-file scores in a table
   - Recommend running `/seo fix --dry-run` to preview auto-fixes

## Output

- `seo-report.json` — machine-readable full report
- `seo-report.md` — client-deliverable Markdown report

## Script Commands

```bash
# Scan and save JSON results
python ~/.claude/skills/ads/scripts/seo_scanner.py ./public_html --json > /tmp/seo-results.json

# Generate report from results
python ~/.claude/skills/ads/scripts/seo_report.py /tmp/seo-results.json \
  --site-url https://example.com \
  --output-dir ./seo-report/
```

## Grade Bands

| Grade | Score   | Interpretation |
|-------|---------|----------------|
| A     | 90–100  | Excellent |
| B     | 80–89   | Good |
| C     | 70–79   | Fair |
| D     | 60–69   | Poor |
| F     | 0–59    | Critical |
