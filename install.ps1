#Requires -Version 5.1
<#
.SYNOPSIS
    Claude Ads + SEO Skill Installer for Windows (multi-host).
.DESCRIPTION
    Installs the Claude Ads skill, the SEO skill (Venice AI powered), sub-skills,
    agents, and reference files for Claude Code (default) or any of the supported
    experimental host CLIs.

    Targets:
      claude     Claude Code (verified)
      codex      OpenAI Codex CLI (experimental)
      cursor     Cursor IDE (experimental)
      windsurf   Windsurf IDE (experimental)
      gemini     Gemini CLI (experimental)
      goose      Goose CLI (experimental)
.PARAMETER Target
    Which host CLI to install for. Default: claude.
.PARAMETER SkillDir
    Override the target's default skill install root.
.PARAMETER AgentDir
    Override the target's default agent install root.
.PARAMETER VeniceApiKey
    Venice AI API key. Written to the SEO config file.
    Get yours at https://venice.ai/settings/api
.PARAMETER SkipSeo
    Skip SEO skill installation.
.PARAMETER SkipAds
    Skip Ads skill installation.
.EXAMPLE
    .\install.ps1
.EXAMPLE
    .\install.ps1 -Target codex
.EXAMPLE
    .\install.ps1 -VeniceApiKey "vn-your-key-here"
.EXAMPLE
    .\install.ps1 -SkillDir C:\Custom\Skills
#>

param(
    [ValidateSet('claude','codex','cursor','windsurf','gemini','goose')]
    [string]$Target = 'claude',
    [string]$SkillDir = '',
    [string]$AgentDir = '',
    [string]$VeniceApiKey = '',
    [switch]$SkipSeo,
    [switch]$SkipAds
)

$ErrorActionPreference = "Stop"

function Resolve-TargetPaths {
    param([string]$T)
    switch ($T) {
        'claude' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".claude\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".claude\agents"
                AllowPip  = $true
                Label     = "Claude Code"
            }
        }
        'codex' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".codex\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".codex\agents"
                AllowPip  = $true
                Label     = "OpenAI Codex CLI"
            }
        }
        'cursor' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".cursor\extensions\claude-ads\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".cursor\extensions\claude-ads\agents"
                AllowPip  = $false
                Label     = "Cursor IDE"
            }
        }
        'windsurf' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".windsurf\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".windsurf\agents"
                AllowPip  = $false
                Label     = "Windsurf IDE"
            }
        }
        'gemini' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".gemini\extensions\claude-ads\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".gemini\extensions\claude-ads\agents"
                AllowPip  = $false
                Label     = "Gemini CLI"
            }
        }
        'goose' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".config\goose\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".config\goose\agents"
                AllowPip  = $false
                Label     = "Goose CLI"
            }
        }
        default {
            throw "Unknown target: $T"
        }
    }
}

function Test-InstallPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if ($Path -match '[\;\&\|\$\(\)\<\>\`]') { return $false }
    if ($Path -match '\.\.') { return $false }
    if ($Path -match '^[-]') { return $false }
    if ($Path -match '^(\\\\|//)') { return $false }   # UNC paths
    return $true
}

function Main {
    $paths = Resolve-TargetPaths -T $Target
    $SkillBase = $paths.SkillBase
    $AgentDirResolved = $paths.AgentDir
    $AllowPip = $paths.AllowPip
    $HostLabel = $paths.Label

    if ($SkillDir) {
        if (-not (Test-InstallPath -Path $SkillDir)) {
            Write-Host "X Invalid -SkillDir: contains forbidden characters or traversal" -ForegroundColor Red
            exit 1
        }
        $SkillBase = $SkillDir
    }
    if ($AgentDir) {
        if (-not (Test-InstallPath -Path $AgentDir)) {
            Write-Host "X Invalid -AgentDir: contains forbidden characters or traversal" -ForegroundColor Red
            exit 1
        }
        $AgentDirResolved = $AgentDir
    }

    $AdsSkillDir  = Join-Path $SkillBase "ads"
    $SeoSkillDir  = Join-Path $SkillBase "seo"
    $PrimaryRepoUrl  = "https://github.com/Decipheredmedia/claude-ads"
    $FallbackRepoUrl = "https://github.com/AI-Marketing-Hub/claude-ads"

    Write-Host "============================================"
    Write-Host "   Claude Ads + SEO Skill - Installer"
    Write-Host "   Target: $HostLabel"
    Write-Host "============================================"
    Write-Host ""

    # Check prerequisites
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "X Git is required but not installed." -ForegroundColor Red
        exit 1
    }
    Write-Host "OK Git detected" -ForegroundColor Green

    # Create directories
    if (-not $SkipAds) {
        New-Item -ItemType Directory -Path (Join-Path $AdsSkillDir "references") -Force | Out-Null
    }
    if (-not $SkipSeo) {
        New-Item -ItemType Directory -Path (Join-Path $SeoSkillDir "references") -Force | Out-Null
    }
    New-Item -ItemType Directory -Path $AgentDirResolved -Force | Out-Null

    # Clone to temp directory
    $TempDir = Join-Path $env:TEMP "claude-ads-install-$(Get-Random)"
    Write-Host "Downloading claude-ads..."

    try {
        # Temporarily allow stderr (git writes progress to stderr — treated as error in PS 5.1)
        $ErrorActionPreference = "Continue"
        git clone --depth 1 $PrimaryRepoUrl "$TempDir\claude-ads" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            git clone --depth 1 $FallbackRepoUrl "$TempDir\claude-ads" 2>&1 | Out-Null
        }
        $ErrorActionPreference = "Stop"
        if ($LASTEXITCODE -ne 0) { throw "Git clone failed from both repositories" }

        # ── Ads skill ──────────────────────────────────────────────────────
        if (-not $SkipAds) {
            Write-Host "Installing Ads skill files..."
            New-Item -ItemType Directory -Path "$AdsSkillDir\references" -Force | Out-Null
            Copy-Item "$TempDir\claude-ads\ads\SKILL.md" -Destination "$AdsSkillDir\SKILL.md" -Force
            if (Test-Path "$TempDir\claude-ads\ads\references") {
                Copy-Item "$TempDir\claude-ads\ads\references\*.md" -Destination "$AdsSkillDir\references\" -Force
            }
        }

        # ── SEO skill ──────────────────────────────────────────────────────
        if (-not $SkipSeo) {
            Write-Host "Installing SEO skill files..."
            New-Item -ItemType Directory -Path "$SeoSkillDir\references" -Force | Out-Null
            Copy-Item "$TempDir\claude-ads\seo\SKILL.md" -Destination "$SeoSkillDir\SKILL.md" -Force
            if (Test-Path "$TempDir\claude-ads\seo\references") {
                Copy-Item "$TempDir\claude-ads\seo\references\*.md" -Destination "$SeoSkillDir\references\" -Force
            }
        }

        # ── Sub-skills (ads-* and seo-*) ───────────────────────────────────
        Write-Host "Installing sub-skills..."
        Get-ChildItem "$TempDir\claude-ads\skills" -Directory | ForEach-Object {
            $SkillName = $_.Name
            if ($SkipAds -and $SkillName -like "ads-*") { return }
            if ($SkipSeo -and $SkillName -like "seo*")  { return }

            $TargetDir = Join-Path $SkillBase $SkillName
            New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
            Copy-Item (Join-Path $_.FullName "SKILL.md") -Destination "$TargetDir\SKILL.md" -Force

            # Copy assets (industry templates) if they exist
            $AssetsDir = Join-Path $_.FullName "assets"
            if (Test-Path $AssetsDir) {
                $TargetAssets = Join-Path $TargetDir "assets"
                New-Item -ItemType Directory -Path $TargetAssets -Force | Out-Null
                Copy-Item "$AssetsDir\*.md" -Destination "$TargetAssets\" -Force
            }
        }

        # ── Agents ────────────────────────────────────────────────────────
        Write-Host "Installing subagents..."
        Copy-Item "$TempDir\claude-ads\agents\*.md" -Destination "$AgentDirResolved\" -Force

        # ── Python scripts ─────────────────────────────────────────────────
        $ScriptsSource = "$TempDir\claude-ads\scripts"
        if (Test-Path $ScriptsSource) {
            Write-Host "Installing Python scripts (ads + SEO)..."
            $ScriptsDir = Join-Path $AdsSkillDir "scripts"
            New-Item -ItemType Directory -Path $ScriptsDir -Force | Out-Null
            Copy-Item "$ScriptsSource\*.py" -Destination "$ScriptsDir\" -Force
            Copy-Item "$TempDir\claude-ads\requirements.txt" -Destination "$AdsSkillDir\requirements.txt" -Force
        }

        # ── Python dependencies ────────────────────────────────────────────
        Write-Host ""
        if ($AllowPip) {
            Write-Host "Installing Python dependencies..."
            $ErrorActionPreference = "Continue"
            pip install -q -r "$AdsSkillDir\requirements.txt" 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  OK Python dependencies installed" -ForegroundColor Green
            } else {
                Write-Host "  Warning: pip install failed. Run manually: pip install -r $AdsSkillDir\requirements.txt" -ForegroundColor Yellow
            }
            $ErrorActionPreference = "Stop"
        } else {
            Write-Host "i  Skipping Python dependencies - $HostLabel host runtime may not execute Python skills directly." -ForegroundColor Yellow
            Write-Host "   If you need SEO scanning / fixing, install manually:"
            Write-Host "     pip install -r $AdsSkillDir\requirements.txt"
        }

        # ── Venice AI configuration ────────────────────────────────────────
        Write-Host ""
        if (-not $SkipSeo) {
            $SeoConfigFile = Join-Path $SeoSkillDir "config.json"

            # Determine key: parameter > env var
            $ResolvedKey = $VeniceApiKey
            if ([string]::IsNullOrWhiteSpace($ResolvedKey)) {
                $ResolvedKey = $env:VENICE_API_KEY
            }

            $ConfigData = @{
                api_key     = if ($ResolvedKey) { $ResolvedKey } else { "" }
                model       = "llama-3.3-70b"
                base_url    = "https://api.venice.ai/api/v1"
                temperature = 0.3
                max_tokens  = 512
                provider    = "venice"
            }
            $ConfigData | ConvertTo-Json -Depth 2 | Set-Content -Path $SeoConfigFile -Encoding UTF8

            if (-not [string]::IsNullOrWhiteSpace($ResolvedKey)) {
                Write-Host "  OK Venice AI config written to: $SeoConfigFile" -ForegroundColor Green
            } else {
                Write-Host "  Warning: Venice AI API key not configured." -ForegroundColor Yellow
                Write-Host "    For AI-assisted SEO fixes (title, description, alt-text, schema):"
                Write-Host "    Option 1: setx VENICE_API_KEY `"vn-your-key-here`""
                Write-Host "    Option 2: edit $SeoConfigFile"
                Write-Host "    Get your key at: https://venice.ai/settings/api"
                Write-Host ""
                Write-Host "    Structural SEO checks work without a key."
            }
        }

        # ── banana-claude check ────────────────────────────────────────────
        Write-Host ""
        if (-not $SkipAds) {
            $BananaPath = Join-Path $SkillBase "banana\SKILL.md"
            if (Test-Path $BananaPath) {
                Write-Host "  OK banana-claude detected (image generation ready)" -ForegroundColor Green
            } else {
                Write-Host "  Warning: banana-claude not installed. Image generation requires it." -ForegroundColor Yellow
                Write-Host "    Install: https://github.com/AgriciDaniel/banana-claude"
                Write-Host "    Then run: /banana setup (to configure API key)"
            }
            Write-Host ""
        }

        Write-Host "Installation complete for $HostLabel!" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Installed to:"
        Write-Host "    Skills: $SkillBase"
        Write-Host "    Agents: $AgentDirResolved"
        Write-Host ""
        if (-not $SkipAds) {
            Write-Host "  Ads skill:"
            Write-Host "    - 1 main skill (ads orchestrator)"
            Write-Host "    - 22 sub-skills (platform + functional + creative)"
            Write-Host "    - 10 agents (6 audit + 4 creative)"
            Write-Host ""
        }
        if (-not $SkipSeo) {
            Write-Host "  SEO skill (Venice AI powered):"
            Write-Host "    - 1 main skill (seo orchestrator)"
            Write-Host "    - 3 sub-skills (seo-audit, seo-fix, seo-scan)"
            Write-Host "    - Python scripts: seo_scanner.py, seo_fixer.py, seo_report.py, venice_provider.py"
            Write-Host ""
        }
        Write-Host "Usage:"
        Write-Host "  1. Start your host CLI"
        if (-not $SkipAds) {
            Write-Host "  2. Ads commands:   /ads audit"
            Write-Host "                     /ads plan saas"
            Write-Host "                     /ads google"
            Write-Host ""
        }
        if (-not $SkipSeo) {
            Write-Host "  3. SEO commands:   /seo scan ./public_html"
            Write-Host "                     /seo audit"
            Write-Host "                     /seo fix --dry-run"
            Write-Host "                     /seo fix"
            Write-Host ""
        }
        Write-Host "To uninstall: .\uninstall.ps1 -Target $Target"
    }
    finally {
        # Cleanup temp directory
        if (Test-Path $TempDir) {
            Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Main
