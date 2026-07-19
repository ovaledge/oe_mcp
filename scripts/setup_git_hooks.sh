#!/usr/bin/env bash
# Install pre-commit git hooks (ruff, mypy, pytest, CodeQL on commit only).
# Idempotent — safe to re-run.
#
# Usage:
#   ./scripts/setup_git_hooks.sh
#
# Called automatically from scripts/setup_local_mcp.sh when .git exists.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

die() { echo "error: $*" >&2; exit 1; }

if [[ ! -d .git ]]; then
  echo "==> Git hooks: skip (not a git repository)"
  exit 0
fi

command -v poetry >/dev/null 2>&1 || die "poetry not on PATH; run scripts/setup_local_mcp.sh first or install Poetry"

echo "==> Ensuring dev dependencies (pre-commit, pytest, ruff)..."
poetry install --with dev --no-interaction

echo "==> Installing pre-commit hooks (requires pre-commit >= 3.2)..."
poetry run pre-commit --version
poetry run pre-commit install
# Remove legacy pre-push hook so checks are not duplicated on git push.
poetry run pre-commit uninstall --hook-type pre-push 2>/dev/null || true
poetry run pre-commit validate-config .pre-commit-config.yaml

chmod +x scripts/run_codeql.sh 2>/dev/null || true

echo "==> Git hooks ready:"
echo "    git commit → ruff check + mypy + pytest (tests/) + CodeQL"
echo "                 (CodeQL skips if CLI missing; CODEQL_REQUIRED=1 to enforce;"
echo "                  CODEQL_SKIP=1 to skip once)"
echo "    git push   → no local hook (CI / GitHub Code Scanning on the remote)"
