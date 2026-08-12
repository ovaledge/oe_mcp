#!/usr/bin/env python3
"""
Generate (or verify) an OvalEdge JWT for live integration tests, using `.env` config.

The integration suite needs `Authorization: <scheme> <JWT>` on every call. This script
performs the same client-credentials exchange the local MCP server does
(`POST /api/user/token/generate` with `userToken` + `userSecret` from `.env`),
validates that what came back is actually a JWT, and probes a real MCP endpoint with
it so a bad token fails here rather than as 20 confusing test skips.

Usage:
    poetry run python scripts/generate_oe_jwt.py            # exchange, verify, print export
    poetry run python scripts/generate_oe_jwt.py --jwt XYZ  # verify a JWT you pasted
    eval "$(poetry run python scripts/generate_oe_jwt.py --export)"

Exit codes: 0 verified · 1 exchange failed · 2 token returned but rejected by the API.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import re
import sys
import time

import httpx

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_JWT_RE = re.compile(r"^[\w-]+\.[\w-]+\.[\w-]+$")


def _load_dotenv() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

from server.config import settings  # noqa: E402
from server.constants import MCP_PATH_ASSET_EXPLORER  # noqa: E402


def _looks_like_jwt(token: str) -> bool:
    return bool(_JWT_RE.match(token.strip().strip('"')))


def _describe(token: str) -> str:
    from server.auth.token_exchange import jwt_exp_epoch

    exp = jwt_exp_epoch(token)
    if not exp:
        return "no exp claim"
    remaining = exp - int(time.time())
    if remaining <= 0:
        return f"EXPIRED {abs(remaining) // 60}m ago"
    return f"valid for {remaining // 60}m"


async def _exchange() -> str:
    from server.auth.token_exchange import TokenExchangeError, exchange_client_credentials

    if not settings.ovaledge_user_token or not settings.ovaledge_user_secret:
        raise SystemExit(
            "OVALEDGE_USER_TOKEN / OVALEDGE_USER_SECRET are not set in .env.\n"
            "Get them from OvalEdge: My Profile -> API credentials."
        )
    try:
        return await exchange_client_credentials()
    except TokenExchangeError as exc:
        print(f"Token exchange failed: {exc}", file=sys.stderr)
        print(
            "\nIf the endpoint returns an empty 200 for any input, this build does not\n"
            "issue JWTs from token+secret. Generate one in the OvalEdge UI\n"
            "(My Profile -> API credentials -> generate token) and re-run with --jwt.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


async def _verify(token: str) -> bool:
    """Probe a real MCP endpoint so an unusable token fails loudly here."""
    url = settings.ovaledge_base_url.rstrip("/") + MCP_PATH_ASSET_EXPLORER
    headers = {"Authorization": f"{settings.ovaledge_http_auth_scheme} {token}"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url, params={"page": 1, "limit": 1}, headers=headers)
    if response.status_code == 200:
        print(f"Verified against {MCP_PATH_ASSET_EXPLORER} (HTTP 200).", file=sys.stderr)
        return True
    print(
        f"Token rejected by {MCP_PATH_ASSET_EXPLORER}: "
        f"HTTP {response.status_code} {response.text[:200]}",
        file=sys.stderr,
    )
    return False


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jwt", help="Verify this JWT instead of exchanging credentials")
    parser.add_argument(
        "--export",
        action="store_true",
        help="Print only 'export OE_INTEGRATION_JWT=...' for eval()",
    )
    parser.add_argument(
        "--no-verify", action="store_true", help="Skip the live endpoint probe"
    )
    args = parser.parse_args()

    print(f"OvalEdge: {settings.ovaledge_base_url}", file=sys.stderr)
    token = (args.jwt or await _exchange()).strip().strip('"')

    if not _looks_like_jwt(token):
        print(
            f"Not a JWT (expected 3 dot-separated segments, got {token.count('.') + 1}).\n"
            "The OvalEdge user token is not itself a JWT — it must be exchanged.",
            file=sys.stderr,
        )
        return 1

    print(f"JWT obtained ({_describe(token)}).", file=sys.stderr)

    if not args.no_verify and not await _verify(token):
        return 2

    if args.export:
        print(f"export OE_INTEGRATION_JWT={token}")
    else:
        print(token)
        print(
            "\nRun the live suite with:\n"
            f'  export OE_INTEGRATION_JWT="{token[:18]}..."\n'
            "  poetry run pytest -c tests/integration/pytest.ini tests/integration "
            "-m integration",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
