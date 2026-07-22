#!/usr/bin/env bash
# Type-check server, entrypoints, and evals (same as CI).
set -euo pipefail
cd "$(dirname "$0")/.."
poetry run mypy server/ entrypoints/ evals/
