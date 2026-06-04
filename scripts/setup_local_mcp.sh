#!/usr/bin/env bash
# One-shot local MCP setup (macOS + Linux).
# Usage:
#   ./scripts/setup_local_mcp.sh           # install deps, .env, smoke import, print mcp.json hint
#   ./scripts/setup_local_mcp.sh --dev     # also run ruff, mypy, pytest (developer / CI-like)
#   ./scripts/setup_local_mcp.sh --help

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RUN_DEV=0
for arg in "$@"; do
  case "$arg" in
    --dev) RUN_DEV=1 ;;
    -h|--help)
      cat <<'EOF'
One-shot local MCP setup (macOS + Linux).

Usage:
  ./scripts/setup_local_mcp.sh          Install Poetry if needed, poetry install, .env, smoke import, print mcp.json snippet.
  ./scripts/setup_local_mcp.sh --dev    Same as above, then ruff + mypy + pytest.

Notes:
  - Requires Python 3.12+ on PATH as python3 (Python 3.12 or 3.13 recommended).
  - Homebrew is optional; this script uses the official Poetry installer.
  - Local MCP uses stdio; the IDE starts the process — nothing runs as a background daemon here.
EOF
      exit 0
      ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

OS="$(uname -s)"
case "$OS" in
  Darwin|Linux) ;;
  *) die "unsupported OS: $OS (expected Darwin or Linux)" ;;
esac

need_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

echo "==> Repository: $REPO_ROOT"

need_cmd curl
need_cmd python3

echo "==> Checking Python >= 3.12 (recommended: 3.12/3.13)..."
PYTHON_VERSION="$(python3 -c 'import sys; print(sys.version.split()[0])')"
echo "    Found python3: $PYTHON_VERSION"
python3 - <<'PY' || die "Python 3.12+ is required. Recommended: Python 3.12 or 3.13 (install via pyenv, Homebrew, or your OS package manager)."
import sys
if sys.version_info < (3, 12):
    sys.stderr.write(f"found Python {sys.version.split()[0]}\n")
    raise SystemExit(1)
PY

ensure_poetry() {
  if command -v poetry >/dev/null 2>&1; then
    echo "==> Poetry already on PATH: $(command -v poetry)"
    return 0
  fi
  local po_home="${POETRY_HOME:-$HOME/.local/share/pypoetry}"
  local po_bin="$po_home/bin"
  if [[ -x "$po_bin/poetry" ]]; then
    export PATH="$po_bin:$PATH"
    echo "==> Poetry found at $po_bin/poetry"
    return 0
  fi
  echo "==> Installing Poetry (official installer via python3)..."
  curl -sSL https://install.python-poetry.org | python3 - || die "Poetry installer failed. Ensure python3 is 3.12+ and TLS/network settings allow downloads."
  export PATH="${po_bin}:$PATH"
  command -v poetry >/dev/null 2>&1 || die "Poetry install finished but poetry not on PATH; add $po_bin to PATH and restart your shell"
}

ensure_poetry
poetry --version

echo "==> Installing Python dependencies (poetry install --with dev)..."
poetry install --with dev --no-interaction

echo "==> Ensuring local .env file..."
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "    Created .env from .env.example — edit OVALEDGE_* and credentials before using MCP."
else
  echo "    .env already exists; leaving in place."
fi

echo "==> Smoke check (import local MCP entrypoint)..."
poetry run python -c "from entrypoints.local import mcp; assert mcp is not None"

if [[ -x "$REPO_ROOT/scripts/setup_git_hooks.sh" ]]; then
  "$REPO_ROOT/scripts/setup_git_hooks.sh"
fi

if [[ "$RUN_DEV" -eq 1 ]]; then
  echo "==> Running ruff..."
  poetry run ruff check .
  echo "==> Running mypy..."
  poetry run mypy server/ entrypoints/
  echo "==> Running pytest (with coverage)..."
  "$REPO_ROOT/scripts/run_tests.sh"
fi

echo ""
echo "==> Local MCP is ready."
echo "    Edit .env (OVALEDGE_BASE_URL, OVALEDGE_USER_TOKEN, OVALEDGE_USER_SECRET, AUTH_MODE=local)."
echo "    Run manually:  poetry -C \"$REPO_ROOT\" run oe-mcp-local"
echo ""
echo "==> Cursor / Claude Desktop — add to your MCP config (mcp.json)."
echo "    Below uses poetry -C <repo> (no cwd key). Env matches typical local OvalEdge MCP."
echo ""

REPO_ROOT_JSON="$REPO_ROOT" python3 - <<'PY'
import json
import os

repo = os.environ["REPO_ROOT_JSON"]
block = {
    "command": "poetry",
    "args": ["-C", repo, "run", "oe-mcp-local"],
    "env": {
        "OVALEDGE_BASE_URL": "http://127.0.0.1:8080/ovaledge",
        "OVALEDGE_USER_TOKEN": "your-user-token",
        "OVALEDGE_USER_SECRET": "your-user-secret",
        "OVALEDGE_HTTP_AUTH_SCHEME": "jwt",
        "AUTH_MODE": "local",
    },
}
print(json.dumps({"mcpServers": {"ovaledge-local": block}}, indent=2))
PY

echo ""
echo "    Replace env placeholders with your values (or omit env and rely on .env in the repo)."
echo "    Cursor: cp .cursor/mcp.json.example .cursor/mcp.json (or ~/.cursor/mcp.json) — see .cursor/README.md"
echo ""
echo "Done."
