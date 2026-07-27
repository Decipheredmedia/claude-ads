---
name: seo-fix
description: "SEO auto-fixer sub-skill — applies idempotent, safe fixes to HTML/PHP files: charset, viewport, canonical, Open Graph, Twitter Card, lazy loading, robots.txt, sitemap.xml. With VENICE_API_KEY: also generates titles, meta descriptions, alt text, and JSON-LD schema. Creates .bak backups. Validates PHP syntax after fix. Use when user says seo fix, fix my seo, auto fix seo, apply seo fixes, fix website seo, or fix html seo."
user-invokable: true
tested_date: 2026-07-27
tested_with: claude-code v2.x
---

# SEO Fix

Apply safe, idempotent SEO fixes to HTML and PHP files.

## Process

1. **Collect context**: path (default: current directory), site URL, dry-run preference
2. **Check for Venice AI key**: warn if missing (AI fixes will be skipped)
3. **Run fixer**:
   - `--dry-run`: show diffs only, no files written
   - Normal mode: write in place with `.bak` backup
4. **PHP safety**: run `php -l` after each PHP fix; restore `.bak` on syntax error
5. **Present summary**: files fixed, fixes applied per file, errors

## Automatic Fixes (no AI required)

- `<meta charset="UTF-8">` — added if missing
- `<meta name="viewport" ...>` — added if missing
- `<link rel="canonical" href="...">` — added if missing
- Open Graph tags (`og:title`, `og:description`, `og:url`, `og:type`) — added if missing
- `<meta name="twitter:card">` — added if missing
- `loading="lazy"` — added to images after the 2nd one
- `robots.txt` — generated at project root if missing
- `sitemap.xml` — generated at project root if missing

## AI-Assisted Fixes (require VENICE_API_KEY)

- `<title>` — generated/rewritten if missing or out of range
- `<meta name="description">` — generated/rewritten if missing or out of range
- `alt` attributes — generated for images with missing alt text
- JSON-LD schema — generated and injected if absent

## Script Commands

```bash
# Dry-run preview
python ~/.claude/skills/ads/scripts/seo_fixer.py ./public_html --dry-run

# Apply all safe fixes
python ~/.claude/skills/ads/scripts/seo_fixer.py ./public_html --site-url https://example.com

# Fix a single file
python ~/.claude/skills/ads/scripts/seo_fixer.py ./index.html --site-url https://example.com
```

## Safety Rules

- `.bak` files are created before every in-place write (disable with `--no-backup`)
- PHP business logic is **never** touched
- All fixes are idempotent — running twice produces the same result
- `php -l` validates PHP files post-fix; failures trigger automatic restore
