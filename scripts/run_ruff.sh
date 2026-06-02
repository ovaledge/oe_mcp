#!/usr/bin/env bash
# Run ruff in the Poetry venv (macOS + Linux). Used by pre-commit and CI-style local checks.
#
# Usage:
#   ./scripts/run_ruff.sh
#   ./scripts/run_ruff.sh check --fix .

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

die() { echo "error: $*" >&2; exit 1; }

if [[ -x .venv/bin/ruff ]]; then
  exec .venv/bin/ruff check .
fi

command -v poetry >/dev/null 2>&1 || die "poetry not on PATH; run ./scripts/setup_local_mcp.sh first"

poetry install --with dev --no-interaction
exec poetry run ruff check .
