<#
.SYNOPSIS
One-shot local MCP setup (Windows PowerShell).

.DESCRIPTION
Installs Poetry if needed, installs project dependencies, creates .env from .env.example,
runs a local smoke import, and prints an MCP config snippet.

Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\setup_local_mcp.ps1
  powershell -ExecutionPolicy Bypass -File .\scripts\setup_local_mcp.ps1 -Dev

Notes:
  - Requires Python 3.12+ (Python 3.12 or 3.13 recommended).
#>

[CmdletBinding()]
param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

function Die {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

function Need-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Die "missing required command: $Name"
    }
}

function Ensure-Poetry {
    $poetryCmd = Get-Command poetry -ErrorAction SilentlyContinue
    if ($poetryCmd) {
        Write-Host "==> Poetry already on PATH: $($poetryCmd.Path)"
        return
    }

    Write-Host "==> Installing Poetry (official installer via py)..."
    $installer = (Invoke-WebRequest -Uri "https://install.python-poetry.org" -UseBasicParsing).Content
    $installer | py -
    if ($LASTEXITCODE -ne 0) {
        Die "Poetry installer failed. Ensure Python 3.12+ is your default 'py' runtime and internet/TLS settings are working."
    }

    $userScripts = Join-Path $env:APPDATA "Python\Scripts"
    if (Test-Path $userScripts) {
        $env:Path = "$userScripts;$env:Path"
    }

    if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
        Die "Poetry install finished but poetry is not on PATH. Add $userScripts to PATH, restart PowerShell, then rerun."
    }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

Write-Host "==> Repository: $RepoRoot"

Need-Command py

Write-Host "==> Checking Python >= 3.12 (recommended: 3.12/3.13)..."
$pyVersionOut = py -c "import sys; print(sys.version.split()[0])" 2>$null
if ($LASTEXITCODE -eq 0 -and $pyVersionOut) {
    Write-Host "    Found py default: $pyVersionOut"
}
$pyCheck = @'
import sys
if sys.version_info < (3, 12):
    sys.stderr.write(f"found Python {sys.version.split()[0]}\n")
    raise SystemExit(1)
'@
$pyCheck | py - 2>$null
if ($LASTEXITCODE -ne 0) {
    Die "Python 3.12+ is required. Recommended: Python 3.12 or 3.13."
}

Ensure-Poetry
poetry --version

Write-Host "==> Installing Python dependencies (poetry install)..."
poetry install --no-interaction

Write-Host "==> Ensuring local .env file..."
$envPath = Join-Path $RepoRoot ".env"
$envExamplePath = Join-Path $RepoRoot ".env.example"
if (-not (Test-Path $envPath)) {
    Copy-Item $envExamplePath $envPath
    Write-Host "    Created .env from .env.example — edit OVALEDGE_* and credentials before using MCP."
} else {
    Write-Host "    .env already exists; leaving in place."
}

Write-Host "==> Smoke check (import local MCP entrypoint)..."
poetry run python -c "from entrypoints.local import mcp; assert mcp is not None"

$hooksScript = Join-Path $RepoRoot "scripts" "setup_git_hooks.ps1"
if (Test-Path $hooksScript) {
    & $hooksScript
}

if ($Dev) {
    Write-Host "==> Running ruff..."
    poetry run ruff check .
    Write-Host "==> Running mypy..."
    poetry run mypy server/ entrypoints/
    Write-Host "==> Running pytest..."
    poetry run pytest
}

Write-Host ""
Write-Host "==> Local MCP is ready."
Write-Host "    Edit .env (OVALEDGE_BASE_URL, OVALEDGE_USER_TOKEN, OVALEDGE_USER_SECRET, AUTH_MODE=local)."
Write-Host "    Run manually:  poetry -C `"$RepoRoot`" run oe-mcp-local"
Write-Host ""
Write-Host "==> Cursor / Claude Desktop — add to your MCP config (mcp.json)."
Write-Host "    Below uses poetry -C <repo> (no cwd key). Env matches typical local OvalEdge MCP."
Write-Host ""

$mcpConfig = @{
    mcpServers = @{
        "ovaledge-local" = @{
            command = "poetry"
            args    = @("-C", $RepoRoot, "run", "oe-mcp-local")
            env     = @{
                OVALEDGE_BASE_URL        = "http://127.0.0.1:8080/ovaledge"
                OVALEDGE_USER_TOKEN      = "your-user-token"
                OVALEDGE_USER_SECRET     = "your-user-secret"
                OVALEDGE_HTTP_AUTH_SCHEME = "jwt"
                AUTH_MODE                = "local"
            }
        }
    }
}
$mcpConfig | ConvertTo-Json -Depth 8

Write-Host ""
Write-Host "    Replace env placeholders with your values (or omit env and rely on .env in the repo)."
Write-Host "    Cursor: cp .cursor/mcp.json.example .cursor/mcp.json — see .cursor/README.md"
Write-Host "Done."
