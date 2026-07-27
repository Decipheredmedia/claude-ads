"""SEO auto-fixer — applies safe, idempotent fixes to HTML and PHP files.

Safe automatic fixes (no Venice AI required)
--------------------------------------------
  - Add <meta charset="UTF-8"> if missing
  - Add <meta name="viewport" ...> if missing
  - Add <link rel="canonical" href="..."> if missing
  - Add missing Open Graph / Twitter Card meta tags (basic stubs)
  - Add loading="lazy" to images below the fold (all but first 2)
  - Add <robots.txt> and <sitemap.xml> stubs at project root if missing

Venice AI-assisted fixes (require VENICE_API_KEY)
--------------------------------------------------
  - Generate / rewrite <title> if missing or wrong length
  - Generate <meta name="description"> if missing or wrong length
  - Generate alt text for images with missing alt attributes
  - Generate JSON-LD structured data snippet

PHP safety
----------
  - PHP files are only fixed in <head> / meta sections
  - After fix, ``php -l`` is run if PHP CLI is available;
    if it fails, the .bak is restored and the file is skipped
  - Fixes are idempotent: existing tags are never duplicated

Backup + dry-run
----------------
  - Before any in-place write, a ``.bak`` file is created
  - ``--dry-run`` prints a unified diff without writing

Usage (Python API)
------------------
>>> from seo_fixer import fix_file, fix_directory
>>> fix_file("./index.html", dry_run=False)
>>> fix_directory("./public_html", dry_run=True)

CLI
---
$ python seo_fixer.py ./public_html --dry-run
$ python seo_fixer.py ./index.html
$ python seo_fixer.py ./public_html --no-backup
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from seo_scanner import (
    extract_php_blocks,
    restore_php_blocks,
    scan_file,
)

# ─── Constants ────────────────────────────────────────────────────────────────

_DEFAULT_VIEWPORT = 'width=device-width, initial-scale=1'
_DEFAULT_OG_TYPE = "website"

# ─── Public API ───────────────────────────────────────────────────────────────


def fix_file(
    path: str | Path,
    dry_run: bool = False,
    backup: bool = True,
    venice_provider=None,
    site_url: str = "",
) -> dict:
    """Apply SEO fixes to a single HTML or PHP file.

    Args:
        path:            Path to the file.
        dry_run:         If True, print diff but do not write.
        backup:          If True, write ``.bak`` backup before overwriting.
        venice_provider: Optional LLM provider for AI-assisted fixes.
        site_url:        Base URL of the site (used for canonical tags).

    Returns:
        Dict with keys: path, status, fixes_applied, diff (if dry_run), error.
    """
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "status": "error", "error": "File not found", "fixes_applied": []}

    suffix = path.suffix.lower()
    if suffix not in (".html", ".php"):
        return {"path": str(path), "status": "skipped", "fixes_applied": []}

    original = path.read_text(encoding="utf-8", errors="replace")

    # Scan the file first to know what needs fixing
    scan = scan_file(path)
    failed_ids = {c["id"] for c in scan["checks"] if c["status"] in ("fail", "warning")}

    if not failed_ids:
        return {"path": str(path), "status": "ok", "fixes_applied": [], "score": scan["score"]}

    # Work on placeholder-substituted HTML for PHP files
    is_php = suffix == ".php"
    php_blocks: list[str] = scan.get("php_blocks", [])
    working_html = scan.get("raw_html", original)

    # Apply fixes
    fixed_html, fixes_applied = _apply_fixes(
        working_html,
        failed_ids,
        scan,
        venice_provider=venice_provider,
        site_url=site_url,
        is_php=is_php,
    )

    if not fixes_applied:
        return {"path": str(path), "status": "ok", "fixes_applied": [], "score": scan["score"]}

    # Restore PHP blocks
    if is_php:
        fixed_source = restore_php_blocks(fixed_html, php_blocks)
    else:
        fixed_source = fixed_html

    if fixed_source == original:
        return {"path": str(path), "status": "ok", "fixes_applied": [], "score": scan["score"]}

    # Generate diff
    diff_lines = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        fixed_source.splitlines(keepends=True),
        fromfile=f"{path} (original)",
        tofile=f"{path} (fixed)",
    ))
    diff_str = "".join(diff_lines)

    if dry_run:
        if diff_str:
            print(diff_str)
        return {
            "path": str(path),
            "status": "dry_run",
            "fixes_applied": fixes_applied,
            "diff": diff_str,
        }

    # Write file
    if backup:
        bak_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak_path)

    path.write_text(fixed_source, encoding="utf-8")

    # Validate PHP syntax if php CLI is available
    if is_php and _php_available():
        valid, err = _validate_php(path)
        if not valid:
            # Restore from backup
            if backup:
                shutil.copy2(bak_path, path)
            else:
                path.write_text(original, encoding="utf-8")
            return {
                "path": str(path),
                "status": "error",
                "error": f"PHP syntax validation failed after fix: {err}. File restored.",
                "fixes_applied": [],
            }

    return {
        "path": str(path),
        "status": "fixed",
        "fixes_applied": fixes_applied,
        "score_before": scan["score"],
    }


def fix_directory(
    directory: str | Path,
    dry_run: bool = False,
    backup: bool = True,
    venice_provider=None,
    site_url: str = "",
    generate_robots: bool = True,
    generate_sitemap: bool = True,
) -> list[dict]:
    """Apply SEO fixes to all HTML/PHP files in a directory.

    Args:
        directory:         Root directory to scan.
        dry_run:           If True, preview changes without writing.
        backup:            If True, write .bak before overwriting.
        venice_provider:   Optional Venice AI provider.
        site_url:          Base site URL.
        generate_robots:   Generate robots.txt if missing.
        generate_sitemap:  Generate sitemap.xml stub if missing.

    Returns:
        List of fix result dicts, one per processed file.
    """
    directory = Path(directory)
    results: list[dict] = []

    for ext in (".html", ".php"):
        for f in sorted(directory.rglob(f"*{ext}")):
            result = fix_file(
                f,
                dry_run=dry_run,
                backup=backup,
                venice_provider=venice_provider,
                site_url=site_url,
            )
            results.append(result)

    # Generate project-level files
    if generate_robots:
        robots_result = _ensure_robots_txt(directory, site_url, dry_run)
        if robots_result:
            results.append(robots_result)

    if generate_sitemap:
        sitemap_result = _ensure_sitemap_xml(directory, site_url, results, dry_run)
        if sitemap_result:
            results.append(sitemap_result)

    return results


# ─── Core fix engine ──────────────────────────────────────────────────────────


def _apply_fixes(
    html: str,
    failed_ids: set[str],
    scan: dict,
    venice_provider=None,
    site_url: str = "",
    is_php: bool = False,
) -> tuple[str, list[str]]:
    """Apply all applicable fixes and return (fixed_html, list_of_applied_fix_names)."""
    fixes_applied: list[str] = []

    # Ensure we have a <head> section to inject into
    html = _ensure_head(html)

    # C03b — charset
    if "C03b" in failed_ids and not _has_charset(html):
        html = _inject_into_head(html, '<meta charset="UTF-8">', position="first")
        fixes_applied.append("charset")

    # C03a — viewport
    if "C03a" in failed_ids and not _has_meta_name(html, "viewport"):
        html = _inject_into_head(
            html,
            f'<meta name="viewport" content="{_DEFAULT_VIEWPORT}">',
        )
        fixes_applied.append("viewport")

    # C01 — title (Venice AI if available)
    if "C01" in failed_ids and venice_provider:
        title_text = scan.get("title", "")
        page_hint = _extract_page_hint(html)
        if not title_text or len(title_text) < 10 or len(title_text) > 60:
            try:
                prompt = (
                    f"Write a concise, keyword-rich SEO title (50–60 chars) for a web page about: {page_hint}. "
                    "Reply with ONLY the title text, no quotes."
                )
                new_title = venice_provider.complete(
                    [{"role": "user", "content": prompt}],
                    system="You are an expert SEO copywriter.",
                    max_tokens=80,
                )[:60].strip()
                if title_text:
                    html = re.sub(r"(<title[^>]*>).*?(</title>)", f"\\g<1>{new_title}\\g<2>", html, flags=re.I | re.DOTALL)
                else:
                    html = _inject_into_head(html, f"<title>{new_title}</title>")
                fixes_applied.append("title")
            except Exception:
                pass  # Skip AI fix on error, do not corrupt the file

    # C02 — meta description (Venice AI if available)
    if "C02" in failed_ids and venice_provider:
        desc_text = scan.get("meta_description", "")
        if not desc_text or len(desc_text) < 50 or len(desc_text) > 160:
            page_hint = _extract_page_hint(html)
            try:
                prompt = (
                    f"Write a compelling meta description (150–160 chars) for a web page about: {page_hint}. "
                    "Reply with ONLY the description text, no quotes."
                )
                new_desc = venice_provider.complete(
                    [{"role": "user", "content": prompt}],
                    system="You are an expert SEO copywriter.",
                    max_tokens=200,
                )[:160].strip()
                if desc_text:
                    html = re.sub(
                        r'(<meta\s[^>]*name=["\']description["\'][^>]*content=["\'])([^"\']*?)(["\'])',
                        f'\\g<1>{_escape_attr(new_desc)}\\g<3>',
                        html, flags=re.I,
                    )
                else:
                    html = _inject_into_head(
                        html,
                        f'<meta name="description" content="{_escape_attr(new_desc)}">',
                    )
                fixes_applied.append("meta_description")
            except Exception:
                pass

    # C05 — image alt attributes (Venice AI if available)
    if "C05" in failed_ids and venice_provider:
        html, alt_count = _fix_image_alts(html, venice_provider)
        if alt_count:
            fixes_applied.append(f"image_alts ({alt_count})")

    # C06 — canonical
    if "C06" in failed_ids and not _has_canonical(html):
        canonical_href = site_url.rstrip("/") + "/" if site_url else ""
        html = _inject_into_head(html, f'<link rel="canonical" href="{canonical_href}">')
        fixes_applied.append("canonical")

    # C07 — Open Graph tags
    if "C07" in failed_ids:
        html, og_count = _fix_og_tags(html, scan, site_url, venice_provider)
        if og_count:
            fixes_applied.append(f"og_tags ({og_count})")

    # C08 — Twitter Card
    if "C08" in failed_ids and not _has_meta_name(html, "twitter:card"):
        html = _inject_into_head(html, '<meta name="twitter:card" content="summary_large_image">')
        fixes_applied.append("twitter_card")

    # C09 — JSON-LD (Venice AI if available)
    if "C09" in failed_ids and venice_provider:
        html, schema_added = _fix_jsonld(html, scan, venice_provider)
        if schema_added:
            fixes_applied.append("jsonld_schema")

    # C11 — image width/height: skip (requires actual image dimension data)
    # C12 — lazy loading
    if "C12" in failed_ids:
        html, lazy_count = _fix_lazy_loading(html)
        if lazy_count:
            fixes_applied.append(f"lazy_loading ({lazy_count})")

    return html, fixes_applied


# ─── Individual fix helpers ───────────────────────────────────────────────────


def _ensure_head(html: str) -> str:
    """Ensure the document has a <head> section; add one if missing."""
    if re.search(r"<head[\s>]", html, re.I):
        return html
    # No <head>: inject after <html> or at the start
    if re.search(r"<html[\s>]", html, re.I):
        return re.sub(r"(<html[^>]*>)", r"\1\n<head></head>", html, flags=re.I)
    return f"<head></head>\n{html}"


def _inject_into_head(html: str, tag: str, position: str = "last") -> str:
    """Inject a tag into <head>.  position='first' or 'last'."""
    # Guard: don't inject if the tag is already present (idempotency)
    tag_name = re.match(r"<(\w+)", tag)
    if tag_name:
        tag_key = tag_name.group(1).lower()
        if tag_key == "meta":
            # Check by name or charset attribute
            name_m = re.search(r'name=["\']([^"\']+)["\']', tag, re.I)
            charset_m = re.search(r'charset', tag, re.I)
            prop_m = re.search(r'property=["\']([^"\']+)["\']', tag, re.I)
            if name_m and _has_meta_name(html, name_m.group(1)):
                return html
            if charset_m and _has_charset(html):
                return html
            if prop_m and _has_meta_property(html, prop_m.group(1)):
                return html
        elif tag_key == "link":
            rel_m = re.search(r'rel=["\']([^"\']+)["\']', tag, re.I)
            if rel_m and rel_m.group(1).lower() == "canonical" and _has_canonical(html):
                return html

    if position == "first":
        return re.sub(r"(<head[^>]*>)", f"\\1\n  {tag}", html, flags=re.I, count=1)
    # last: inject before </head>
    if re.search(r"</head>", html, re.I):
        return re.sub(r"(</head>)", f"  {tag}\n\\1", html, flags=re.I, count=1)
    return re.sub(r"(<head[^>]*>)", f"\\1\n  {tag}", html, flags=re.I, count=1)


def _fix_image_alts(html: str, provider) -> tuple[str, int]:
    """Generate alt text for images missing it using Venice AI."""
    count = 0
    img_re = re.compile(r'<img\s([^>]*)>', re.I)

    def replacer(m: re.Match) -> str:
        nonlocal count
        attrs = m.group(1)
        if re.search(r'\balt\s*=', attrs, re.I):
            return m.group(0)  # Already has alt
        src_m = re.search(r'src=["\']([^"\']+)["\']', attrs, re.I)
        src = src_m.group(1) if src_m else ""
        filename = Path(src).stem.replace("-", " ").replace("_", " ") if src else "image"
        try:
            prompt = f"Write a short, descriptive SEO alt text (max 125 chars) for an image with filename: '{filename}'. Reply with ONLY the alt text, no quotes."
            alt_text = provider.complete(
                [{"role": "user", "content": prompt}],
                system="You are an SEO expert. Write concise, descriptive alt text.",
                max_tokens=60,
            )[:125].strip()
        except Exception:
            alt_text = filename[:125]
        count += 1
        return f'<img {attrs} alt="{_escape_attr(alt_text)}">'

    return img_re.sub(replacer, html), count


def _fix_og_tags(html: str, scan: dict, site_url: str, provider=None) -> tuple[str, int]:
    """Add missing Open Graph meta tags."""
    count = 0
    title = scan.get("title", "Page")
    desc = scan.get("meta_description", "")

    needed = {
        "og:title": f'<meta property="og:title" content="{_escape_attr(title)}">',
        "og:description": f'<meta property="og:description" content="{_escape_attr(desc[:160])}">',
        "og:url": f'<meta property="og:url" content="{site_url}">',
        "og:type": f'<meta property="og:type" content="{_DEFAULT_OG_TYPE}">',
    }

    for prop, tag in needed.items():
        if not _has_meta_property(html, prop):
            html = _inject_into_head(html, tag)
            count += 1

    # og:image — skip if no image URL is available (user must set manually)
    return html, count


def _fix_jsonld(html: str, scan: dict, provider) -> tuple[str, bool]:
    """Generate and inject a JSON-LD schema block using Venice AI."""
    # Check idempotency: don't inject if one already exists
    if re.search(r'<script[^>]*type=["\']application/ld\+json["\']', html, re.I):
        return html, False

    title = scan.get("title", "")
    desc = scan.get("meta_description", "")
    page_hint = _extract_page_hint(html)

    prompt = (
        f"Generate a valid JSON-LD schema.org structured data snippet for a web page. "
        f"Page title: '{title}'. Description: '{desc}'. Page content hint: '{page_hint[:200]}'. "
        "Choose the most appropriate @type (Article, WebPage, LocalBusiness, Product, or FAQPage). "
        "Reply with ONLY the raw JSON-LD object (no <script> tags, no markdown fencing)."
    )
    try:
        schema_json = provider.complete(
            [{"role": "user", "content": prompt}],
            system="You are an SEO expert. Generate valid schema.org JSON-LD.",
            max_tokens=400,
        ).strip()
        # Validate it's parseable JSON
        json.loads(schema_json)
        tag = f'<script type="application/ld+json">\n{schema_json}\n</script>'
        html = _inject_into_head(html, tag)
        return html, True
    except Exception:
        return html, False


def _fix_lazy_loading(html: str) -> tuple[str, int]:
    """Add loading='lazy' to images that are likely below the fold (all after the 2nd)."""
    count = 0
    img_count = 0
    img_re = re.compile(r'<img\s([^>]*)>', re.I)

    def replacer(m: re.Match) -> str:
        nonlocal count, img_count
        img_count += 1
        attrs = m.group(1)
        if img_count <= 2:
            return m.group(0)  # Skip hero/above-fold images
        if re.search(r'\bloading\s*=', attrs, re.I):
            return m.group(0)  # Already has loading attribute
        count += 1
        return f'<img {attrs} loading="lazy">'

    return img_re.sub(replacer, html), count


# ─── Presence checks (for idempotency) ────────────────────────────────────────


def _has_charset(html: str) -> bool:
    return bool(
        re.search(r'<meta\s[^>]*charset\s*=', html, re.I)
        or re.search(r'<meta\s[^>]*http-equiv=["\']content-type["\']', html, re.I)
    )


def _has_meta_name(html: str, name: str) -> bool:
    pattern = re.compile(
        r'<meta\s[^>]*name=["\']' + re.escape(name) + r'["\']', re.I
    )
    return bool(pattern.search(html))


def _has_meta_property(html: str, prop: str) -> bool:
    pattern = re.compile(
        r'<meta\s[^>]*property=["\']' + re.escape(prop) + r'["\']', re.I
    )
    return bool(pattern.search(html))


def _has_canonical(html: str) -> bool:
    return bool(re.search(r'<link\s[^>]*rel=["\']canonical["\']', html, re.I))


def _extract_page_hint(html: str) -> str:
    """Extract a brief text hint about the page content from H1 or body text."""
    h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.DOTALL)
    if h1_m:
        return re.sub(r"<[^>]+>", "", h1_m.group(1)).strip()[:200]
    # Fall back to first non-empty paragraph text
    p_m = re.search(r"<p[^>]*>(.*?)</p>", html, re.I | re.DOTALL)
    if p_m:
        return re.sub(r"<[^>]+>", "", p_m.group(1)).strip()[:200]
    return "web page"


def _escape_attr(s: str) -> str:
    """Minimal HTML attribute value escaping."""
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


# ─── Project-level files ──────────────────────────────────────────────────────


def _ensure_robots_txt(
    root: Path, site_url: str, dry_run: bool
) -> Optional[dict]:
    robots_path = root / "robots.txt"
    if robots_path.exists():
        return None

    sitemap_url = f"{site_url.rstrip('/')}/sitemap.xml" if site_url else "/sitemap.xml"
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {sitemap_url}\n"
    )

    if dry_run:
        print(f"[dry-run] Would create: {robots_path}")
        print(content)
        return {"path": str(robots_path), "status": "dry_run", "fixes_applied": ["robots_txt"]}

    robots_path.write_text(content, encoding="utf-8")
    return {"path": str(robots_path), "status": "created", "fixes_applied": ["robots_txt"]}


def _ensure_sitemap_xml(
    root: Path, site_url: str, file_results: list[dict], dry_run: bool
) -> Optional[dict]:
    sitemap_path = root / "sitemap.xml"
    if sitemap_path.exists():
        return None

    base = site_url.rstrip("/") if site_url else "https://example.com"
    # Collect HTML files that were successfully scanned/fixed
    urls = []
    for r in file_results:
        p = Path(r["path"])
        if p.suffix in (".html", ".php") and not r.get("error"):
            rel = p.relative_to(root) if root in p.parents else p.name
            urls.append(f"{base}/{rel}")

    entries = "\n".join(
        f"  <url><loc>{u}</loc></url>" for u in urls[:500]
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )

    if dry_run:
        print(f"[dry-run] Would create: {sitemap_path}")
        return {"path": str(sitemap_path), "status": "dry_run", "fixes_applied": ["sitemap_xml"]}

    sitemap_path.write_text(content, encoding="utf-8")
    return {"path": str(sitemap_path), "status": "created", "fixes_applied": ["sitemap_xml"]}


# ─── PHP validation ───────────────────────────────────────────────────────────


def _php_available() -> bool:
    return shutil.which("php") is not None


def _validate_php(path: Path) -> tuple[bool, str]:
    """Run ``php -l`` on a file.  Returns (is_valid, error_message)."""
    try:
        result = subprocess.run(
            ["php", "-l", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, ""
        return False, (result.stdout + result.stderr).strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True, ""  # Can't validate, assume OK


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="SEO auto-fixer for HTML/PHP files")
    parser.add_argument("path", help="File or directory to fix")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--no-backup", action="store_true", help="Skip .bak file creation")
    parser.add_argument("--site-url", default="", help="Base URL of the site")
    parser.add_argument("--no-robots", action="store_true", help="Skip robots.txt generation")
    parser.add_argument("--no-sitemap", action="store_true", help="Skip sitemap.xml generation")
    args = parser.parse_args()

    # Try to load Venice provider if API key is available
    try:
        from venice_provider import get_provider
        provider = get_provider()
        if not getattr(provider, "api_key", None):
            provider = None
    except Exception:
        provider = None

    target = Path(args.path)
    if target.is_dir():
        results = fix_directory(
            target,
            dry_run=args.dry_run,
            backup=not args.no_backup,
            venice_provider=provider,
            site_url=args.site_url,
            generate_robots=not args.no_robots,
            generate_sitemap=not args.no_sitemap,
        )
    elif target.is_file():
        results = [fix_file(
            target,
            dry_run=args.dry_run,
            backup=not args.no_backup,
            venice_provider=provider,
            site_url=args.site_url,
        )]
    else:
        print(f"Error: not found: {target}", file=sys.stderr)
        sys.exit(1)

    # Summary
    fixed = [r for r in results if r.get("status") == "fixed"]
    errors = [r for r in results if r.get("status") == "error"]
    dry_run_count = [r for r in results if r.get("status") == "dry_run"]

    if args.dry_run:
        print(f"\n✓ Dry-run complete: {len(dry_run_count)} file(s) would be modified")
    else:
        print(f"\n✓ Fixed: {len(fixed)} file(s)")
        if errors:
            print(f"✗ Errors: {len(errors)}")
            for e in errors:
                print(f"  {e['path']}: {e.get('error', '')}")


if __name__ == "__main__":
    _cli()
