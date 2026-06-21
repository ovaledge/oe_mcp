#!/usr/bin/env bash
# Run unit tests in the Poetry venv (macOS + Linux).
# Coverage flags are explicit here so plain `pytest` on PATH never fails when
# pytest-cov is missing (e.g. system Python outside .venv).
#
# Usage:
#   ./scripts/run_tests.sh              # default: term coverage report
#   ./scripts/run_tests.sh -q           # extra pytest args
#   ./scripts/run_tests.sh --no-cov     # skip coverage (faster)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

die() { echo "error: $*" >&2; exit 1; }

WITH_COV=1
PYTEST_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --no-cov) WITH_COV=0 ;;
    *) PYTEST_ARGS+=("$arg") ;;
  esac
done

run_pytest() {
  local pytest_bin="$1"
  if [[ "$WITH_COV" -eq 1 ]]; then
    exec "$pytest_bin" \
      --cov=server \
      --cov=entrypoints \
      --cov-report=term-missing:skip-covered \
      --cov-fail-under=0 \
      "${PYTEST_ARGS[@]}"
  fi
  exec "$pytest_bin" "${PYTEST_ARGS[@]}"
}

if [[ -x .venv/bin/pytest ]]; then
  run_pytest .venv/bin/pytest
fi

command -v poetry >/dev/null 2>&1 || die "poetry not on PATH; run ./scripts/setup_local_mcp.sh first"

poetry install --with dev --no-interaction

if [[ "$WITH_COV" -eq 1 ]]; then
  exec poetry run pytest \
    --cov=server \
    --cov=entrypoints \
    --cov-report=term-missing:skip-covered \
    --cov-fail-under=0 \
    "${PYTEST_ARGS[@]}"
fi

exec poetry run pytest "${PYTEST_ARGS[@]}"
