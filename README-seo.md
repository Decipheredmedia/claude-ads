# SEO Skill for claude-ads — Installation & Configuration Guide

> **Powered by Venice AI** · Works with Claude Code, Codex CLI, Cursor, Windsurf, Gemini CLI, Goose

The SEO skill extends [claude-ads](https://github.com/Decipheredmedia/claude-ads) with
comprehensive on-page and technical SEO analysis for `.html` and `.php` website files.
It auto-fixes issues in place, generates JSON + Markdown reports, and uses
**Venice AI** (OpenAI-compatible) for AI-assisted improvements.

---

## Table of Contents

1. [Requirements](#requirements)
2. [Quick Start](#quick-start)
3. [Windows 10/11 Installation](#windows-1011-installation)
4. [Ubuntu 20.04 Installation](#ubuntu-2004-installation)
5. [Venice AI Configuration](#venice-ai-configuration)
6. [Usage Examples](#usage-examples)
7. [What Gets Checked & Fixed](#what-gets-checked--fixed)
8. [Uninstall](#uninstall)
9. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.9+ | For SEO scanner/fixer scripts |
| **pip** | any | Python package manager |
| **Git** | any | Required by the installer |
| **Venice AI account** | — | [Get API key](https://venice.ai/settings/api) — free tier available |
| **PHP CLI** _(optional)_ | 7.4+ | Enables `php -l` syntax validation for `.php` files |
| **beautifulsoup4** | 4.12+ | Installed automatically by `pip install -r requirements.txt` |

### Supported host CLIs

| Host | Status |
|------|--------|
| Claude Code | ✅ Verified |
| OpenAI Codex CLI | ⚠ Experimental |
| Cursor IDE | ⚠ Experimental |
| Windsurf IDE | ⚠ Experimental |
| Gemini CLI | ⚠ Experimental |
| Goose CLI | ⚠ Experimental |

---

## Quick Start

```bash
# Install (Claude Code, default target)
bash <(curl -fsSL https://raw.githubusercontent.com/Decipheredmedia/claude-ads/main/install.sh) \
  --venice-api-key=vn-your-key-here

# Then in Claude Code / your host CLI:
/seo scan ./public_html
/seo audit
/seo fix --dry-run
/seo fix
```

---

## Windows 10/11 Installation

### Step 1 — Prerequisites

Open **PowerShell as Administrator** and ensure you have Git and Python:

```powershell
# Check Git
git --version

# Check Python
python --version   # or python3 --version

# If not installed, install via winget:
winget install Git.Git
winget install Python.Python.3.12
```

### Step 2 — Set execution policy (if not already done)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 3 — Install the skill

**One-liner (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/Decipheredmedia/claude-ads/main/install.ps1 | iex
```

Or download and run with options:

```powershell
# Download installer
Invoke-WebRequest -Uri https://raw.githubusercontent.com/Decipheredmedia/claude-ads/main/install.ps1 `
  -OutFile install.ps1

# Install for Claude Code with Venice AI key
.\install.ps1 -VeniceApiKey "vn-your-key-here"

# Install for a different host
.\install.ps1 -Target codex -VeniceApiKey "vn-your-key-here"
```

### Step 4 — Set `VENICE_API_KEY` as a persistent environment variable

```powershell
# Persist across sessions (requires new terminal to take effect)
[System.Environment]::SetEnvironmentVariable("VENICE_API_KEY", "vn-your-key-here", "User")

# Or use setx (requires new terminal to take effect)
setx VENICE_API_KEY "vn-your-key-here"
```

### Step 5 — Edit the config file (optional)

The installer writes a config file to:
```
%USERPROFILE%\.claude\skills\seo\config.json
```

Open with Notepad:
```powershell
notepad "$env:USERPROFILE\.claude\skills\seo\config.json"
```

Full example config:
```json
{
  "api_key": "vn-your-key-here",
  "model": "llama-3.3-70b",
  "base_url": "https://api.venice.ai/api/v1",
  "temperature": 0.3,
  "max_tokens": 512,
  "provider": "venice"
}
```

Available Venice models: `llama-3.3-70b`, `venice-uncensored`, `mistral-31-24b` (check [venice.ai/models](https://venice.ai/models) for current list).

### Step 6 — Install Python dependencies

```powershell
pip install -r "$env:USERPROFILE\.claude\skills\ads\requirements.txt"
```

### Step 7 — (Optional) Install PHP CLI for .php file validation

Download PHP for Windows from [windows.php.net](https://windows.php.net/download/) and add to PATH:
```powershell
# Add PHP to PATH (adjust path as needed)
$env:Path += ";C:\php"
[System.Environment]::SetEnvironmentVariable("Path", $env:Path, "User")
```

### Step 8 — Verify installation

```powershell
# In Claude Code or your host CLI:
# /seo scan ./path/to/your/website
```

Or smoke-test the Venice AI connection:
```powershell
python "$env:USERPROFILE\.claude\skills\ads\scripts\venice_provider.py" `
  --prompt "Write a 55-char SEO title for a bakery website"
```

---

## Ubuntu 20.04 Installation

### Step 1 — Install prerequisites

```bash
sudo apt update
sudo apt install -y git python3 python3-pip

# Optional: PHP CLI for .php file syntax validation
sudo apt install -y php-cli

# Verify
git --version && python3 --version
```

### Step 2 — Install the skill

**One-liner:**

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Decipheredmedia/claude-ads/main/install.sh) \
  --venice-api-key=vn-your-key-here
```

Or with target override:

```bash
# Download and run
curl -fsSL https://raw.githubusercontent.com/Decipheredmedia/claude-ads/main/install.sh \
  -o /tmp/install-claude-ads.sh
bash /tmp/install-claude-ads.sh --target=claude --venice-api-key=vn-your-key-here
```

For other host CLIs:
```bash
bash install.sh --target=codex   --venice-api-key=vn-your-key-here
bash install.sh --target=cursor  --venice-api-key=vn-your-key-here
bash install.sh --target=goose   --venice-api-key=vn-your-key-here
```

### Step 3 — Export `VENICE_API_KEY`

Add to `~/.bashrc` or `~/.profile`:

```bash
echo 'export VENICE_API_KEY="vn-your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### Step 4 — Edit the config file (optional)

The config file is at:
```
~/.claude/skills/seo/config.json
```

```bash
nano ~/.claude/skills/seo/config.json
```

Full example:
```json
{
  "api_key": "vn-your-key-here",
  "model": "llama-3.3-70b",
  "base_url": "https://api.venice.ai/api/v1",
  "temperature": 0.3,
  "max_tokens": 512,
  "provider": "venice"
}
```

### Step 5 — Install Python dependencies

```bash
pip3 install -r ~/.claude/skills/ads/requirements.txt
# If you get an externally-managed-environment error on Ubuntu 22.04+:
pip3 install --break-system-packages -r ~/.claude/skills/ads/requirements.txt
```

### Step 6 — Verify installation

Smoke-test Venice AI connection:
```bash
python3 ~/.claude/skills/ads/scripts/venice_provider.py \
  --prompt "Write a 55-char SEO title for a bakery website"
```

Smoke-test SEO scanner:
```bash
python3 ~/.claude/skills/ads/scripts/seo_scanner.py ./my-website/
```

Expected output:
```
============================================================
  ./my-website/index.html  |  Score: 72/100  (C)
============================================================
  ✓ [C01] Title length OK (55 chars)
  ✗ [C02] Missing meta description
      → Add a <meta name='description'> between 150–160 characters.
  ...
```

---

## Venice AI Configuration

### Configuration priority

The SEO skill loads configuration in this order (highest priority first):

1. `VENICE_API_KEY` environment variable (for the key)
2. `~/.claude/skills/seo/config.json` (full config)
3. Built-in defaults

### Config file schema

```json
{
  "api_key": "vn-your-key-here",
  "model": "llama-3.3-70b",
  "base_url": "https://api.venice.ai/api/v1",
  "temperature": 0.3,
  "max_tokens": 512,
  "provider": "venice"
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `api_key` | `""` | Venice AI API key |
| `model` | `llama-3.3-70b` | Venice model name |
| `base_url` | `https://api.venice.ai/api/v1` | API endpoint |
| `temperature` | `0.3` | Sampling temperature (0–2) |
| `max_tokens` | `512` | Max tokens per generation |
| `provider` | `venice` | Set to `mock` for offline/CI use |

### What works without an API key

All structural checks run without Venice AI:
- Viewport & charset detection (C03)
- Heading structure (C04)
- Canonical tag (C06)
- Open Graph / Twitter Card injection (C07/C08)
- Lazy loading (C12)
- Semantic HTML checks (C13)
- Render-blocking detection (C14)
- Duplicate content detection (C15)

**Requires Venice AI:**
- Title generation/rewriting (C01)
- Meta description generation/rewriting (C02)
- Alt text generation (C05)
- JSON-LD schema generation (C09)

---

## Usage Examples

### Scan (read-only, no changes)

```
/seo scan ./public_html
/seo scan ./index.html
```

### Audit (scan + JSON + Markdown report)

```
/seo audit
/seo audit ./public_html
```

Outputs:
- `seo-report.json` — machine-readable
- `seo-report.md` — client-deliverable

### Fix — preview first

```
/seo fix --dry-run
/seo fix ./public_html --dry-run
```

Shows a unified diff of all proposed changes. Nothing is written to disk.

### Fix — apply

```
/seo fix
/seo fix ./public_html
/seo fix ./index.html
```

- Creates `.bak` backup before each file is overwritten
- For `.php` files: runs `php -l` after fix; restores `.bak` on syntax error
- Generates `robots.txt` and `sitemap.xml` at project root if missing

### Fix without backups

```
/seo fix --no-backup
```

---

## What Gets Checked & Fixed

| Check | ID | Severity | Auto-fix |
|-------|----|----------|----------|
| Title presence & length (50–60 chars) | C01 | Critical/High | ✅ (AI) |
| Meta description presence & length (150–160 chars) | C02 | High | ✅ (AI) |
| Viewport meta tag | C03a | High | ✅ |
| Charset declaration | C03b | Medium | ✅ |
| Single H1, no skipped heading levels | C04 | High | ❌ manual |
| Image alt attributes | C05 | High | ✅ (AI) |
| Canonical link tag | C06 | High | ✅ |
| Open Graph tags (og:title, og:description, og:url, og:type) | C07 | Medium | ✅ |
| Twitter Card tag | C08 | Low | ✅ |
| JSON-LD structured data | C09 | High | ✅ (AI) |
| Robots meta tag | C10 | Medium | ❌ manual |
| Image width/height (CLS prevention) | C11 | Medium | ❌ manual |
| Lazy loading (loading="lazy") | C12 | Low | ✅ |
| Semantic HTML landmarks (nav, main, footer) | C13 | Medium | ❌ manual |
| Render-blocking scripts/styles in head | C14 | Low | ❌ manual |
| Duplicate title/description across files | C15 | High | ❌ manual |
| hreflang tags | C16 | Info | ❌ manual |

**Project-level files generated if missing:**
- `robots.txt` — with `Sitemap:` directive
- `sitemap.xml` — with URLs for all scanned HTML/PHP files

---

## Uninstall

### Ubuntu / macOS

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Decipheredmedia/claude-ads/main/uninstall.sh)
# Or for a specific target:
bash uninstall.sh --target=codex
```

This removes:
- `~/.claude/skills/ads/` (ads orchestrator + scripts)
- `~/.claude/skills/seo/` (seo orchestrator + config)
- `~/.claude/skills/ads-*/` (all ads sub-skills)
- `~/.claude/skills/seo-*/` (all seo sub-skills)
- Bundled agent `.md` files from `~/.claude/agents/`

### Windows

```powershell
.\uninstall.ps1
# Or for a specific target:
.\uninstall.ps1 -Target codex
```

---

## Troubleshooting & FAQ

### Venice API errors

**`RuntimeError: Venice API key not configured`**

Set your key:
```bash
# Linux/macOS
export VENICE_API_KEY="vn-your-key-here"

# Windows PowerShell
setx VENICE_API_KEY "vn-your-key-here"
```
Or add `"api_key": "vn-your-key-here"` to the config file.

**`RuntimeError: Venice API unavailable after 4 retries`**

Venice API may be temporarily unavailable. The skill retries with exponential
back-off (1→2→4→8 seconds). If it persists:
- Check [status.venice.ai](https://venice.ai) for outages
- Verify your API key is valid at [venice.ai/settings/api](https://venice.ai/settings/api)
- Structural SEO fixes still run without AI — only generative fixes are skipped

**`RuntimeError: Venice API error 401`**

Invalid API key. Get a valid key at [venice.ai/settings/api](https://venice.ai/settings/api).

---

### PHP validation failures

**`PHP syntax validation failed after fix: File restored.`**

The fixer detected that a PHP file became syntactically invalid after applying fixes.
The original file was restored from the `.bak` backup. To investigate:

```bash
# Check what the fixer would have done
/seo fix ./problem-file.php --dry-run

# Validate manually
php -l ./problem-file.php
```

If PHP CLI is not installed, syntax validation is skipped (fixes are applied without
checking). Install PHP CLI to enable validation:
```bash
# Ubuntu
sudo apt install -y php-cli

# macOS
brew install php
```

---

### Ubuntu permission issues

**`Permission denied: ~/.claude/skills/`**

```bash
chmod u+rw -R ~/.claude/skills/
```

**`externally-managed-environment` pip error (Ubuntu 22.04+)**

```bash
pip3 install --break-system-packages -r ~/.claude/skills/ads/requirements.txt
```

Or use a virtual environment:
```bash
python3 -m venv ~/.claude/skills/ads/venv
source ~/.claude/skills/ads/venv/bin/activate
pip install -r ~/.claude/skills/ads/requirements.txt
```

---

### Windows PowerShell execution policy

**`cannot be loaded because running scripts is disabled`**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Or run the installer directly:
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -VeniceApiKey "vn-your-key"
```

---

### `beautifulsoup4` not found

If the SEO scanner fails with `ModuleNotFoundError: No module named 'bs4'`:

```bash
pip3 install beautifulsoup4
```

The scanner falls back to a simplified stdlib parser if `bs4` is not available.
The stdlib fallback covers the most critical checks (title, description, viewport,
H1, canonical) but skips some advanced checks (OG tags, JSON-LD validation, etc.).
Install `beautifulsoup4` for full coverage.

---

### SEO scanner finds no files

If `/seo scan ./my-site` reports `0 files scanned`:
- The path must exist and contain `.html` or `.php` files
- The scanner checks recursively — nested directories are included
- Verify: `find ./my-site -name "*.html" -o -name "*.php" | head`

---

### Running tests (CI / development)

Tests do **not** require a live `VENICE_API_KEY` — all Venice calls are mocked:

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

To add a real Venice AI key for manual integration tests:
```bash
VENICE_API_KEY=vn-your-key python -m pytest tests/ -v -k "integration"
```

---

## Manual follow-up after install

1. **Add `VENICE_API_KEY` to your CI/CD secrets** if you want AI-assisted fixes in automated pipelines
2. **Set `og:image`** manually — the fixer cannot determine your page's representative image URL automatically
3. **Review `noindex` warnings** — the fixer never removes `noindex` tags automatically; verify they are intentional
4. **Set canonical href values** — the fixer injects `<link rel="canonical" href="">` with the `--site-url` value; update per-page URLs for accuracy
5. **Review duplicate title/description warnings** — these require editorial judgement to create unique, keyword-rich variants

---

*Part of [claude-ads](https://github.com/Decipheredmedia/claude-ads) — the AI-powered advertising & SEO skill suite for Claude Code and other host CLIs.*
