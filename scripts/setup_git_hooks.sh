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

echo "==> Checking CodeQL CLI (required for commit hooks by default)..."
CODEQL_BIN=""
for candidate in codeql \
  "${REPO_ROOT}/.tools/codeql/codeql" \
  "${HOME}/.local/codeql/codeql" \
  "${HOME}/.local/bin/codeql"
do
  if command -v "${candidate}" >/dev/null 2>&1 || [[ -x "${candidate}" ]]; then
    if [[ "${candidate}" == "codeql" ]]; then
      CODEQL_BIN="$(command -v codeql)"
    else
      CODEQL_BIN="${candidate}"
    fi
    break
  fi
done

if [[ -z "${CODEQL_BIN}" ]]; then
  echo "warning: CodeQL CLI not found. Install with:" >&2
  echo "         ./scripts/install_codeql_cli.sh" >&2
  echo "         (commits will fail until installed, unless CODEQL_SKIP=1)" >&2
  if [[ "${CODEQL_SETUP_INSTALL:-0}" == "1" ]]; then
    echo "==> CODEQL_SETUP_INSTALL=1 — running install_codeql_cli.sh ..."
    bash "${REPO_ROOT}/scripts/install_codeql_cli.sh"
  fi
else
  echo "    found: ${CODEQL_BIN}"
  "${CODEQL_BIN}" version 2>/dev/null | head -n 3 || true
fi

echo "==> Installing pre-commit hooks (requires pre-commit >= 3.2)..."
poetry run pre-commit --version
poetry run pre-commit install
# Remove legacy pre-push hook so checks are not duplicated on git push.
poetry run pre-commit uninstall --hook-type pre-push 2>/dev/null || true
poetry run pre-commit validate-config .pre-commit-config.yaml

chmod +x scripts/run_codeql.sh scripts/install_codeql_cli.sh 2>/dev/null || true

echo "==> Git hooks ready:"
echo "    git commit → ruff check + mypy + pytest (tests/) + CodeQL (required)"
echo "                 CODEQL_SKIP=1 to skip once; CODEQL_REQUIRED=0 if CLI missing"
echo "    git push   → GitHub Actions CodeQL workflow + Code Scanning"
echo "    install CLI: ./scripts/install_codeql_cli.sh"
