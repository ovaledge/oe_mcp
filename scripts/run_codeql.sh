#!/usr/bin/env bash
# Run CodeQL Python security analysis (used by the pre-commit hook).
# Optional unless CODEQL_REQUIRED=1.
#
# Usage:
#   ./scripts/run_codeql.sh
#
# Env:
#   CODEQL_SKIP=1       — skip entirely (exit 0)
#   CODEQL_REQUIRED=1   — fail if `codeql` is not on PATH
#   CODEQL_BIN          — path to codeql binary (default: codeql on PATH)
#   CODEQL_DB_DIR       — database dir (default: .codeql/db)
#   CODEQL_OUT_DIR      — results dir (default: .codeql)
#
# Install CodeQL CLI: https://docs.github.com/en/code-security/codeql-cli

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ "${CODEQL_SKIP:-0}" == "1" ]]; then
  echo "codeql: skipped (CODEQL_SKIP=1)"
  exit 0
fi

CODEQL_BIN="${CODEQL_BIN:-codeql}"
CODEQL_OUT_DIR="${CODEQL_OUT_DIR:-.codeql}"
CODEQL_DB_DIR="${CODEQL_DB_DIR:-${CODEQL_OUT_DIR}/db}"
CSV_OUT="${CODEQL_OUT_DIR}/results.csv"
SUITE="codeql/python-queries:codeql-suites/python-security-and-quality.qls"
SUITE_FALLBACK="python-security-and-quality.qls"

if ! command -v "${CODEQL_BIN}" >/dev/null 2>&1; then
  msg="codeql: '${CODEQL_BIN}' not found on PATH."
  if [[ "${CODEQL_REQUIRED:-0}" == "1" ]]; then
    echo "error: ${msg} Install CodeQL CLI or set CODEQL_BIN. (CODEQL_REQUIRED=1)" >&2
    exit 1
  fi
  echo "warning: ${msg} Skipping. Install CLI or set CODEQL_REQUIRED=1 to enforce." >&2
  exit 0
fi

mkdir -p "${CODEQL_OUT_DIR}"

echo "==> CodeQL: creating Python database at ${CODEQL_DB_DIR} ..."
"${CODEQL_BIN}" database create "${CODEQL_DB_DIR}" \
  --language=python \
  --source-root="${REPO_ROOT}" \
  --overwrite \
  --quiet

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

# Fail on any finding whose path mentions server/ (CSV layout varies by CLI version;
# match the whole row for simplicity).
ALERT_LINES="$(awk 'NR>1 && tolower($0) ~ /server\// { print }' "${CSV_OUT}" || true)"
ALERT_COUNT=0
if [[ -n "${ALERT_LINES}" ]]; then
  ALERT_COUNT="$(printf '%s\n' "${ALERT_LINES}" | grep -c . || true)"
fi

if [[ "${ALERT_COUNT}" -gt 0 ]]; then
  echo "error: CodeQL reported ${ALERT_COUNT} alert(s) under server/:" >&2
  printf '%s\n' "${ALERT_LINES}" | head -n 40 >&2
  echo "Full results: ${CSV_OUT}" >&2
  echo "Skip once: CODEQL_SKIP=1 git commit ..." >&2
  exit 1
fi

echo "==> CodeQL: no alerts under server/ (results: ${CSV_OUT})"
exit 0
