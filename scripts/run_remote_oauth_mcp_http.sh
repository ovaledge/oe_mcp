#!/usr/bin/env bash
# Run OvalEdge MCP over HTTP with AUTH_MODE=remote (Okta / OIDC Connect).
#
# Clients use the MCP Connect button → Okta authorize/token. This server validates
# the access token (JWT JWKS or opaque introspect) and forwards Bearer to OvalEdge.
#
# Server .env needs: OVALEDGE_BASE_URL, OAUTH_ISSUER, OAUTH_CLIENT_ID,
# OAUTH_CLIENT_SECRET (for introspect), optional OAUTH_AUDIENCE / OAUTH_INTROSPECTION_URL.
# Okta redirect URIs (Cursor/Claude/GitHub Copilot/Microsoft Copilot):
#   README_REMOTE_MCP.md#okta-redirect-uris-all-clients
# Lambda ZIP: AUTH_MODE=remote ./scripts/deploy.sh --zip
#   infra/DEPLOY.md#okta-connect-lambda-zip
#
# Header-auth deployments (token+secret in mcp.json):
#   ./scripts/run_remote_mcp_http.sh
#
# Usage:
#   ./scripts/run_remote_oauth_mcp_http.sh              # start detached
#   ./scripts/run_remote_oauth_mcp_http.sh --foreground
#   ./scripts/run_remote_oauth_mcp_http.sh --stop
#   ./scripts/run_remote_oauth_mcp_http.sh --status
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="${HOME}/.local/bin:${PATH}"

PID_FILE="${OE_MCP_PID_FILE:-/tmp/oe-mcp-remote-oauth-http.pid}"
LOG_FILE="${OE_MCP_LOG_FILE:-/tmp/oe-mcp-remote-oauth-http.log}"
MODE="background"

usage() {
  cat <<'EOF'
Usage: ./scripts/run_remote_oauth_mcp_http.sh [--foreground|--stop|--status|-h]

  (default)       Start uvicorn detached via nohup
  --foreground    Run in the current terminal
  --stop          Stop the background process
  --status        Show pid / health
  -h, --help      Show this help

Env: HOST, PORT, MCP_PUBLIC_BASE_URL, OVALEDGE_BASE_URL, OAUTH_*,
     OE_MCP_PID_FILE, OE_MCP_LOG_FILE
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --foreground | -f)
      MODE="foreground"
      shift
      ;;
    --stop)
      MODE="stop"
      shift
      ;;
    --status)
      MODE="status"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1 (try --help)" >&2
      exit 1
      ;;
  esac
done

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

export AUTH_MODE=remote
export MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-false}"
export OVALEDGE_REMOTE_FORWARD_IDP_TOKEN="${OVALEDGE_REMOTE_FORWARD_IDP_TOKEN:-true}"
# Prefer Bearer for Okta tokens when unset / still jwt from local mode.
if [[ -z "${OVALEDGE_HTTP_AUTH_SCHEME:-}" || "${OVALEDGE_HTTP_AUTH_SCHEME}" == "jwt" ]]; then
  export OVALEDGE_HTTP_AUTH_SCHEME=Bearer
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [[ -z "${MCP_PUBLIC_BASE_URL:-}" ]]; then
  DETECTED_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  if [[ -n "${DETECTED_IP}" ]]; then
    MCP_PUBLIC_BASE_URL="http://${DETECTED_IP}:${PORT}"
  else
    MCP_PUBLIC_BASE_URL="http://127.0.0.1:${PORT}"
  fi
fi
export MCP_PUBLIC_BASE_URL

print_client_hint() {
  echo "OvalEdge MCP HTTP (AUTH_MODE=remote / Okta): ${MCP_PUBLIC_BASE_URL}/mcp"
  echo "OAuth discovery: ${MCP_PUBLIC_BASE_URL}/.well-known/oauth-authorization-server"
  echo "AUTH_MODE=${AUTH_MODE} forward_idp=${OVALEDGE_REMOTE_FORWARD_IDP_TOKEN}"
  echo "Bind: ${HOST}:${PORT}"
  echo ""
  echo "mcp.json (Connect button — no token/secret headers):"
  echo ""
  cat <<EOF
{
  "mcpServers": {
    "ovaledge-remote-oauth": {
      "url": "${MCP_PUBLIC_BASE_URL}/mcp"
    }
  }
}
EOF
  echo ""
  echo "Require: OAUTH_ISSUER, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET (introspect)."
  echo "Prefer HTTPS (or X-Forwarded-Proto: https) for protected /mcp calls."
}

is_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  if [[ -f "$PID_FILE" ]]; then
    tr -d '[:space:]' <"$PID_FILE" || true
  fi
}

stop_server() {
  local pid
  pid="$(read_pid)"
  if [[ -z "$pid" ]]; then
    echo "No pid file at ${PID_FILE} (server not tracked)."
    exit 0
  fi
  if ! is_running "$pid"; then
    echo "Stale pid ${pid} — removing ${PID_FILE}"
    rm -f "$PID_FILE"
    exit 0
  fi
  echo "Stopping MCP OAuth HTTP pid=${pid} ..."
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! is_running "$pid"; then
      rm -f "$PID_FILE"
      echo "Stopped."
      exit 0
    fi
    sleep 1
  done
  echo "Process still running; sending SIGKILL ..."
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "Stopped."
}

status_server() {
  local pid
  pid="$(read_pid)"
  echo "PID file: ${PID_FILE}"
  echo "Log file: ${LOG_FILE}"
  if [[ -z "$pid" ]]; then
    echo "Status:   not running (no pid file)"
  elif is_running "$pid"; then
    echo "Status:   running (pid=${pid})"
    ps -p "$pid" -o pid=,etime=,cmd= || true
  else
    echo "Status:   not running (stale pid=${pid})"
  fi
  if command -v curl >/dev/null 2>&1; then
    echo ""
    echo "Health:   $(curl -sS --max-time 3 "http://127.0.0.1:${PORT}/health" 2>/dev/null || echo 'unreachable')"
  fi
}

case "$MODE" in
  stop)
    stop_server
    ;;
  status)
    status_server
    exit 0
    ;;
esac

: "${OVALEDGE_BASE_URL:?Set OVALEDGE_BASE_URL in .env or export it}"
: "${OAUTH_ISSUER:?Set OAUTH_ISSUER (e.g. https://….okta.com/oauth2/default)}"
: "${OAUTH_CLIENT_ID:?Set OAUTH_CLIENT_ID (Okta app client id)}"

existing_pid="$(read_pid)"
if [[ -n "$existing_pid" ]] && is_running "$existing_pid"; then
  echo "error: already running as pid ${existing_pid} (see --status / --stop)" >&2
  exit 1
fi
rm -f "$PID_FILE"

print_client_hint
echo ""

UVICORN_CMD=(poetry run uvicorn entrypoints.lambda_handler:app --host "$HOST" --port "$PORT")

if [[ "$MODE" == "foreground" ]]; then
  echo "Running in foreground (Ctrl+C to stop)."
  echo ""
  exec "${UVICORN_CMD[@]}"
fi

nohup "${UVICORN_CMD[@]}" >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
disown $! 2>/dev/null || true

sleep 1
pid="$(read_pid)"
if ! is_running "$pid"; then
  echo "error: process exited immediately — check log:" >&2
  echo "  ${LOG_FILE}" >&2
  tail -n 40 "$LOG_FILE" >&2 || true
  rm -f "$PID_FILE"
  exit 1
fi

echo "Started in background (survives terminal close)."
echo "  pid:    ${pid}"
echo "  log:    ${LOG_FILE}"
echo "  pidfile:${PID_FILE}"
echo ""
echo "Commands:"
echo "  ./scripts/run_remote_oauth_mcp_http.sh --status"
echo "  ./scripts/run_remote_oauth_mcp_http.sh --stop"
echo "  tail -f ${LOG_FILE}"
