#!/usr/bin/env bash
# Run OvalEdge MCP over HTTP on a remote host (EC2 / VM) with per-request credentials.
#
# AUTH_MODE=remote_credentials — OvalEdge user token+secret come from the MCP client
# (mcp.json headers), NOT from .env. The server only needs OVALEDGE_BASE_URL.
#
# By default the process is detached with nohup so closing the terminal does not kill it.
#
# Local laptop (credentials in .env, one JWT at startup):
#   ./scripts/run_local_mcp_http.sh
#
# Usage:
#   ./scripts/run_remote_mcp_http.sh              # start in background (default)
#   ./scripts/run_remote_mcp_http.sh --foreground # attach to terminal (debug)
#   ./scripts/run_remote_mcp_http.sh --stop       # stop background process
#   ./scripts/run_remote_mcp_http.sh --status     # show pid / health
#   HOST=0.0.0.0 PORT=8000 MCP_PUBLIC_BASE_URL=http://YOUR_HOST:8000 ./scripts/run_remote_mcp_http.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Non-interactive shells (nohup/systemd) often omit Poetry from PATH.
export PATH="${HOME}/.local/bin:${PATH}"

PID_FILE="${OE_MCP_PID_FILE:-/tmp/oe-mcp-remote-http.pid}"
LOG_FILE="${OE_MCP_LOG_FILE:-/tmp/oe-mcp-remote-http.log}"
MODE="background"

usage() {
  cat <<'EOF'
Usage: ./scripts/run_remote_mcp_http.sh [--foreground|--stop|--status|-h]

  (default)       Start uvicorn detached via nohup (survives terminal close)
  --foreground    Run in the current terminal (Ctrl+C stops the server)
  --stop          Stop the background process recorded in the pid file
  --status        Show pid file / process / health
  -h, --help      Show this help

Env: HOST (default 0.0.0.0), PORT (8000), MCP_PUBLIC_BASE_URL, OVALEDGE_BASE_URL,
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

# Force remote header auth — do not inherit AUTH_MODE=local from .env.
# Credentials are supplied per request via X-OvalEdge-Token + X-OvalEdge-Secret
# (or X-OvalEdge-Credentials) from the MCP client mcp.json.
export AUTH_MODE=remote_credentials
export MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-false}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

# Public URL clients use (Cursor mcp.json). Override when behind a custom domain / TLS proxy.
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
  echo "OvalEdge MCP HTTP (remote_credentials): ${MCP_PUBLIC_BASE_URL}/mcp"
  echo "Brand icon:        ${MCP_PUBLIC_BASE_URL}/brand/ovaledge-mcp-icon.png"
  echo "AUTH_MODE=${AUTH_MODE} MCP_HTTP_STATELESS=${MCP_HTTP_STATELESS}"
  echo "Bind: ${HOST}:${PORT}"
  echo ""
  echo "mcp.json example (credentials from client — not stored on this server):"
  echo ""
  cat <<EOF
{
  "mcpServers": {
    "ovaledge-remote-http": {
      "url": "${MCP_PUBLIC_BASE_URL}/mcp",
      "headers": {
        "X-Forwarded-Proto": "https",
        "X-OvalEdge-Token": "YOUR_OVALEDGE_USER_TOKEN",
        "X-OvalEdge-Secret": "YOUR_OVALEDGE_USER_SECRET"
      }
    }
  }
}
EOF
  echo ""
  echo "X-Forwarded-Proto: https is required when the client talks plain HTTP (middleware TLS check)."
  echo "Prefer a TLS reverse proxy (nginx/Caddy) in production and drop that header spoof."
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
  echo "Stopping MCP HTTP pid=${pid} ..."
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

: "${OVALEDGE_BASE_URL:?Set OVALEDGE_BASE_URL in .env or export it (OvalEdge app URL)}"

# Server must NOT require machine user token/secret for this mode.
if [[ -n "${OVALEDGE_USER_TOKEN:-}" || -n "${OVALEDGE_USER_SECRET:-}" ]]; then
  echo "Note: OVALEDGE_USER_TOKEN / OVALEDGE_USER_SECRET in .env are ignored for AUTH_MODE=remote_credentials."
  echo "      Put credentials in the MCP client mcp.json headers instead."
  echo ""
fi

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
  echo "Running in foreground (Ctrl+C to stop). For detach, omit --foreground."
  echo ""
  exec "${UVICORN_CMD[@]}"
fi

# Background: nohup + disown so SIGHUP from closing SSH/terminal does not kill uvicorn.
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
echo "  ./scripts/run_remote_mcp_http.sh --status"
echo "  ./scripts/run_remote_mcp_http.sh --stop"
echo "  tail -f ${LOG_FILE}"
