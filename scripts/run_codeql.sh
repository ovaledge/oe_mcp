#!/usr/bin/env bash
# Run CodeQL Python security analysis (used by the pre-commit hook).
#
# Required by default: commits fail if the CodeQL CLI is missing or if
# security alerts are found under first-party server/ / entrypoints/.
# Opt out once with CODEQL_SKIP=1, or set CODEQL_REQUIRED=0 to allow a missing CLI.
#
# Usage:
#   ./scripts/run_codeql.sh
#   ./scripts/install_codeql_cli.sh   # one-time CLI install
#
# Env:
#   CODEQL_SKIP=1         — skip entirely (exit 0)
#   CODEQL_REQUIRED=0|1   — default 1; fail if `codeql` is not on PATH
#   CODEQL_BIN            — path to codeql binary (default: codeql on PATH)
#   CODEQL_DB_DIR         — database dir (default: .codeql/db)
#   CODEQL_OUT_DIR        — results dir (default: .codeql)
#   CODEQL_SUITE          — query suite (default: security-extended; faster than
#                           security-and-quality and skips "unused variable" noise)
#
# Install: ./scripts/install_codeql_cli.sh
# Config:  .github/codeql/codeql-config.yml (excludes .aws-sam, .venv, …)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ "${CODEQL_SKIP:-0}" == "1" ]]; then
  echo "codeql: skipped (CODEQL_SKIP=1)"
  exit 0
fi

CODEQL_REQUIRED="${CODEQL_REQUIRED:-1}"
CODEQL_BIN="${CODEQL_BIN:-codeql}"
CODEQL_OUT_DIR="${CODEQL_OUT_DIR:-.codeql}"
CODEQL_DB_DIR="${CODEQL_DB_DIR:-${CODEQL_OUT_DIR}/db}"
CSV_OUT="${CODEQL_OUT_DIR}/results.csv"
CONFIG="${REPO_ROOT}/.github/codeql/codeql-config.yml"
# Local default: security-extended (not security-and-quality) — much less noise/time.
SUITE="${CODEQL_SUITE:-codeql/python-queries:codeql-suites/python-security-extended.qls}"
SUITE_FALLBACK="${CODEQL_SUITE_FALLBACK:-python-security-extended.qls}"

# Prefer a repo-local or user-local install from install_codeql_cli.sh when PATH
# does not already have `codeql`.
if ! command -v "${CODEQL_BIN}" >/dev/null 2>&1; then
  for candidate in \
    "${REPO_ROOT}/.tools/codeql/codeql" \
    "${HOME}/.local/codeql/codeql"
  do
    if [[ -x "${candidate}" ]]; then
      CODEQL_BIN="${candidate}"
      break
    fi
  done
fi

if ! command -v "${CODEQL_BIN}" >/dev/null 2>&1 && [[ ! -x "${CODEQL_BIN}" ]]; then
  msg="codeql: '${CODEQL_BIN}' not found on PATH (or .tools/codeql / ~/.local/codeql)."
  if [[ "${CODEQL_REQUIRED}" == "1" ]]; then
    echo "error: ${msg}" >&2
    echo "Install: ./scripts/install_codeql_cli.sh" >&2
    echo "Or skip once: CODEQL_SKIP=1 git commit ..." >&2
    exit 1
  fi
  echo "warning: ${msg} Skipping (CODEQL_REQUIRED=0)." >&2
  exit 0
fi

mkdir -p "${CODEQL_OUT_DIR}"

CREATE_ARGS=(
  database create "${CODEQL_DB_DIR}"
  --language=python
  --source-root="${REPO_ROOT}"
  --overwrite
  --quiet
)
if [[ -f "${CONFIG}" ]]; then
  CREATE_ARGS+=(--codescanning-config="${CONFIG}")
  echo "==> CodeQL: using config ${CONFIG}"
else
  echo "warning: missing ${CONFIG}; extraction may include .aws-sam and be very slow" >&2
fi

echo "==> CodeQL: creating Python database at ${CODEQL_DB_DIR} ..."
"${CODEQL_BIN}" "${CREATE_ARGS[@]}"

echo "==> CodeQL: analyzing (${SUITE}) ..."
if ! "${CODEQL_BIN}" database analyze "${CODEQL_DB_DIR}" \
  --format=csv \
  --output="${CSV_OUT}" \
  "${SUITE}" \
  --quiet
then
  "${CODEQL_BIN}" database analyze "${CODEQL_DB_DIR}" \
    --format=csv \
    --output="${CSV_OUT}" \
    "${SUITE_FALLBACK}" \
    --quiet
fi

if [[ ! -f "${CSV_OUT}" ]]; then
  echo "error: CodeQL produced no CSV results at ${CSV_OUT}" >&2
  exit 1
fi

# Only first-party paths (repo-root /server/ or /entrypoints/), never .aws-sam copies.
# CSV path column is typically quoted like "/server/auth/....py".
ALERT_LINES="$(
  awk -F',' '
    NR == 1 { next }
    {
      line = $0
      # Prefer a quoted path field that starts with /server/ or /entrypoints/
      if (match(line, /"\/(server|entrypoints)\/[^"]*"/)) {
        path = substr(line, RSTART, RLENGTH)
        if (path !~ /\.aws-sam/ && path !~ /\.venv/) {
          # Skip recommendation-only noise if severity column says recommendation
          if (line ~ /,"recommendation",/) next
          print line
        }
      }
    }
  ' "${CSV_OUT}" || true
)"

ALERT_COUNT=0
if [[ -n "${ALERT_LINES}" ]]; then
  ALERT_COUNT="$(printf '%s\n' "${ALERT_LINES}" | grep -c . || true)"
fi

if [[ "${ALERT_COUNT}" -gt 0 ]]; then
  echo "error: CodeQL reported ${ALERT_COUNT} first-party alert(s) under server/ or entrypoints/:" >&2
  # Avoid SIGPIPE (exit 141) under pipefail when head closes early.
  printf '%s\n' "${ALERT_LINES}" | head -n 40 >&2 || true
  echo "Full results: ${CSV_OUT}" >&2
  echo "Skip once: CODEQL_SKIP=1 git commit ..." >&2
  exit 1
fi

echo "==> CodeQL: no first-party security alerts (results: ${CSV_OUT})"
exit 0
