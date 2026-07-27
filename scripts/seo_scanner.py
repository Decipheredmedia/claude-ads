"""SEO scanner for HTML and PHP files.

Parses .html and .php source files, checks for on-page and technical SEO
issues, and returns structured ``ScanResult`` objects.

PHP handling
------------
PHP blocks (``<?php ... ?>``, ``<?= ... ?>``) are replaced with inert
placeholder comments before HTML parsing, then restored byte-for-byte when
writing fixes.  The scanner never modifies PHP logic — only ``<head>``,
meta, schema, and semantic HTML sections are touched.

Checks performed (16 categories)
-----------------------------------
  C01  Title tag: presence, length (50–60 chars)
  C02  Meta description: presence, length (150–160 chars)
  C03  Viewport + charset meta tags
  C04  Heading structure: one H1, no skipped levels
  C05  Image alt attributes: missing / empty
  C06  Canonical link tag
  C07  Open Graph meta tags (og:title, og:description, og:image, og:url)
  C08  Twitter Card meta tags (twitter:card, twitter:title)
  C09  JSON-LD / Structured data presence
  C10  Robots meta tag validity
  C11  Image width/height attributes (CLS prevention)
  C12  Lazy-loading: ``loading="lazy"`` on off-screen images
  C13  Semantic HTML landmarks (nav, main, article/section, footer)
  C14  Render-blocking inline scripts / styles in <head>
  C15  Duplicate title or meta description (cross-file, caller-provided)
  C16  hreflang tags for multi-language sites

Usage
-----
>>> from seo_scanner import scan_file, scan_directory
>>> results = scan_directory("./public_html")
>>> for r in results:
...     print(r["path"], r["score"])

CLI
---
$ python seo_scanner.py ./public_html --json
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ─── Optional bs4 import ─────────────────────────────────────────────────────
try:
    from bs4 import BeautifulSoup, Tag

    _BS4 = True
except ImportError:
    _BS4 = False

# ─── PHP placeholder helpers ──────────────────────────────────────────────────

# Matches all PHP open/close tag variants: <?php...?>, <?=...?>, and <? ...?>
# Using a non-greedy match to avoid swallowing multiple blocks.
_PHP_BLOCK_RE = re.compile(r"<\?(?:php|=)?.*?\?>", re.DOTALL | re.IGNORECASE)
_PHP_PLACEHOLDER_TPL = "<!-- __PHP_BLOCK_{idx}__ -->"
_PHP_PLACEHOLDER_RE = re.compile(r"<!-- __PHP_BLOCK_(\d+)__ -->")


def extract_php_blocks(source: str) -> tuple[str, list[str]]:
    """Replace PHP blocks with inert HTML comments.

    Args:
        source: Raw PHP file content.

    Returns:
        Tuple of (html_with_placeholders, list_of_original_php_blocks).
    """
    blocks: list[str] = []

    def replacer(m: re.Match) -> str:
        idx = len(blocks)
        blocks.append(m.group(0))
        return _PHP_PLACEHOLDER_TPL.format(idx=idx)

    html = _PHP_BLOCK_RE.sub(replacer, source)
    return html, blocks


def restore_php_blocks(html: str, blocks: list[str]) -> str:
    """Restore PHP placeholder comments with original PHP source blocks."""

    def replacer(m: re.Match) -> str:
        idx = int(m.group(1))
        return blocks[idx] if idx < len(blocks) else m.group(0)

    return _PHP_PLACEHOLDER_RE.sub(replacer, html)


# ─── Check result dataclasses (plain dicts for JSON-serializability) ──────────

# severity levels: "critical" | "high" | "medium" | "low"
# status:          "pass" | "fail" | "warning" | "info"


def _check(
    id: str,
    category: str,
    status: str,
    message: str,
    severity: str = "medium",
    detail: Optional[str] = None,
    fix_hint: Optional[str] = None,
) -> dict:
    c = {
        "id": id,
        "category": category,
        "status": status,
        "message": message,
        "severity": severity,
    }
    if detail:
        c["detail"] = detail
    if fix_hint:
        c["fix_hint"] = fix_hint
    return c


# ─── Per-check scoring weights (deducted on fail) ────────────────────────────

_WEIGHTS: dict[str, int] = {
    "C01": 15,   # title
    "C02": 15,   # meta description
    "C03": 5,    # viewport / charset
    "C04": 10,   # heading structure
    "C05": 10,   # image alts
    "C06": 5,    # canonical
    "C07": 5,    # OG tags
    "C08": 3,    # Twitter card
    "C09": 8,    # JSON-LD
    "C10": 3,    # robots meta
    "C11": 5,    # img width/height
    "C12": 3,    # lazy loading
    "C13": 5,    # semantic HTML
    "C14": 3,    # render-blocking
    "C15": 5,    # duplicate title/desc
    "C16": 1,    # hreflang
}


# ─── Main scanner ─────────────────────────────────────────────────────────────


def scan_file(
    path: str | Path,
    known_titles: Optional[set[str]] = None,
    known_descs: Optional[set[str]] = None,
) -> dict:
    """Scan a single HTML or PHP file for SEO issues.

    Args:
        path:          Path to .html or .php file.
        known_titles:  Set of titles already seen in this scan batch (for C15).
        known_descs:   Set of descriptions already seen (for C15).

    Returns:
        A dict with keys: path, is_php, score, grade, checks, php_blocks,
        raw_html (placeholder-substituted), title, meta_description.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    is_php = path.suffix.lower() == ".php"

    php_blocks: list[str] = []
    if is_php:
        html_source, php_blocks = extract_php_blocks(raw)
    else:
        html_source = raw

    checks: list[dict] = []

    if _BS4:
        checks, meta = _scan_with_bs4(html_source, known_titles, known_descs)
    else:
        checks, meta = _scan_with_stdlib(html_source, known_titles, known_descs)

    score = _compute_score(checks)
    grade = _score_to_grade(score)

    return {
        "path": str(path),
        "is_php": is_php,
        "score": score,
        "grade": grade,
        "checks": checks,
        "php_blocks": php_blocks,
        "raw_html": html_source,
        "title": meta.get("title", ""),
        "meta_description": meta.get("meta_description", ""),
    }


def scan_directory(
    directory: str | Path,
    extensions: tuple[str, ...] = (".html", ".php"),
    max_files: int = 500,
) -> list[dict]:
    """Recursively scan a directory for HTML/PHP files.

    Args:
        directory:  Root directory to scan.
        extensions: File extensions to include.
        max_files:  Safety cap to prevent runaway scans.

    Returns:
        List of scan result dicts (one per file).
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    files: list[Path] = []
    for ext in extensions:
        files.extend(directory.rglob(f"*{ext}"))

    files = sorted(files)[:max_files]

    known_titles: set[str] = set()
    known_descs: set[str] = set()
    results: list[dict] = []

    for f in files:
        try:
            result = scan_file(f, known_titles, known_descs)
            # Track for duplicate detection
            if result["title"]:
                known_titles.add(result["title"])
            if result["meta_description"]:
                known_descs.add(result["meta_description"])
            results.append(result)
        except Exception as exc:
            results.append({
                "path": str(f),
                "is_php": f.suffix.lower() == ".php",
                "score": 0,
                "grade": "F",
                "checks": [
                    _check("ERR", "parse_error", "fail",
                           f"Could not parse file: {exc}", severity="critical")
                ],
                "php_blocks": [],
                "raw_html": "",
                "title": "",
                "meta_description": "",
                "error": str(exc),
            })

    return results


# ─── BeautifulSoup scanner ────────────────────────────────────────────────────


def _scan_with_bs4(
    html: str,
    known_titles: Optional[set[str]],
    known_descs: Optional[set[str]],
) -> tuple[list[dict], dict]:
    """Run all SEO checks using BeautifulSoup4."""
    soup = BeautifulSoup(html, "html.parser")
    checks: list[dict] = []
    meta: dict = {}

    # C01 — Title
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    meta["title"] = title_text
    checks.extend(_check_title(title_text))

    # C02 — Meta description
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    desc_text = desc_tag.get("content", "").strip() if desc_tag else ""
    meta["meta_description"] = desc_text
    checks.extend(_check_meta_description(desc_text))

    # C03 — Viewport + charset
    checks.extend(_check_viewport_charset(soup))

    # C04 — Heading structure
    checks.extend(_check_headings(soup))

    # C05 — Image alts
    checks.extend(_check_image_alts(soup))

    # C06 — Canonical
    checks.extend(_check_canonical(soup))

    # C07 — Open Graph
    checks.extend(_check_open_graph(soup))

    # C08 — Twitter Card
    checks.extend(_check_twitter_card(soup))

    # C09 — JSON-LD
    checks.extend(_check_jsonld(soup))

    # C10 — Robots meta
    checks.extend(_check_robots_meta(soup))

    # C11 — Image dimensions (CLS)
    checks.extend(_check_image_dimensions(soup))

    # C12 — Lazy loading
    checks.extend(_check_lazy_loading(soup))

    # C13 — Semantic HTML
    checks.extend(_check_semantic_html(soup))

    # C14 — Render-blocking
    checks.extend(_check_render_blocking(soup))

    # C15 — Duplicate detection
    checks.extend(_check_duplicates(title_text, desc_text, known_titles, known_descs))

    # C16 — hreflang
    checks.extend(_check_hreflang(soup))

    return checks, meta


# ─── Stdlib fallback scanner ──────────────────────────────────────────────────


def _scan_with_stdlib(
    html: str,
    known_titles: Optional[set[str]],
    known_descs: Optional[set[str]],
) -> tuple[list[dict], dict]:
    """Minimal scanner using only stdlib (no bs4).  Covers the most critical checks."""
    checks: list[dict] = []
    meta: dict = {}

    # Title
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.DOTALL)
    title_text = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
    meta["title"] = title_text
    checks.extend(_check_title(title_text))

    # Meta description
    m = re.search(
        r'<meta\s[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
        html, re.I,
    )
    if not m:
        m = re.search(
            r'<meta\s[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
            html, re.I,
        )
    desc_text = m.group(1).strip() if m else ""
    meta["meta_description"] = desc_text
    checks.extend(_check_meta_description(desc_text))

    # Viewport
    has_vp = bool(re.search(r'<meta\s[^>]*name=["\']viewport["\']', html, re.I))
    has_charset = bool(re.search(r'<meta\s[^>]*(charset|http-equiv=["\']Content-Type)', html, re.I))
    if not has_vp:
        checks.append(_check("C03a", "viewport", "fail",
                              "Missing <meta name='viewport'>", severity="high",
                              fix_hint='Add: <meta name="viewport" content="width=device-width, initial-scale=1">'))
    else:
        checks.append(_check("C03a", "viewport", "pass", "Viewport meta tag present"))
    if not has_charset:
        checks.append(_check("C03b", "charset", "fail",
                              "Missing charset declaration", severity="medium",
                              fix_hint='Add: <meta charset="UTF-8">'))
    else:
        checks.append(_check("C03b", "charset", "pass", "Charset declared"))

    # H1
    h1_count = len(re.findall(r"<h1[\s>]", html, re.I))
    if h1_count == 0:
        checks.append(_check("C04a", "headings", "fail", "No <h1> tag found", severity="high",
                              fix_hint="Add a single <h1> tag with your primary keyword."))
    elif h1_count > 1:
        checks.append(_check("C04a", "headings", "fail",
                              f"Multiple <h1> tags ({h1_count})", severity="high",
                              fix_hint="Keep exactly one <h1> per page."))
    else:
        checks.append(_check("C04a", "headings", "pass", "Single <h1> found"))

    # Canonical
    has_canonical = bool(re.search(r'<link\s[^>]*rel=["\']canonical["\']', html, re.I))
    if not has_canonical:
        checks.append(_check("C06", "canonical", "fail",
                              "Missing canonical link tag", severity="high",
                              fix_hint='Add: <link rel="canonical" href="https://example.com/page">'))
    else:
        checks.append(_check("C06", "canonical", "pass", "Canonical tag present"))

    # Duplicate check
    checks.extend(_check_duplicates(title_text, desc_text, known_titles, known_descs))

    return checks, meta


# ─── Individual check functions ───────────────────────────────────────────────


def _check_title(title: str) -> list[dict]:
    if not title:
        return [_check("C01", "title", "fail",
                       "Missing <title> tag", severity="critical",
                       fix_hint="Add a <title> tag between 50–60 characters.")]
    length = len(title)
    if length < 10:
        return [_check("C01", "title", "fail",
                       f"Title too short ({length} chars, need 50–60)",
                       severity="high",
                       fix_hint="Expand the title to 50–60 characters including your primary keyword.")]
    if length < 50:
        return [_check("C01", "title", "warning",
                       f"Title below ideal length ({length} chars, ideal 50–60)",
                       severity="medium",
                       fix_hint="Expand the title to 50–60 characters including your primary keyword.")]
    if length > 60:
        return [_check("C01", "title", "warning",
                       f"Title too long ({length} chars, ideal 50–60)",
                       severity="medium",
                       fix_hint="Trim the title to 60 characters or fewer to avoid truncation in SERPs.")]
    return [_check("C01", "title", "pass", f"Title length OK ({length} chars)")]


def _check_meta_description(desc: str) -> list[dict]:
    if not desc:
        return [_check("C02", "meta_description", "fail",
                       "Missing meta description", severity="high",
                       fix_hint="Add a <meta name='description'> between 150–160 characters.")]
    length = len(desc)
    if length < 50:
        return [_check("C02", "meta_description", "fail",
                       f"Meta description too short ({length} chars, need 150–160)",
                       severity="high",
                       fix_hint="Expand the meta description to 150–160 characters.")]
    if length > 160:
        return [_check("C02", "meta_description", "warning",
                       f"Meta description too long ({length} chars, ideal 150–160)",
                       severity="medium",
                       fix_hint="Trim the meta description to 160 characters or fewer.")]
    return [_check("C02", "meta_description", "pass", f"Meta description length OK ({length} chars)")]


def _check_viewport_charset(soup) -> list[dict]:
    results = []
    has_vp = bool(soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}))
    if not has_vp:
        results.append(_check("C03a", "viewport", "fail",
                               "Missing <meta name='viewport'>", severity="high",
                               fix_hint='Add: <meta name="viewport" content="width=device-width, initial-scale=1">'))
    else:
        results.append(_check("C03a", "viewport", "pass", "Viewport meta tag present"))

    # charset: <meta charset="utf-8"> or <meta http-equiv="Content-Type" ...>
    has_charset = bool(
        soup.find("meta", charset=True)
        or soup.find("meta", attrs={"http-equiv": re.compile(r"content-type", re.I)})
    )
    if not has_charset:
        results.append(_check("C03b", "charset", "fail",
                               "Missing charset declaration", severity="medium",
                               fix_hint='Add: <meta charset="UTF-8">'))
    else:
        results.append(_check("C03b", "charset", "pass", "Charset declared"))
    return results


def _check_headings(soup) -> list[dict]:
    results = []
    h1_tags = soup.find_all("h1")
    if not h1_tags:
        results.append(_check("C04a", "headings", "fail", "No <h1> tag found",
                               severity="high",
                               fix_hint="Add a single <h1> containing the primary keyword."))
    elif len(h1_tags) > 1:
        results.append(_check("C04a", "headings", "fail",
                               f"Multiple <h1> tags ({len(h1_tags)})", severity="high",
                               fix_hint="Keep exactly one <h1> per page."))
    else:
        results.append(_check("C04a", "headings", "pass", "Single <h1> found"))

    # Check for skipped heading levels (e.g., H1 → H3, skipping H2)
    levels = [int(t.name[1]) for t in soup.find_all(re.compile(r"^h[1-6]$", re.I))]
    skipped: list[str] = []
    for i in range(len(levels) - 1):
        if levels[i + 1] > levels[i] + 1:
            skipped.append(f"H{levels[i]} → H{levels[i+1]}")
    if skipped:
        results.append(_check("C04b", "headings", "warning",
                               f"Skipped heading level(s): {', '.join(skipped)}",
                               severity="medium",
                               fix_hint="Do not skip heading levels for proper document structure."))
    else:
        results.append(_check("C04b", "headings", "pass", "Heading hierarchy is sequential"))

    return results


def _check_image_alts(soup) -> list[dict]:
    imgs = soup.find_all("img")
    missing = [img for img in imgs if not img.get("alt")]
    if not imgs:
        return [_check("C05", "image_alts", "info", "No images found on this page")]
    if missing:
        srcs = [img.get("src", "")[:50] for img in missing[:5]]
        return [_check("C05", "image_alts", "fail",
                       f"{len(missing)} image(s) missing alt text",
                       severity="high",
                       detail=f"First offenders: {', '.join(srcs)}",
                       fix_hint="Add descriptive alt attributes to all <img> tags.")]
    return [_check("C05", "image_alts", "pass", f"All {len(imgs)} image(s) have alt text")]


def _check_canonical(soup) -> list[dict]:
    canonical = soup.find("link", attrs={"rel": re.compile(r"canonical", re.I)})
    if not canonical:
        return [_check("C06", "canonical", "fail",
                       "Missing canonical link tag", severity="high",
                       fix_hint='Add: <link rel="canonical" href="https://example.com/page/">')]
    href = canonical.get("href", "").strip()
    if not href:
        return [_check("C06", "canonical", "warning",
                       "Canonical tag present but href is empty", severity="medium",
                       fix_hint="Set a full absolute URL in the canonical href.")]
    return [_check("C06", "canonical", "pass", f"Canonical tag present: {href[:60]}")]


def _check_open_graph(soup) -> list[dict]:
    required_props = ["og:title", "og:description", "og:image", "og:url"]
    found = {
        tag.get("property", "").lower()
        for tag in soup.find_all("meta", property=True)
    }
    missing = [p for p in required_props if p not in found]
    if missing:
        return [_check("C07", "open_graph", "fail",
                       f"Missing OG tags: {', '.join(missing)}", severity="medium",
                       fix_hint=f"Add missing Open Graph meta tags to <head>.")]
    return [_check("C07", "open_graph", "pass", "All core Open Graph tags present")]


def _check_twitter_card(soup) -> list[dict]:
    required = ["twitter:card"]
    found = {
        tag.get("name", "").lower()
        for tag in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)})
    }
    missing = [p for p in required if p not in found]
    if missing:
        return [_check("C08", "twitter_card", "warning",
                       "Missing Twitter Card meta tags", severity="low",
                       fix_hint='Add: <meta name="twitter:card" content="summary_large_image">')]
    return [_check("C08", "twitter_card", "pass", "Twitter Card tag present")]


def _check_jsonld(soup) -> list[dict]:
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    if not scripts:
        return [_check("C09", "structured_data", "fail",
                       "No JSON-LD structured data found", severity="high",
                       fix_hint="Add appropriate JSON-LD schema (Article, Product, LocalBusiness, etc.).")]
    try:
        schemas = [json.loads(s.get_text()) for s in scripts]
        types = [s.get("@type", "unknown") for s in schemas]
        return [_check("C09", "structured_data", "pass",
                       f"JSON-LD present: {', '.join(str(t) for t in types)}")]
    except (json.JSONDecodeError, AttributeError):
        return [_check("C09", "structured_data", "warning",
                       "JSON-LD present but malformed", severity="medium",
                       fix_hint="Validate your JSON-LD at https://validator.schema.org/")]


def _check_robots_meta(soup) -> list[dict]:
    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    if not robots:
        return [_check("C10", "robots_meta", "info",
                       "No robots meta tag (defaults to index,follow — OK for public pages)")]
    content = robots.get("content", "").lower()
    if "noindex" in content:
        return [_check("C10", "robots_meta", "warning",
                       f"Page is set to NOINDEX: '{content}'", severity="high",
                       fix_hint="Remove noindex if this page should appear in search results.")]
    return [_check("C10", "robots_meta", "pass", f"Robots meta: '{content}'")]


def _check_image_dimensions(soup) -> list[dict]:
    imgs = soup.find_all("img")
    missing_dims = [
        img for img in imgs
        if not (img.get("width") and img.get("height"))
    ]
    if not imgs:
        return []
    if missing_dims:
        return [_check("C11", "image_dimensions", "warning",
                       f"{len(missing_dims)} image(s) missing width/height (may cause CLS)",
                       severity="medium",
                       fix_hint="Add explicit width and height attributes to prevent layout shift.")]
    return [_check("C11", "image_dimensions", "pass", "All images have width/height attributes")]


def _check_lazy_loading(soup) -> list[dict]:
    imgs = soup.find_all("img")
    without_lazy = [img for img in imgs if img.get("loading") != "lazy"]
    if len(without_lazy) > 2:
        return [_check("C12", "lazy_loading", "warning",
                       f"{len(without_lazy)} image(s) missing loading='lazy'",
                       severity="low",
                       fix_hint='Add loading="lazy" to images below the fold.')]
    return [_check("C12", "lazy_loading", "pass", "Lazy loading applied")]


def _check_semantic_html(soup) -> list[dict]:
    results = []
    for landmark, severity in [("nav", "medium"), ("main", "high"), ("footer", "low")]:
        if not soup.find(landmark):
            results.append(_check("C13", "semantic_html", "warning",
                                   f"Missing <{landmark}> landmark", severity=severity,
                                   fix_hint=f"Wrap appropriate content in a <{landmark}> element."))
    if not results:
        results.append(_check("C13", "semantic_html", "pass",
                               "Core semantic HTML landmarks present (nav, main, footer)"))
    return results


def _check_render_blocking(soup) -> list[dict]:
    head = soup.find("head")
    if not head:
        return []
    blocking = []
    for tag in head.find_all(["script", "style"]):
        if tag.name == "script":
            # Inline script or external without async/defer
            if not (tag.get("async") or tag.get("defer") or tag.get("type") in ("application/ld+json",)):
                blocking.append(tag.name)
        elif tag.name == "style" and tag.get_text(strip=True):
            blocking.append("inline-style")

    if blocking:
        return [_check("C14", "render_blocking", "warning",
                       f"Potential render-blocking elements in <head>: {len(blocking)}",
                       severity="low",
                       fix_hint="Add async/defer to <script> tags; consider moving non-critical CSS out of <head>.")]
    return [_check("C14", "render_blocking", "pass", "No obvious render-blocking elements in <head>")]


def _check_duplicates(
    title: str,
    desc: str,
    known_titles: Optional[set[str]],
    known_descs: Optional[set[str]],
) -> list[dict]:
    results = []
    if title and known_titles and title in known_titles:
        results.append(_check("C15a", "duplicate_title", "fail",
                               "Duplicate title detected across scanned files",
                               severity="high",
                               fix_hint="Each page must have a unique <title> tag."))
    if desc and known_descs and desc in known_descs:
        results.append(_check("C15b", "duplicate_description", "fail",
                               "Duplicate meta description detected across scanned files",
                               severity="high",
                               fix_hint="Each page must have a unique meta description."))
    return results


def _check_hreflang(soup) -> list[dict]:
    hreflang_tags = soup.find_all("link", attrs={"hreflang": True})
    # Only flag if there are strong signals of a multi-language site
    html_tag = soup.find("html")
    lang = html_tag.get("lang", "") if html_tag else ""
    if hreflang_tags:
        return [_check("C16", "hreflang", "pass",
                       f"{len(hreflang_tags)} hreflang tag(s) found")]
    if lang and "-" in lang:
        # e.g., lang="en-US" suggests localized content
        return [_check("C16", "hreflang", "info",
                       "Consider adding hreflang tags if you serve multiple languages/regions")]
    return []


# ─── Scoring ──────────────────────────────────────────────────────────────────


def _compute_score(checks: list[dict]) -> int:
    """Return a 0–100 SEO score based on failed/warned checks."""
    score = 100
    for c in checks:
        if c["status"] in ("fail", "warning"):
            cid_prefix = c["id"][:3]
            weight = _WEIGHTS.get(cid_prefix, 2)
            if c["status"] == "fail":
                score -= weight
            else:  # warning
                score -= weight // 2
    return max(0, min(100, score))


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


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="SEO scanner for HTML/PHP files")
    parser.add_argument("path", help="File or directory to scan")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    target = Path(args.path)
    if target.is_dir():
        results = scan_directory(target)
    elif target.is_file():
        results = [scan_file(target)]
    else:
        print(f"Error: not found: {target}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"\n{'='*60}")
            print(f"  {r['path']}  |  Score: {r['score']}/100  ({r['grade']})")
            print(f"{'='*60}")
            for c in r["checks"]:
                icon = {"pass": "✓", "fail": "✗", "warning": "⚠", "info": "ℹ"}.get(c["status"], "?")
                print(f"  {icon} [{c['id']}] {c['message']}")
                if "fix_hint" in c and c["status"] != "pass":
                    print(f"      → {c['fix_hint']}")


if __name__ == "__main__":
    _cli()
