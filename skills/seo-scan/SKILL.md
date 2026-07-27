---
name: seo-scan
description: "SEO scan sub-skill — read-only scan of HTML/PHP files for 16 SEO check categories. No files are modified. Outputs per-file check results to stdout. Use when user says seo scan, scan my website, check seo issues, seo check, find seo problems, seo review, or list seo issues."
user-invokable: true
tested_date: 2026-07-27
tested_with: claude-code v2.x
---

# SEO Scan

Read-only scan of HTML/PHP files — no modifications made.

## Process

1. **Get path**: current directory or user-specified path
2. **Run scanner** on all `.html` and `.php` files found recursively
3. **Display results** per file: check ID, status icon, message, fix hint

## Output Format

```
============================================================
  ./index.html  |  Score: 72/100  (C)
============================================================
  ✓ [C01] Title length OK (55 chars)
  ✗ [C02] Missing meta description
      → Add a <meta name='description'> between 150–160 characters.
  ✓ [C03a] Viewport meta tag present
  ✓ [C03b] Charset declared
  ✗ [C04a] No <h1> tag found
      → Add a single <h1> containing the primary keyword.
  ⚠ [C05] 3 image(s) missing alt text
      → Add descriptive alt attributes to all <img> tags.
  ...
```

## Script Commands

```bash
# Scan directory (human-readable)
python ~/.claude/skills/ads/scripts/seo_scanner.py ./public_html

# Scan directory (JSON output)
python ~/.claude/skills/ads/scripts/seo_scanner.py ./public_html --json

# Scan single file
python ~/.claude/skills/ads/scripts/seo_scanner.py ./index.html
```

## Status Icons

| Icon | Meaning |
|------|---------|
| ✓    | Pass    |
| ✗    | Fail    |
| ⚠    | Warning |
| ℹ    | Info    |

## Next Steps After Scan

- `/seo audit` — generate a full JSON+Markdown report with scoring
- `/seo fix --dry-run` — preview all auto-fixes as diffs
- `/seo fix` — apply fixes with .bak backups
