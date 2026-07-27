#!/usr/bin/env bash
set -euo pipefail

# Claude Ads Installer
# Wraps everything in main() to prevent partial execution on network failure.
#
# Default target is Claude Code. Cross-host targets are EXPERIMENTAL — they
# install the same skill artifacts under each host's expected directory, but
# the host's own runtime conventions may differ. Pin path overrides via
# --skill-dir / --agent-dir if the auto-detected paths are wrong for your
# install.
#
# Usage:
#   bash install.sh                              # default: --target=claude
#   bash install.sh --target=codex
#   bash install.sh --target=cursor
#   bash install.sh --target=windsurf
#   bash install.sh --target=gemini
#   bash install.sh --target=goose
#   bash install.sh --skill-dir=/custom/path     # override the target's default path
#
# All target keys are validated against a strict whitelist (no shell injection
# possible via --target=...). Custom --skill-dir paths are validated against
# `;&|$()<>` ` `, leading dashes, `..` segments, and UNC-style paths.

REPO_URL="https://github.com/AI-Marketing-Hub/claude-ads"
DECIPHERED_REPO_URL="https://github.com/Decipheredmedia/claude-ads"

# ─────────────────────────────────────────────────────────────────────────────
# Target whitelist + path mapping
# ─────────────────────────────────────────────────────────────────────────────
#
# Keep this table the SINGLE source of truth. When a new host CLI is added,
# update only this case statement plus the help text.
#
# claude    — Claude Code (VERIFIED, GA)
# codex     — OpenAI Codex CLI (EXPERIMENTAL, verify before relying on)
# cursor    — Cursor IDE (EXPERIMENTAL, extension model differs)
# windsurf  — Windsurf IDE (EXPERIMENTAL)
# gemini    — Gemini CLI (EXPERIMENTAL)
# goose     — Goose CLI (EXPERIMENTAL)

resolve_target_paths() {
    local target="$1"
    case "$target" in
        claude)
            SKILL_BASE="${HOME}/.claude/skills"
            AGENT_DIR="${HOME}/.claude/agents"
            ALLOW_PIP=1
            HOST_LABEL="Claude Code"
            ;;
        codex)
            SKILL_BASE="${HOME}/.codex/skills"
            AGENT_DIR="${HOME}/.codex/agents"
            ALLOW_PIP=1
            HOST_LABEL="OpenAI Codex CLI"
            ;;
        cursor)
            SKILL_BASE="${HOME}/.cursor/extensions/claude-ads/skills"
            AGENT_DIR="${HOME}/.cursor/extensions/claude-ads/agents"
            ALLOW_PIP=0
            HOST_LABEL="Cursor IDE"
            ;;
        windsurf)
            SKILL_BASE="${HOME}/.windsurf/skills"
            AGENT_DIR="${HOME}/.windsurf/agents"
            ALLOW_PIP=0
            HOST_LABEL="Windsurf IDE"
            ;;
        gemini)
            SKILL_BASE="${HOME}/.gemini/extensions/claude-ads/skills"
            AGENT_DIR="${HOME}/.gemini/extensions/claude-ads/agents"
            ALLOW_PIP=0
            HOST_LABEL="Gemini CLI"
            ;;
        goose)
            SKILL_BASE="${HOME}/.config/goose/skills"
            AGENT_DIR="${HOME}/.config/goose/agents"
            ALLOW_PIP=0
            HOST_LABEL="Goose CLI"
            ;;
        *)
            return 1
            ;;
    esac
    return 0
}

# Reject anything that could be path-injection, flag-confusion, or
# directory-traversal. Called before --skill-dir / --agent-dir values are
# used in `mkdir`, `cp`, or `rm`.
validate_install_path() {
    local path="$1"
    # Reject empty
    [ -z "$path" ] && return 1
    # Reject leading dash (flag confusion: `--skill-dir=-rf`)
    case "$path" in -*) return 1 ;; esac
    # Reject shell metacharacters
    case "$path" in *[\;\&\|\$\(\)\<\>\`\\]*) return 1 ;; esac
    # Reject parent-traversal segments
    case "$path" in *..*) return 1 ;; esac
    # Reject UNC-style paths (Windows-ish input slipping through bash)
    case "$path" in //*|\\\\*) return 1 ;; esac
    return 0
}

print_help() {
    cat <<EOF
Claude Ads + SEO Skill Installer

Usage:
  bash install.sh [--target=<host>] [--skill-dir=<path>] [--agent-dir=<path>]
                  [--venice-api-key=<key>] [--skip-seo] [--skip-ads]

Targets (default: claude):
  claude     Claude Code (verified)
  codex      OpenAI Codex CLI (experimental)
  cursor     Cursor IDE (experimental)
  windsurf   Windsurf IDE (experimental)
  gemini     Gemini CLI (experimental)
  goose      Goose CLI (experimental)

Overrides:
  --skill-dir=<path>         Override the target's default skill install root
  --agent-dir=<path>         Override the target's default agent install root
  --venice-api-key=<key>     Write Venice AI API key to the SEO config file
  --skip-seo                 Skip SEO skill installation
  --skip-ads                 Skip Ads skill installation

Examples:
  bash install.sh
  bash install.sh --target=codex
  bash install.sh --target=claude --venice-api-key=vn-your-key-here
  bash install.sh --target=claude --skill-dir=~/custom/skills

EOF
}

main() {
    # Defaults
    local TARGET="claude"
    local SKILL_DIR_OVERRIDE=""
    local AGENT_DIR_OVERRIDE=""
    local VENICE_API_KEY=""
    local SKIP_SEO=0
    local SKIP_ADS=0

    # Parse args
    while [ $# -gt 0 ]; do
        case "$1" in
            --target=*)
                TARGET="${1#*=}"
                ;;
            --target)
                shift
                [ $# -eq 0 ] && { echo "✗ --target requires a value" >&2; exit 1; }
                TARGET="$1"
                ;;
            --skill-dir=*)
                SKILL_DIR_OVERRIDE="${1#*=}"
                ;;
            --skill-dir)
                shift
                [ $# -eq 0 ] && { echo "✗ --skill-dir requires a value" >&2; exit 1; }
                SKILL_DIR_OVERRIDE="$1"
                ;;
            --agent-dir=*)
                AGENT_DIR_OVERRIDE="${1#*=}"
                ;;
            --agent-dir)
                shift
                [ $# -eq 0 ] && { echo "✗ --agent-dir requires a value" >&2; exit 1; }
                AGENT_DIR_OVERRIDE="$1"
                ;;
            --venice-api-key=*)
                VENICE_API_KEY="${1#*=}"
                ;;
            --venice-api-key)
                shift
                [ $# -eq 0 ] && { echo "✗ --venice-api-key requires a value" >&2; exit 1; }
                VENICE_API_KEY="$1"
                ;;
            --skip-seo)
                SKIP_SEO=1
                ;;
            --skip-ads)
                SKIP_ADS=1
                ;;
            --help|-h)
                print_help
                exit 0
                ;;
            *)
                echo "✗ Unknown argument: $1" >&2
                echo "  Run: bash install.sh --help" >&2
                exit 1
                ;;
        esac
        shift
    done

    # Resolve target paths (rejects unknown targets via whitelist)
    if ! resolve_target_paths "$TARGET"; then
        echo "✗ Unknown target: $TARGET" >&2
        echo "  Valid targets: claude, codex, cursor, windsurf, gemini, goose" >&2
        echo "  Run: bash install.sh --help" >&2
        exit 1
    fi

    # Apply path overrides (with strict validation)
    if [ -n "$SKILL_DIR_OVERRIDE" ]; then
        validate_install_path "$SKILL_DIR_OVERRIDE" || {
            echo "✗ Invalid --skill-dir: contains forbidden characters or traversal" >&2
            exit 1
        }
        SKILL_BASE="$SKILL_DIR_OVERRIDE"
    fi
    if [ -n "$AGENT_DIR_OVERRIDE" ]; then
        validate_install_path "$AGENT_DIR_OVERRIDE" || {
            echo "✗ Invalid --agent-dir: contains forbidden characters or traversal" >&2
            exit 1
        }
        AGENT_DIR="$AGENT_DIR_OVERRIDE"
    fi

    local SKILL_DIR="${SKILL_BASE}/ads"
    local SEO_SKILL_DIR="${SKILL_BASE}/seo"

    echo "════════════════════════════════════════════"
    echo "║   Claude Ads + SEO Skill - Installer    ║"
    echo "║   Target: ${HOST_LABEL}"
    echo "════════════════════════════════════════════"
    echo ""

    # Check prerequisites
    command -v git >/dev/null 2>&1 || { echo "✗ Git is required but not installed."; exit 1; }
    echo "✓ Git detected"

    # Create directories
    if [ "${SKIP_ADS}" = "0" ]; then
        mkdir -p "${SKILL_DIR}/references"
    fi
    if [ "${SKIP_SEO}" = "0" ]; then
        mkdir -p "${SEO_SKILL_DIR}/references"
    fi
    mkdir -p "${AGENT_DIR}"

    # Clone or update
    TEMP_DIR=$(mktemp -d)
    trap 'rm -rf "${TEMP_DIR}"' EXIT

    echo "↓ Downloading claude-ads..."
    git clone --depth 1 "${DECIPHERED_REPO_URL}" "${TEMP_DIR}/claude-ads" 2>/dev/null \
        || git clone --depth 1 "${REPO_URL}" "${TEMP_DIR}/claude-ads" 2>/dev/null

    # ── Ads skill ────────────────────────────────────────────────────────────
    if [ "${SKIP_ADS}" = "0" ]; then
        echo "→ Installing Ads skill files..."
        cp "${TEMP_DIR}/claude-ads/ads/SKILL.md" "${SKILL_DIR}/SKILL.md"
        if [ -d "${TEMP_DIR}/claude-ads/ads/references" ]; then
            cp "${TEMP_DIR}/claude-ads/ads/references/"*.md "${SKILL_DIR}/references/"
        fi
    fi

    # ── SEO skill ────────────────────────────────────────────────────────────
    if [ "${SKIP_SEO}" = "0" ]; then
        echo "→ Installing SEO skill files..."
        cp "${TEMP_DIR}/claude-ads/seo/SKILL.md" "${SEO_SKILL_DIR}/SKILL.md"
        if [ -d "${TEMP_DIR}/claude-ads/seo/references" ]; then
            cp "${TEMP_DIR}/claude-ads/seo/references/"*.md "${SEO_SKILL_DIR}/references/"
        fi
    fi

    # ── Sub-skills (ads-* and seo-*) ─────────────────────────────────────────
    echo "→ Installing sub-skills..."
    for skill_dir in "${TEMP_DIR}/claude-ads/skills"/*/; do
        skill_name=$(basename "${skill_dir}")
        # Respect --skip-ads / --skip-seo flags
        if [ "${SKIP_ADS}" = "1" ] && echo "${skill_name}" | grep -q "^ads-"; then
            continue
        fi
        if [ "${SKIP_SEO}" = "1" ] && echo "${skill_name}" | grep -q "^seo"; then
            continue
        fi
        target="${SKILL_BASE}/${skill_name}"
        mkdir -p "${target}"
        cp "${skill_dir}SKILL.md" "${target}/SKILL.md"

        # Copy assets (industry templates) if they exist
        if [ -d "${skill_dir}assets" ]; then
            mkdir -p "${target}/assets"
            cp "${skill_dir}assets/"*.md "${target}/assets/"
        fi
    done

    # ── Agents ────────────────────────────────────────────────────────────────
    echo "→ Installing subagents..."
    cp "${TEMP_DIR}/claude-ads/agents/"*.md "${AGENT_DIR}/" 2>/dev/null || true

    # ── Python scripts ────────────────────────────────────────────────────────
    SCRIPTS_DIR="${SKILL_DIR}/scripts"
    if [ -d "${TEMP_DIR}/claude-ads/scripts" ]; then
        echo "→ Installing Python scripts (ads + SEO)..."
        mkdir -p "${SCRIPTS_DIR}"
        cp "${TEMP_DIR}/claude-ads/scripts/"*.py "${SCRIPTS_DIR}/"
        cp "${TEMP_DIR}/claude-ads/requirements.txt" "${SKILL_DIR}/requirements.txt"
    fi

    # ── Python dependencies ──────────────────────────────────────────────────
    echo ""
    if [ "${ALLOW_PIP}" = "1" ]; then
        echo "→ Installing Python dependencies..."
        if command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
            PIP_CMD="pip3"
            command -v pip3 >/dev/null 2>&1 || PIP_CMD="pip"
            ${PIP_CMD} install -q -r "${SKILL_DIR}/requirements.txt" 2>/dev/null \
                || { echo "  ⚠ Standard pip install failed, trying --break-system-packages..." >&2; \
                     ${PIP_CMD} install --break-system-packages -q -r "${SKILL_DIR}/requirements.txt" 2>/dev/null; } \
                && echo "  ✓ Python dependencies installed" \
                || echo "  ⚠ pip install failed. Run manually: pip3 install -r ${SKILL_DIR}/requirements.txt"
        else
            echo "  ⚠ pip not found. Install deps manually: pip3 install -r ${SKILL_DIR}/requirements.txt"
        fi
    else
        echo "ℹ Skipping Python dependencies — ${HOST_LABEL} host runtime may not execute Python skills directly."
        echo "  If you need SEO scanning / fixing, install manually:"
        echo "    pip3 install -r ${SKILL_DIR}/requirements.txt"
    fi

    # ── Venice AI configuration ───────────────────────────────────────────────
    echo ""
    if [ "${SKIP_SEO}" = "0" ]; then
        SEO_CONFIG_DIR="${SEO_SKILL_DIR}"
        SEO_CONFIG_FILE="${SEO_CONFIG_DIR}/config.json"
        mkdir -p "${SEO_CONFIG_DIR}"

        # Use provided key or check environment
        _VENICE_KEY="${VENICE_API_KEY:-${VENICE_API_KEY:-}}"
        if [ -z "${_VENICE_KEY}" ] && [ -n "${VENICE_API_KEY:-}" ]; then
            _VENICE_KEY="${VENICE_API_KEY}"
        fi

        if [ -n "${_VENICE_KEY}" ]; then
            cat > "${SEO_CONFIG_FILE}" <<VNCEOF
{
  "api_key": "${_VENICE_KEY}",
  "model": "llama-3.3-70b",
  "base_url": "https://api.venice.ai/api/v1",
  "temperature": 0.3,
  "max_tokens": 512,
  "provider": "venice"
}
VNCEOF
            echo "  ✓ Venice AI config written to: ${SEO_CONFIG_FILE}"
        else
            # Write placeholder config if not already present
            if [ ! -f "${SEO_CONFIG_FILE}" ]; then
                cat > "${SEO_CONFIG_FILE}" <<VNCEOF
{
  "api_key": "",
  "model": "llama-3.3-70b",
  "base_url": "https://api.venice.ai/api/v1",
  "temperature": 0.3,
  "max_tokens": 512,
  "provider": "venice"
}
VNCEOF
            fi
            echo "  ⚠ Venice AI API key not set."
            echo "    For AI-assisted SEO fixes (title, description, alt-text, schema):"
            echo "    Option 1: export VENICE_API_KEY=vn-your-key-here"
            echo "    Option 2: edit ${SEO_CONFIG_FILE}"
            echo "    Get your key at: https://venice.ai/settings/api"
            echo ""
            echo "    Structural SEO checks (viewport, canonical, OG tags, etc.) work without a key."
        fi
    fi

    # ── banana-claude check ───────────────────────────────────────────────────
    echo ""
    if [ "${SKIP_ADS}" = "0" ]; then
        if [ -d "${SKILL_BASE}/banana" ] || [ -f "${SKILL_BASE}/banana/SKILL.md" ]; then
            echo "  ✓ banana-claude detected (image generation ready)"
        else
            echo "  ⚠ banana-claude not installed. Image generation (/ads generate, /ads photoshoot) requires it."
            echo "    Install: curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/banana-claude/main/install.sh | bash"
            echo "    Then run: /banana setup (to configure API key)"
        fi
        echo ""
    fi

    echo "✓ Installation complete for ${HOST_LABEL}!"
    echo ""
    echo "  Installed to:"
    echo "    Skills: ${SKILL_BASE}"
    echo "    Agents: ${AGENT_DIR}"
    echo ""
    if [ "${SKIP_ADS}" = "0" ]; then
        echo "  Ads skill:"
        echo "    • 1 main skill (ads orchestrator)"
        echo "    • 22 sub-skills (platform + functional + creative)"
        echo "    • 10 agents (6 audit + 4 creative)"
        echo "    • 25 reference files"
        echo ""
    fi
    if [ "${SKIP_SEO}" = "0" ]; then
        echo "  SEO skill (Venice AI powered):"
        echo "    • 1 main skill (seo orchestrator)"
        echo "    • 3 sub-skills (seo-audit, seo-fix, seo-scan)"
        echo "    • Python scripts: seo_scanner.py, seo_fixer.py, seo_report.py, venice_provider.py"
        echo ""
    fi
    echo "Usage:"
    echo "  1. Start your host CLI"
    if [ "${SKIP_ADS}" = "0" ]; then
        echo "  2. Ads commands:   /ads audit"
        echo "                      /ads plan saas"
        echo "                      /ads google"
        echo ""
    fi
    if [ "${SKIP_SEO}" = "0" ]; then
        echo "  3. SEO commands:   /seo scan ./public_html"
        echo "                      /seo audit"
        echo "                      /seo fix --dry-run"
        echo "                      /seo fix"
        echo ""
    fi
    echo "To uninstall: bash uninstall.sh --target=${TARGET}"
}

main "$@"
