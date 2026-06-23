#!/usr/bin/env bash
# Run OvalEdge MCP over HTTP on localhost (for Cursor logo + Streamable HTTP).
# Same credentials as stdio; use the ovaledge-local-http entry in .cursor/mcp.json.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

export AUTH_MODE="${AUTH_MODE:-local}"
export MCP_PUBLIC_BASE_URL="${MCP_PUBLIC_BASE_URL:-http://127.0.0.1:8000}"
export MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-false}"

: "${OVALEDGE_BASE_URL:?Set OVALEDGE_BASE_URL in .env or export it (OvalEdge app URL)}"
: "${OVALEDGE_USER_TOKEN:?Set OVALEDGE_USER_TOKEN in .env or export it}"
: "${OVALEDGE_USER_SECRET:?Set OVALEDGE_USER_SECRET in .env or export it}"

echo "OvalEdge MCP HTTP: ${MCP_PUBLIC_BASE_URL}/mcp"
echo "Brand icon:        ${MCP_PUBLIC_BASE_URL}/brand/ovaledge-mcp-icon.png"
echo "AUTH_MODE=${AUTH_MODE} MCP_HTTP_STATELESS=${MCP_HTTP_STATELESS}"
echo "Connect Cursor via ovaledge-local-http in mcp.json (no credential headers needed)."
echo ""

exec poetry run uvicorn entrypoints.lambda_handler:app --host 127.0.0.1 --port 8000
