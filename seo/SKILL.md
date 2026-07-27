---
name: seo
description: "On-page and technical SEO analysis and auto-fixing for HTML and PHP websites. Powered by Venice AI (OpenAI-compatible). Recursively scans .html/.php files for 16+ check categories, generates JSON+Markdown reports with 0-100 scoring, and auto-fixes issues in-place with .bak backups. Use when user says seo audit, seo fix, seo scan, check my website SEO, fix SEO, optimize my HTML, improve my page ranking, analyze my website, or on-page SEO."
argument-hint: "audit [<path>] | fix [<path>] [--dry-run] | scan <path> | report [--json]"
license: MIT
tested_date: 2026-07-27
tested_with: claude-code v2.x
---

# SEO: On-Page & Technical SEO Optimization

Comprehensive SEO analysis and auto-fixing for `.html` and `.php` website
files. Uses **Venice AI** (OpenAI-compatible) for generative tasks:
title writing, meta description generation, alt-text generation, and
JSON-LD schema injection. All structural checks run locally with zero AI calls.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/seo scan <path>` | Scan files for SEO issues (read-only, no changes) |
| `/seo audit [<path>]` | Scan + generate JSON + Markdown report with scoring |
| `/seo fix [<path>]` | Auto-fix safe issues in place (creates .bak backups) |
| `/seo fix --dry-run` | Preview fixes as a diff without writing |
| `/seo fix --no-backup` | Fix without creating .bak files |

## Context Intake (Always Do This First)

Before scanning, ask:
1. **Path**: directory or single file to scan (`./`, `./public_html`, `./index.html`)
2. **Site URL**: base URL of the website (used for canonical tags and OG tags)
3. **Venice AI key**: is `VENICE_API_KEY` set? AI-assisted fixes need it. Pure structural checks work without it.

If the user runs `/seo audit` without arguments, scan the current working directory.

## Check Categories

The skill runs 16 check categories per file:

| ID   | Category           | Severity | AI Required? |
|------|--------------------|----------|--------------|
| C01  | Title tag          | Critical | For generation |
| C02  | Meta description   | High     | For generation |
| C03  | Viewport + charset | High     | No |
| C04  | Heading structure  | High     | No |
| C05  | Image alt text     | High     | For generation |
| C06  | Canonical tag      | High     | No |
| C07  | Open Graph tags    | Medium   | No |
| C08  | Twitter Card       | Low      | No |
| C09  | JSON-LD schema     | High     | For generation |
| C10  | Robots meta        | Medium   | No |
| C11  | Image dimensions   | Medium   | No |
| C12  | Lazy loading       | Low      | No |
| C13  | Semantic HTML      | Medium   | No |
| C14  | Render-blocking    | Low      | No |
| C15  | Duplicate content  | High     | No |
| C16  | hreflang           | Info     | No |

## Scoring

Each file is scored 0–100 with grade bands:

```
A  90–100  Excellent — minimal issues
B  80–89   Good — a few improvements needed
C  70–79   Fair — notable gaps, schedule fixes
D  60–69   Poor — significant SEO problems
F  0–59    Critical — immediate attention required
```

Site-level score = average of all per-file scores.

## PHP File Safety Rules

- PHP blocks (`<?php ... ?>`, `<?= ... ?>`) are preserved **byte-for-byte**
- Only `<head>`, meta, schema, alt-text, and landmark sections are modified
- After fixing, `php -l` is run if PHP CLI is available; if it fails, the `.bak` is restored automatically
- PHP logic / business code is **never** touched

## Output Files

- `seo-report.json` — structured report (machine-readable)
- `seo-report.md` — Markdown report (client-deliverable)
- `robots.txt` — generated at project root if missing
- `sitemap.xml` — generated at project root if missing
- `*.bak` — original file backup before in-place fix

## Venice AI Configuration

The skill uses Venice AI for generative fixes. Configuration priority:
1. `VENICE_API_KEY` environment variable
2. `~/.claude/skills/seo/config.json`:
   ```json
   {
     "api_key": "vn-your-key-here",
     "model": "llama-3.3-70b",
     "temperature": 0.3,
     "max_tokens": 512
   }
   ```

Structural checks (C03–C16 except C05/C09) work without an API key.

## Execution Flow

### `/seo scan <path>`
1. Validate path (no `..`, no shell metacharacters, must exist)
2. Detect PHP vs HTML files
3. For PHP: extract `<?php?>` blocks as placeholders
4. Parse DOM with BeautifulSoup4 (falls back to stdlib html.parser)
5. Run all 16 check categories
6. Print check results per file to stdout

### `/seo audit [<path>]`
1. Run scan (as above)
2. Aggregate scores across all files
3. Generate `seo-report.json` and `seo-report.md`
4. Print summary: site score, grade, top issues, quick wins

### `/seo fix [<path>] [--dry-run]`
1. Run scan to identify failing checks
2. Apply safe automatic fixes (viewport, charset, canonical, OG tags, lazy loading, robots.txt, sitemap.xml)
3. If `VENICE_API_KEY` is set: run AI-assisted fixes (title, description, alt-text, JSON-LD)
4. For PHP files: validate with `php -l` after fix; restore `.bak` on failure
5. Write files in place (or print diff for `--dry-run`)

## Script Commands

The skill delegates to Python scripts in `<SKILL_BASE>/ads/scripts/`:

```
seo_scanner.py  <path> [--json]          # scan and output checks
seo_report.py   <results.json>           # generate report from scan JSON
seo_fixer.py    <path> [--dry-run]       # apply fixes
venice_provider.py --prompt "..."        # smoke-test Venice AI connection
```

## Error Handling

- Missing `VENICE_API_KEY`: structural checks run; AI fixes are skipped with a warning
- PHP syntax error after fix: file is restored from `.bak` automatically
- Parse error on a file: file is reported with `grade: F` and `error` field; other files continue
- Venice API rate limit: automatic exponential backoff (1→2→4→8s, max 4 retries)
- Venice API unavailable: AI fixes skipped; structural fixes still applied

## References

See `references/seo-checks.md` for detailed check descriptions, scoring weights,
and implementation notes.
