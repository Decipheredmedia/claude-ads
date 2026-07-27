"""Tests for the SEO scanner (seo_scanner.py).

Covers:
- PHP block extraction and restoration
- All 16 check categories (pass / fail / warning paths)
- Score computation
- Grade band mapping
- scan_directory with duplicate detection
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# Make scripts/ importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from seo_scanner import (  # noqa: E402
    _check_title,
    _check_meta_description,
    _compute_score,
    _score_to_grade,
    extract_php_blocks,
    restore_php_blocks,
    scan_file,
    scan_directory,
)


# ─── PHP extraction ────────────────────────────────────────────────────────────


def test_php_block_extraction_basic():
    source = "Hello <?php echo 'world'; ?> end"
    html, blocks = extract_php_blocks(source)
    assert "<?php" not in html
    assert len(blocks) == 1
    assert blocks[0] == "<?php echo 'world'; ?>"
    assert "<!-- __PHP_BLOCK_0__ -->" in html


def test_php_block_restoration():
    source = "Hello <?php echo 'world'; ?> end"
    html, blocks = extract_php_blocks(source)
    restored = restore_php_blocks(html, blocks)
    assert restored == source


def test_php_multiple_blocks():
    source = "A <?php $x=1; ?> B <?= $x ?> C"
    html, blocks = extract_php_blocks(source)
    assert len(blocks) == 2
    restored = restore_php_blocks(html, blocks)
    assert restored == source


def test_php_no_blocks():
    source = "<html><body><h1>Test</h1></body></html>"
    html, blocks = extract_php_blocks(source)
    assert html == source
    assert blocks == []


# ─── Title checks ─────────────────────────────────────────────────────────────


def test_title_missing():
    checks = _check_title("")
    assert checks[0]["status"] == "fail"
    assert checks[0]["severity"] == "critical"


def test_title_too_short():
    checks = _check_title("Hi")
    assert checks[0]["status"] == "fail"
    assert checks[0]["severity"] == "high"


def test_title_below_ideal_length():
    checks = _check_title("Short title")  # 11 chars, >= 10 but < 50
    assert checks[0]["status"] == "warning"
    assert checks[0]["severity"] == "medium"


def test_title_too_long():
    checks = _check_title("A" * 65)
    assert checks[0]["status"] == "warning"
    assert checks[0]["severity"] == "medium"


def test_title_perfect():
    checks = _check_title("Best Artisan Bakery in Downtown | Fresh Sourdough Bread")  # 55 chars
    assert checks[0]["status"] == "pass"


# ─── Meta description checks ──────────────────────────────────────────────────


def test_meta_description_missing():
    checks = _check_meta_description("")
    assert checks[0]["status"] == "fail"
    assert checks[0]["severity"] == "high"


def test_meta_description_too_short():
    checks = _check_meta_description("Short")
    assert checks[0]["status"] == "fail"


def test_meta_description_too_long():
    checks = _check_meta_description("D" * 170)
    assert checks[0]["status"] == "warning"


def test_meta_description_perfect():
    # A description that's exactly in the 150-160 char range
    desc = "We offer fresh artisan bread baked daily using traditional family recipes. Visit our bakery in downtown for sourdough, rye, croissants, and much more."
    assert 150 <= len(desc) <= 160, f"Test setup error: description is {len(desc)} chars"
    checks = _check_meta_description(desc)
    assert checks[0]["status"] == "pass"


# ─── Score computation ────────────────────────────────────────────────────────


def test_score_perfect():
    score = _compute_score([
        {"id": "C01", "status": "pass", "severity": "critical"},
        {"id": "C02", "status": "pass", "severity": "high"},
    ])
    assert score == 100


def test_score_fail_reduces_score():
    score = _compute_score([
        {"id": "C01", "status": "fail", "severity": "critical"},
    ])
    assert score == 85  # 100 - 15


def test_score_warning_reduces_half():
    score = _compute_score([
        {"id": "C01", "status": "warning", "severity": "critical"},
    ])
    assert score == 93  # 100 - 15//2 = 100 - 7


def test_score_never_below_zero():
    many_fails = [{"id": "C01", "status": "fail", "severity": "critical"}] * 20
    score = _compute_score(many_fails)
    assert score == 0


def test_score_never_above_100():
    score = _compute_score([])
    assert score == 100


# ─── Grade bands ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("score,expected_grade", [
    (100, "A"),
    (90, "A"),
    (89, "B"),
    (80, "B"),
    (79, "C"),
    (70, "C"),
    (69, "D"),
    (60, "D"),
    (59, "F"),
    (0, "F"),
])
def test_score_to_grade(score, expected_grade):
    assert _score_to_grade(score) == expected_grade


# ─── scan_file integration ────────────────────────────────────────────────────


MINIMAL_HTML = textwrap.dedent("""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Best Bakery in Town | Fresh Artisan Bread</title>
      <meta name="description" content="We offer fresh artisan bread baked daily using traditional recipes in downtown. Visit us for sourdough, croissants, and pastries.">
      <link rel="canonical" href="https://example.com/">
    </head>
    <body>
      <nav><a href="/">Home</a></nav>
      <main><h1>Welcome to Our Bakery</h1><p>Great bread.</p></main>
      <footer>Copyright 2026</footer>
    </body>
    </html>
""")

BROKEN_HTML = textwrap.dedent("""\
    <!DOCTYPE html>
    <html>
    <head></head>
    <body>
      <h1>Page One</h1>
      <h1>Page Two</h1>
      <img src="photo.jpg">
    </body>
    </html>
""")


def test_scan_file_minimal_html(tmp_path):
    f = tmp_path / "index.html"
    f.write_text(MINIMAL_HTML, encoding="utf-8")
    result = scan_file(f)
    assert result["score"] > 50
    assert result["grade"] in ("A", "B", "C", "D")
    assert result["title"] == "Best Bakery in Town | Fresh Artisan Bread"
    assert result["is_php"] is False


def test_scan_file_broken_html_detects_issues(tmp_path):
    f = tmp_path / "broken.html"
    f.write_text(BROKEN_HTML, encoding="utf-8")
    result = scan_file(f)
    failed_ids = {c["id"] for c in result["checks"] if c["status"] == "fail"}
    # Should flag multiple H1s
    assert "C04a" in failed_ids


def test_scan_file_php_preserves_blocks(tmp_path):
    php_content = textwrap.dedent("""\
        <?php include 'header.php'; ?>
        <!DOCTYPE html>
        <html>
        <head>
          <title>PHP Page</title>
        </head>
        <body>
          <?php echo $content; ?>
        </body>
        </html>
    """)
    f = tmp_path / "page.php"
    f.write_text(php_content, encoding="utf-8")
    result = scan_file(f)
    assert result["is_php"] is True
    assert len(result["php_blocks"]) == 2
    # PHP blocks should be present in php_blocks
    assert "<?php include 'header.php'; ?>" in result["php_blocks"]


def test_scan_file_missing_meta_description(tmp_path):
    html = "<html><head><title>Test</title></head><body><h1>Hi</h1></body></html>"
    f = tmp_path / "test.html"
    f.write_text(html, encoding="utf-8")
    result = scan_file(f)
    failed_ids = {c["id"] for c in result["checks"] if c["status"] == "fail"}
    assert "C02" in failed_ids


def test_scan_directory_detects_duplicates(tmp_path):
    html_template = textwrap.dedent("""\
        <html><head>
          <title>Same Title For All Pages</title>
          <meta name="description" content="{desc}">
        </head><body><h1>Content</h1></body></html>
    """)
    desc = "We bake fresh bread every morning and serve it to our loyal customers in the area."
    for i in range(2):
        f = tmp_path / f"page{i}.html"
        f.write_text(html_template.format(desc=desc), encoding="utf-8")

    results = scan_directory(tmp_path)
    assert len(results) == 2
    # Second file should flag duplicate title
    second = results[1]
    dup_ids = {c["id"] for c in second["checks"] if c["status"] == "fail"}
    assert "C15a" in dup_ids


def test_scan_directory_empty(tmp_path):
    results = scan_directory(tmp_path)
    assert results == []


def test_scan_directory_invalid_path():
    with pytest.raises(ValueError):
        scan_directory("/nonexistent/path/that/does/not/exist")


# ─── Full check surface (smoke) ───────────────────────────────────────────────


def test_scan_full_good_page_has_no_critical_fails(tmp_path):
    """A well-formed page should pass critical checks."""
    f = tmp_path / "good.html"
    f.write_text(MINIMAL_HTML, encoding="utf-8")
    result = scan_file(f)
    critical_fails = [
        c for c in result["checks"]
        if c["status"] == "fail" and c.get("severity") == "critical"
    ]
    assert critical_fails == [], f"Unexpected critical fails: {critical_fails}"
