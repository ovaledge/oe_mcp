#!/usr/bin/env bash
# Install pre-commit git hooks (ruff on commit, pytest on push).
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

echo "==> Installing pre-commit hooks..."
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push

echo "==> Git hooks ready:"
echo "    commit → ruff check"
echo "    push   → pytest (tests/)"
