#!/usr/bin/env python3
"""
Validate remote MCP configuration and dependencies (no server required for most checks).

Usage (from repo root):

  poetry run python scripts/validate_remote_mcp.py --all

  # With a real Auth0 access token (same audience as OAUTH_AUDIENCE):
  export OAUTH_TEST_ACCESS_TOKEN="$( ... curl oauth/token ... )"
  poetry run python scripts/validate_remote_mcp.py --ovaledge --token "$OAUTH_TEST_ACCESS_TOKEN"

  # Optional: MCP HTTP (uvicorn must be running on MCP_PUBLIC_BASE_URL):
  poetry run python scripts/validate_remote_mcp.py --mcp --token "$OAUTH_TEST_ACCESS_TOKEN"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any


def _redact_jwt(s: str, head: int = 24, tail: int = 16) -> str:
    s = s.strip()
    if len(s) < head + tail + 10:
        return "***"
    return f"{s[:head]}…{s[-tail:]}"


def _print_json(label: str, obj: Any) -> None:
    print(f"{label}:", json.dumps(obj, indent=2) if isinstance(obj, dict) else obj)


async def cmd_settings() -> None:
    from server.config import settings

    print("--- settings (from .env) ---")
    print("auth_mode:", settings.auth_mode)
    print("oauth_issuer:", settings.oauth_issuer or "(empty)")
    print("oauth_audience:", settings.oauth_audience or "(empty)")
    print("mcp_public_base_url:", settings.mcp_public_base_url or "(empty)")
    print("ovaledge_base_url:", settings.ovaledge_base_url)
    if settings.auth_mode != "remote":
        print("WARN: auth_mode is not 'remote'; HTTP MCP expects AUTH_MODE=remote")


async def cmd_discovery() -> None:
    from server.auth.oauth_discovery import OAuthDiscoveryError, get_authorization_server_metadata

    print("--- IdP discovery (oauth_issuer) ---")
    try:
        doc = await get_authorization_server_metadata()
    except OAuthDiscoveryError as e:
        print("FAIL:", e)
        return
    _print_json("issuer", doc.get("issuer"))
    _print_json("authorization_endpoint", doc.get("authorization_endpoint"))
    _print_json("token_endpoint", doc.get("token_endpoint"))
    _print_json("jwks_uri", doc.get("jwks_uri"))
    print("OK: discovery loaded")


async def cmd_ovaledge(token: str | None) -> None:
    import httpx

    from server.auth.token_exchange import TokenExchangeError, exchange_oauth_access_token
    from server.config import settings
    from server.constants import OVALEDGE_TOKEN_EXCHANGE_PATH

    base = settings.ovaledge_base_url.rstrip("/")
    path = OVALEDGE_TOKEN_EXCHANGE_PATH
    url = f"{base}{path}"

    print("--- OvalEdge token exchange probe ---")
    print("POST", url)
    print("userToken:", "set" if token else "(missing — pass --token or OAUTH_TEST_ACCESS_TOKEN)")

    probe_body = {"userToken": token or "__missing_token_probe__"}
    async with httpx.AsyncClient(timeout=settings.ovaledge_timeout_seconds) as client:
        r = await client.post(
            url,
            json=probe_body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    raw_len = len(r.content or b"")
    print("HTTP status:", r.status_code)
    print("response body length (bytes):", raw_len)
    preview = (r.text or "")[:800]
    print("response preview:", preview if preview else "(empty — backend returned no body)")

    if raw_len == 0:
        print("--- response headers (look for JWT in a custom header or cookie) ---")
        for key, value in r.headers.items():
            shown = value if len(value) < 200 else value[:197] + "..."
            print(f"  {key}: {shown}")
        print(
            "FAIL: Empty response body. The MCP server expects a JSON body or raw JWT text "
            "from POST /api/user/token/generate (see server/auth/token_exchange.py). "
            "If your OvalEdge build returns the token only in a header/cookie, align the "
            "backend with this contract or extend token_exchange to read that header."
        )
        if not token:
            print("Hint: with a real Auth0 access token, if body is still empty, the issue is "
                  "the OvalEdge service on ovaledge_base_url, not Auth0 or this MCP repo.")

    if not token:
        print("SKIP: exchange_oauth_access_token (no --token / OAUTH_TEST_ACCESS_TOKEN)")
        return

    if settings.ovaledge_remote_forward_idp_token:
        print(
            "SKIP: exchange_oauth_access_token — OVALEDGE_REMOTE_FORWARD_IDP_TOKEN=true "
            "(MCP uses IdP token directly; no token/generate call)."
        )
        return

    print("--- exchange_oauth_access_token() (same HTTP call as MCP middleware) ---")
    try:
        oe_jwt = await exchange_oauth_access_token(token)
        print("OK: OvalEdge JWT length:", len(oe_jwt), "preview:", _redact_jwt(oe_jwt))
    except TokenExchangeError as e:
        print("FAIL:", e)


async def cmd_mcp(token: str | None, mcp_url: str | None) -> None:
    import httpx

    from server.config import settings

    if not token:
        print("--- MCP HTTP --- SKIP (need --token or OAUTH_TEST_ACCESS_TOKEN)")
        return

    base = (mcp_url or settings.mcp_public_base_url or "http://127.0.0.1:8000").rstrip("/")
    url = f"{base}/mcp"
    print("--- MCP POST", url, "---")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            content=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"validate_remote_mcp","version":"0.0.1"}}}',
        )
    print("HTTP status:", r.status_code)
    print("response preview:", (r.text or "")[:1200])


async def main_async(args: argparse.Namespace) -> int:
    # Ensure repo root on path when run as script
    _root = os.path.join(os.path.dirname(__file__), "..")
    sys.path.insert(0, os.path.abspath(_root))

    from server.logging_config import configure_stderr_logging

    configure_stderr_logging()

    token = args.token or os.environ.get("OAUTH_TEST_ACCESS_TOKEN")

    run_all = args.all or not any(
        [args.settings, args.discovery, args.ovaledge, args.mcp]
    )

    if run_all or args.settings:
        await cmd_settings()
        print()
    if run_all or args.discovery:
        await cmd_discovery()
        print()
    if run_all or args.ovaledge:
        await cmd_ovaledge(token)
        print()
    if run_all or args.mcp:
        await cmd_mcp(token, args.mcp_url)

    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Validate remote MCP config and integrations")
    p.add_argument(
        "--all",
        action="store_true",
        help="Run settings + discovery + ovaledge (+ mcp if token)",
    )
    p.add_argument("--settings", action="store_true", help="Print loaded settings")
    p.add_argument("--discovery", action="store_true", help="Fetch OIDC discovery via oauth_issuer")
    p.add_argument("--ovaledge", action="store_true", help="Probe OvalEdge token exchange")
    p.add_argument("--mcp", action="store_true", help="POST initialize to MCP HTTP (needs token)")
    p.add_argument("--token", help="Auth0 access token (or env OAUTH_TEST_ACCESS_TOKEN)")
    p.add_argument(
        "--mcp-url",
        dest="mcp_url",
        help="Override MCP base URL (default: mcp_public_base_url or http://127.0.0.1:8000)",
    )
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
