#!/usr/bin/env bash
# Run mypy in the Poetry venv (macOS + Linux). Used by pre-commit and CI-style local checks.
#
# Usage:
#   ./scripts/run_mypy.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

die() { echo "error: $*" >&2; exit 1; }

MYPY_ARGS=(server/ entrypoints/ evals/)

if [[ -x .venv/bin/mypy ]]; then
  exec .venv/bin/mypy "${MYPY_ARGS[@]}"
fi

command -v poetry >/dev/null 2>&1 || die "poetry not on PATH; run ./scripts/setup_local_mcp.sh first"

poetry install --with dev --no-interaction
exec poetry run mypy "${MYPY_ARGS[@]}"
