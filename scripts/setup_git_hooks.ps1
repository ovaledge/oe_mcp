<#
.SYNOPSIS
Install pre-commit git hooks (ruff, mypy, pytest on commit only).

.DESCRIPTION
Idempotent. Skips if not a git repository.
Called from setup_local_mcp.ps1 when .git exists.

Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\setup_git_hooks.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    Write-Host "==> Git hooks: skip (not a git repository)"
    exit 0
}

if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    Write-Error "poetry not on PATH; run scripts/setup_local_mcp.ps1 first or install Poetry"
    exit 1
}

Write-Host "==> Ensuring dev dependencies (pre-commit, pytest, ruff)..."
poetry install --with dev --no-interaction

Write-Host "==> Installing pre-commit hooks (requires pre-commit >= 3.2)..."
poetry run pre-commit --version
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
poetry run pre-commit install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
poetry run pre-commit uninstall --hook-type pre-push 2>$null
poetry run pre-commit validate-config .pre-commit-config.yaml
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Git hooks ready:"
Write-Host "    git commit -> ruff check + mypy + pytest (tests/)"
Write-Host "    git push   -> no local hook (CI runs on the remote)"
