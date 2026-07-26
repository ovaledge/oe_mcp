"""Live API integration tests — isolated from unit-test mocks in tests/conftest.py."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


def _load_dotenv() -> None:
    if not _ENV_FILE.is_file():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# Import after .env is applied (do not use tests/conftest mock URLs).
from server.auth.token_exchange import get_or_refresh_local_token  # noqa: E402
from server.config import settings  # noqa: E402
from server.constants import MCP_PATH_SOURCE_SYSTEM_ACCESS  # noqa: E402


@pytest.fixture(scope="session")
def api_available() -> bool:
    base = settings.ovaledge_base_url.rstrip("/")
    if base in ("https://mock.ovaledge.com", ""):
        return False
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            r = client.get(base + "/")
        return r.status_code < 500
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def auth_headers(api_available: bool) -> dict[str, str]:
    if not api_available:
        pytest.skip("OvalEdge not reachable at OVALEDGE_BASE_URL")

    preset = os.environ.get("OE_INTEGRATION_JWT", "").strip()
    if preset:
        return {"Authorization": f"{settings.ovaledge_http_auth_scheme} {preset}"}

    try:
        token = asyncio.run(get_or_refresh_local_token())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(
            "Could not obtain OvalEdge JWT. Set OE_INTEGRATION_JWT to a fresh JWT from "
            "OvalEdge (My Profile → API credentials → generate token), or fix "
            "OVALEDGE_USER_TOKEN / OVALEDGE_USER_SECRET in .env. "
            f"Detail: {exc}"
        )
    return {"Authorization": f"{settings.ovaledge_http_auth_scheme} {token}"}


@pytest.fixture
async def mcp_get(
    auth_headers: dict[str, str],
) -> Callable[[str, dict[str, object] | None], Awaitable[httpx.Response]]:
    """GET any OvalEdge MCP path under OVALEDGE_BASE_URL."""
    base = settings.ovaledge_base_url.rstrip("/")

    async def _get(path: str, params: dict[str, object] | None = None) -> httpx.Response:
        url = base + path
        async with httpx.AsyncClient(
            timeout=float(settings.ovaledge_timeout_seconds),
            follow_redirects=True,
        ) as client:
            return await client.get(url, params=params or {}, headers=auth_headers)

    return _get


@pytest.fixture
async def api_get(
    mcp_get: Callable[[str, dict[str, object] | None], Awaitable[httpx.Response]],
) -> Callable[[dict[str, object]], Awaitable[httpx.Response]]:
    """Backward-compatible helper for source-system-access live tests."""

    async def _get(params: dict[str, object]) -> httpx.Response:
        return await mcp_get(MCP_PATH_SOURCE_SYSTEM_ACCESS, params)

    return _get


def response_data(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    body = response.json()
    assert isinstance(body, dict)
    if body.get("ok") is False:
        raise AssertionError(f"API ok=false: {body}")
    data = body.get("data")
    assert isinstance(data, dict), f"Expected data object, got {body!r}"
    return data
