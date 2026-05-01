"""Local MCP: OvalEdge 401 triggers JWT cache invalidation and one retry."""

import time
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from jose import jwt as jose_jwt

from server.auth import context as auth_context
from server.client import OvalEdgeClient, OvalEdgeError


@pytest.fixture(autouse=True)
def _reset_jwt_cache() -> Generator[None, None, None]:
    token = auth_context.current_oe_jwt.set("")
    auth_context.local_cached_oe_jwt = ""
    yield
    auth_context.local_cached_oe_jwt = ""
    auth_context.current_oe_jwt.reset(token)


@pytest.mark.asyncio
async def test_get_retries_once_on_401_then_succeeds() -> None:
    stale = jose_jwt.encode({"sub": "no-exp-claim"}, "k", algorithm="HS256")
    fresh = jose_jwt.encode(
        {"sub": "no-exp-claim", "exp": int(time.time()) + 3600},
        "k",
        algorithm="HS256",
    )
    auth_context.local_cached_oe_jwt = stale
    auth_context.current_oe_jwt.set(stale)

    url = "https://mock.ovaledge.com/api/v1/example"
    req1 = httpx.Request("GET", url)
    req2 = httpx.Request("GET", url)
    mock_send = AsyncMock(
        side_effect=[
            httpx.Response(401, request=req1, json={"message": "Unauthorized"}),
            httpx.Response(200, request=req2, json={"recovered": True}),
        ]
    )
    with (
        patch.object(httpx.AsyncClient, "send", mock_send),
        patch(
            "server.auth.token_exchange.exchange_client_credentials",
            new_callable=AsyncMock,
            return_value=fresh,
        ) as ex,
    ):
        async with OvalEdgeClient() as client:
            out = await client.get("/api/v1/example", params=None)

    assert out == {"recovered": True}
    assert mock_send.await_count == 2
    ex.assert_awaited_once()
    assert auth_context.local_cached_oe_jwt == fresh


@pytest.mark.asyncio
async def test_get_raises_when_401_persists_after_refresh() -> None:
    stale = jose_jwt.encode({"sub": "x"}, "k", algorithm="HS256")
    fresh = jose_jwt.encode(
        {"sub": "x", "exp": int(time.time()) + 3600},
        "k",
        algorithm="HS256",
    )
    auth_context.local_cached_oe_jwt = stale
    auth_context.current_oe_jwt.set(stale)

    url = "https://mock.ovaledge.com/api/v1/example"
    req1 = httpx.Request("GET", url)
    req2 = httpx.Request("GET", url)
    mock_send = AsyncMock(
        side_effect=[
            httpx.Response(401, request=req1, json={"message": "first"}),
            httpx.Response(401, request=req2, json={"message": "still bad"}),
        ]
    )
    with (
        patch.object(httpx.AsyncClient, "send", mock_send),
        patch(
            "server.auth.token_exchange.exchange_client_credentials",
            new_callable=AsyncMock,
            return_value=fresh,
        ),
    ):
        async with OvalEdgeClient() as client:
            with pytest.raises(OvalEdgeError) as ei:
                await client.get("/api/v1/example", params=None)

    assert ei.value.status_code == 401
    assert mock_send.await_count == 2
