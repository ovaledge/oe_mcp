"""
Local MCP entrypoint — HTTP transport (uvicorn).

Use when Cursor (or similar) should show the OvalEdge MCP logo from
``GET /brand/ovaledge-mcp-icon.png``. Pair with ``ovaledge-local-http`` in
``.cursor/mcp.json``. Uses ``AUTH_MODE=local`` (same credentials as stdio).

Run:
    poetry run oe-mcp-http
    # or: ./scripts/run_local_mcp_http.sh
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import uvicorn
from dotenv import load_dotenv

from server.branding import brand_icon_http_base, brand_icon_public_url, resolve_mcp_icon_src
from server.logging_config import configure_runtime_observability

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_repo_env() -> None:
    env_path = _REPO_ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def _require_local_credentials() -> None:
    missing = [
        name
        for name, val in (
            ("OVALEDGE_BASE_URL", os.environ.get("OVALEDGE_BASE_URL", "")),
            ("OVALEDGE_USER_TOKEN", os.environ.get("OVALEDGE_USER_TOKEN", "")),
            ("OVALEDGE_USER_SECRET", os.environ.get("OVALEDGE_USER_SECRET", "")),
        )
        if not str(val).strip()
    ]
    if missing:
        print(
            "Missing required local HTTP MCP credentials/configuration.\n"
            "Set required values in repo .env or export before starting oe-mcp-http "
            "(same values as ovaledge-local stdio).",
            file=sys.stderr,
        )
        raise SystemExit(1)


def main() -> None:
    configure_runtime_observability()
    _load_repo_env()
    # Override .env AUTH_MODE=remote_credentials — local HTTP shares one cached JWT (stdio path).
    os.environ["AUTH_MODE"] = "local"
    os.environ.setdefault("MCP_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    os.environ.setdefault("MCP_HTTP_STATELESS", "false")
    _require_local_credentials()

    icon_src = resolve_mcp_icon_src()
    icon_base = brand_icon_http_base()
    host = urlparse(icon_base).hostname if icon_base else None
    if host in ("127.0.0.1", "localhost", "::1") and not (
        os.environ.get("MCP_BRAND_ICON_BASE_URL", "").strip()
    ):
        print(
            "Note: Cursor usually cannot show MCP icons from http://127.0.0.1.\n"
            "Set MCP_BRAND_ICON_BASE_URL=https://<your-api-id>.execute-api.<region>.amazonaws.com "
            "in .env (deployed /brand route) to see the OvalEdge logo.",
            file=sys.stderr,
        )
    elif icon_src and icon_src.startswith("http"):
        print(f"MCP icon URL: {icon_src}", file=sys.stderr)
    elif brand_icon_public_url():
        print(f"MCP icon URL: {brand_icon_public_url()}", file=sys.stderr)

    uvicorn.run(
        "entrypoints.lambda_handler:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
