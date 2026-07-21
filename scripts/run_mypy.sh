#!/usr/bin/env bash
# Type-check server, entrypoints, and evals (same as CI).
# Prefer the project venv so GUI/IDE git commits still work when poetry is
# not on the hook PATH (common on macOS).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

die() { echo "error: $*" >&2; exit 1; }

MYPY_TARGETS=(server/ entrypoints/ evals/)

if [[ -x .venv/bin/mypy ]]; then
  exec .venv/bin/mypy "${MYPY_TARGETS[@]}"
fi

# GUI git hosts often use a minimal PATH; include common Poetry locations.
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"

command -v poetry >/dev/null 2>&1 || die "poetry not on PATH and .venv/bin/mypy missing; run ./scripts/setup_local_mcp.sh first"

exec poetry run mypy "${MYPY_TARGETS[@]}"
