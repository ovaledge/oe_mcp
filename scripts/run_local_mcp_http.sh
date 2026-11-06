#!/usr/bin/env bash
# Run OvalEdge MCP over HTTP on localhost (for Cursor logo + Streamable HTTP).
# Credentials: export OVALEDGE_USER_TOKEN / OVALEDGE_USER_SECRET (and BASE_URL)
# when you run this script, or leave them in .env. Existing exports win — a
# placeholder .env must not overwrite keys you pass on the command line.
# Cursor stdio (ovaledge-local) uses mcp.json env and does not need .env.
# Connect Cursor via ovaledge-local-http in mcp.json (no credential headers).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

_base_was_set=0
_token_was_set=0
_secret_was_set=0
[[ -n "${OVALEDGE_BASE_URL+x}" ]] && _base_was_set=1 && _base_saved="$OVALEDGE_BASE_URL"
[[ -n "${OVALEDGE_USER_TOKEN+x}" ]] && _token_was_set=1 && _token_saved="$OVALEDGE_USER_TOKEN"
[[ -n "${OVALEDGE_USER_SECRET+x}" ]] && _secret_was_set=1 && _secret_saved="$OVALEDGE_USER_SECRET"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

if [[ "$_base_was_set" -eq 1 ]]; then
  export OVALEDGE_BASE_URL="$_base_saved"
fi
if [[ "$_token_was_set" -eq 1 ]]; then
  export OVALEDGE_USER_TOKEN="$_token_saved"
fi
if [[ "$_secret_was_set" -eq 1 ]]; then
  export OVALEDGE_USER_SECRET="$_secret_saved"
fi
unset _base_was_set _token_was_set _secret_was_set _base_saved _token_saved _secret_saved

# Local HTTP must use AUTH_MODE=local so the JWT is exchanged once at startup and cached
# (see local_oe_jwt_lifespan). Do not inherit AUTH_MODE=remote_credentials from .env —
# that re-calls token/generate on every MCP request and breaks OvalEdge single-active-JWT.
#
# Force jwt for outbound OvalEdge calls: a shared .env often sets
# OVALEDGE_HTTP_AUTH_SCHEME=Bearer in the remote section later; that scheme is for IdP
# tokens and causes OvalEdge 401 for JWTs from token/generate.
export AUTH_MODE=local
export OVALEDGE_HTTP_AUTH_SCHEME=jwt
export MCP_PUBLIC_BASE_URL="${MCP_PUBLIC_BASE_URL:-http://127.0.0.1:8000}"
export MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-false}"

: "${OVALEDGE_BASE_URL:?Set OVALEDGE_BASE_URL when running this script, or in .env (OvalEdge app URL)}"
: "${OVALEDGE_USER_TOKEN:?Set OVALEDGE_USER_TOKEN when running this script, or in .env}"
: "${OVALEDGE_USER_SECRET:?Set OVALEDGE_USER_SECRET when running this script, or in .env}"

echo "OvalEdge MCP HTTP: ${MCP_PUBLIC_BASE_URL}/mcp"
echo "Brand icon:        ${MCP_PUBLIC_BASE_URL}/brand/ovaledge-mcp-icon.png"
echo "AUTH_MODE=${AUTH_MODE} OVALEDGE_HTTP_AUTH_SCHEME=${OVALEDGE_HTTP_AUTH_SCHEME} MCP_HTTP_STATELESS=${MCP_HTTP_STATELESS}"
echo "Connect Cursor via ovaledge-local-http in mcp.json (no credential headers needed)."
echo ""

exec poetry run uvicorn entrypoints.lambda_handler:app --host 127.0.0.1 --port 8000
