#Requires -Version 5.1
<#
.SYNOPSIS
    Claude Ads Uninstaller for Windows (multi-host).
.DESCRIPTION
    Removes every ads-* sub-skill directory plus the orchestrator and bundled
    agents from the chosen host's install root. Uses glob discovery so new
    sub-skills don't require uninstaller updates.
.PARAMETER Target
    Which host CLI to uninstall from. Default: claude.
#>

param(
    [ValidateSet('claude','codex','cursor','windsurf','gemini','goose')]
    [string]$Target = 'claude'
)

$ErrorActionPreference = "Stop"

function Resolve-TargetPaths {
    param([string]$T)
    switch ($T) {
        'claude'   { return @{ SkillBase = Join-Path $env:USERPROFILE ".claude\skills";                                AgentDir = Join-Path $env:USERPROFILE ".claude\agents" } }
        'codex'    { return @{ SkillBase = Join-Path $env:USERPROFILE ".codex\skills";                                 AgentDir = Join-Path $env:USERPROFILE ".codex\agents" } }
        'cursor'   { return @{ SkillBase = Join-Path $env:USERPROFILE ".cursor\extensions\claude-ads\skills";          AgentDir = Join-Path $env:USERPROFILE ".cursor\extensions\claude-ads\agents" } }
        'windsurf' { return @{ SkillBase = Join-Path $env:USERPROFILE ".windsurf\skills";                              AgentDir = Join-Path $env:USERPROFILE ".windsurf\agents" } }
        'gemini'   { return @{ SkillBase = Join-Path $env:USERPROFILE ".gemini\extensions\claude-ads\skills";          AgentDir = Join-Path $env:USERPROFILE ".gemini\extensions\claude-ads\agents" } }
        'goose'    { return @{ SkillBase = Join-Path $env:USERPROFILE ".config\goose\skills";                          AgentDir = Join-Path $env:USERPROFILE ".config\goose\agents" } }
        default    { throw "Unknown target: $T" }
    }
}

function Main {
    $paths = Resolve-TargetPaths -T $Target
    $SkillBase = $paths.SkillBase
    $AgentDir = $paths.AgentDir

    Write-Host "Uninstalling from $SkillBase and $AgentDir..."

    # Remove orchestrators (ads + seo)
    foreach ($skillName in @("ads", "seo")) {
        $SkillPath = Join-Path $SkillBase $skillName
        if (Test-Path $SkillPath) {
            Remove-Item -Path $SkillPath -Recurse -Force
        }
    }

    # Remove all ads-* and seo-* sub-skills via glob
    if (Test-Path $SkillBase) {
        Get-ChildItem -Path $SkillBase -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "ads-*" -or $_.Name -like "seo-*" } |
            ForEach-Object { Remove-Item -Path $_.FullName -Recurse -Force }
    }

    # Remove bundled audit + creative agents.
    # NOTE: Keep this list in sync with the contents of `agents/` in the repo.
    # install.ps1 uses `Copy-Item agents\*.md` so any new agent file added
    # there must also be appended below. Pre-v1.7.1 the list contained
    # non-existent entries (audit-amazon, audit-attribution, audit-server-side)
    # and missed the actual shipped agents.
    $Agents = @(
        "audit-budget", "audit-compliance", "audit-creative",
        "audit-google", "audit-meta", "audit-tracking",
        "copy-writer", "creative-strategist", "format-adapter", "visual-designer"
    )
    foreach ($agent in $Agents) {
        $AgentPath = Join-Path $AgentDir "$agent.md"
        if (Test-Path $AgentPath) {
            Remove-Item -Path $AgentPath -Force
        }
    }

    Write-Host "[OK] Uninstalled (ads + seo skills removed)." -ForegroundColor Green
}

Main
