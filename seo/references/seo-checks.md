# SEO Check Reference

Complete reference for all 16 SEO check categories with scoring weights,
pass/fail criteria, and fix guidance.

## Scoring Model

Each file starts at 100 points.  Checks deduct points on fail or warning:

| Severity | Fail deduction | Warning deduction |
|----------|---------------|-------------------|
| Critical | 15 pts        | 8 pts             |
| High     | 10 pts        | 5 pts             |
| Medium   | 5 pts         | 3 pts             |
| Low      | 3 pts         | 1 pt              |

Site score = arithmetic mean of all per-file scores, rounded to nearest integer.

## Check Catalog

### C01 — Title Tag
- **Weight:** 15 pts
- **Pass:** Title present, 50–60 characters
- **Warning:** Title > 60 characters (truncated in SERPs)
- **Fail/Critical:** Title missing
- **Fail/High:** Title < 10 characters
- **Fix:** Venice AI generates a keyword-rich title if missing or wrong length

### C02 — Meta Description
- **Weight:** 15 pts
- **Pass:** Description present, 150–160 characters
- **Warning:** Description > 160 characters
- **Fail/High:** Missing or < 50 characters
- **Fix:** Venice AI generates a compelling description

### C03 — Viewport + Charset
- **Weight:** 5 pts (shared)
- **C03a Viewport:** `<meta name="viewport" content="width=device-width, initial-scale=1">`
- **C03b Charset:** `<meta charset="UTF-8">` or `<meta http-equiv="Content-Type">`
- **Fix:** Injected automatically into `<head>`

### C04 — Heading Structure
- **Weight:** 10 pts
- **C04a H1 count:** Exactly one `<h1>` per page required
- **C04b Hierarchy:** No skipped heading levels (e.g., H1→H3 without H2)
- **Fix:** Manual — structural changes require editorial judgement

### C05 — Image Alt Attributes
- **Weight:** 10 pts
- **Pass:** All `<img>` tags have non-empty `alt` attribute
- **Fail/High:** One or more images missing `alt`
- **Fix:** Venice AI generates alt text from image filename/context

### C06 — Canonical Link Tag
- **Weight:** 5 pts
- **Pass:** `<link rel="canonical" href="...">` present with non-empty href
- **Warning:** Tag present but href is empty
- **Fail/High:** No canonical tag
- **Fix:** Injected automatically with `site_url` from config

### C07 — Open Graph Tags
- **Weight:** 5 pts
- **Required:** `og:title`, `og:description`, `og:image`, `og:url`
- **Fail/Medium:** One or more required OG tags missing
- **Fix:** `og:title`, `og:description`, `og:url`, `og:type` injected automatically
  Note: `og:image` requires a real image URL — set manually

### C08 — Twitter Card
- **Weight:** 3 pts
- **Required:** `twitter:card`
- **Warning/Low:** Missing
- **Fix:** `<meta name="twitter:card" content="summary_large_image">` injected

### C09 — JSON-LD Structured Data
- **Weight:** 8 pts
- **Pass:** Valid `<script type="application/ld+json">` present
- **Warning/Medium:** Malformed JSON in existing schema
- **Fail/High:** No structured data
- **Fix:** Venice AI generates appropriate schema (Article, WebPage, LocalBusiness,
  Product, FAQPage) based on page title/description

### C10 — Robots Meta
- **Weight:** 3 pts
- **Pass:** No robots tag (defaults to index,follow — correct for public pages)
- **Warning/High:** `noindex` or `nofollow` found (flags for review; may be intentional)
- **Fix:** Manual — intentional noindex must not be changed automatically

### C11 — Image Dimensions (CLS Prevention)
- **Weight:** 5 pts
- **Pass:** All `<img>` tags have explicit `width` and `height` attributes
- **Warning/Medium:** Missing dimensions on one or more images
- **Fix:** Must be set manually (requires knowledge of actual image dimensions)

### C12 — Lazy Loading
- **Weight:** 3 pts
- **Pass:** Images after the 2nd have `loading="lazy"`
- **Warning/Low:** Images missing lazy loading attribute
- **Fix:** `loading="lazy"` added to all images after the first two

### C13 — Semantic HTML Landmarks
- **Weight:** 5 pts
- **Checks:** Presence of `<nav>`, `<main>`, `<footer>` elements
- **Warning:** Missing landmark elements
- **Severity:** `<main>` is high; `<nav>` is medium; `<footer>` is low
- **Fix:** Manual — requires wrapping content in proper landmark elements

### C14 — Render-Blocking Resources
- **Weight:** 3 pts
- **Checks:** `<script>` tags in `<head>` without `async`/`defer`; inline `<style>` blocks
- **Warning/Low:** Potential render-blocking elements found
- **Fix:** Add `async` or `defer` to `<script>` tags; move non-critical CSS

### C15 — Duplicate Content Detection
- **Weight:** 5 pts (shared)
- **C15a:** Duplicate `<title>` across scanned files
- **C15b:** Duplicate `<meta name="description">` across scanned files
- **Fail/High:** Duplicate found
- **Fix:** Each page must have unique title and description; use Venice AI to generate unique variants

### C16 — hreflang Tags
- **Weight:** 1 pt
- **Info:** Detected existing hreflang tags or `<html lang>` suggesting localization
- **No penalty** for absence unless multi-language signals are strong
- **Fix:** Add `<link rel="alternate" hreflang="...">` for each language/region variant

## PHP File Handling

PHP files (`.php`) are handled with a placeholder-substitution approach:

1. All `<?php ... ?>`, `<?= ... ?>`, and `<? ... ?>` blocks are extracted and replaced with
   inert HTML comments: `<!-- __PHP_BLOCK_0__ -->`
2. The resulting HTML is parsed and fixed normally
3. After fixing, PHP blocks are restored byte-for-byte from the extracted list
4. `php -l` is run to validate syntax; if it fails, the `.bak` file is restored

**Never modified:**
- PHP function bodies, database queries, template logic
- PHP `echo` / `print` statements
- PHP variable assignments

**Safe to modify (in HTML context only):**
- Content inside `<head>` (meta tags, title, canonical, schema)
- `alt=""` attributes on `<img>` tags
- `loading` attributes on `<img>` tags

## Idempotency Guarantee

Running `/seo fix` multiple times is safe:
- Before injecting any tag, the fixer checks if an equivalent tag already exists
- Duplicate detection uses attribute-matching (name, property, rel, type)
- PHP block extraction/restoration is deterministic

## Score Interpretation

| Grade | Range  | Interpretation |
|-------|--------|----------------|
| A     | 90–100 | Production-ready SEO |
| B     | 80–89  | Good; a few targeted improvements |
| C     | 70–79  | Functional but missing key signals |
| D     | 60–69  | Significant gaps; needs scheduled work |
| F     | 0–59   | Critical issues; requires immediate attention |
