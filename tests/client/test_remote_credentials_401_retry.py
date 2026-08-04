"""remote_credentials: evict cached OvalEdge JWT on 401; retry revoked-session 400."""

import time
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from server.auth import context as auth_context
from server.auth.credentials_cache import (
    CachedJwtEntry,
    credential_cache_key,
    get_default_credentials_cache,
    reset_default_credentials_cache,
)
from server.auth.jwt_util import encode_hs256
from server.client import OvalEdgeClient, OvalEdgeError
from server.config import settings


@pytest.fixture(autouse=True)
def _ctx(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setattr(settings, "auth_mode", "remote_credentials")
    reset_default_credentials_cache()
    t = auth_context.current_oe_jwt.set("")
    k = auth_context.current_oe_credential_cache_key.set("")
    ut = auth_context.current_oe_user_token.set("")
    us = auth_context.current_oe_user_secret.set("")
    yield
    auth_context.current_oe_jwt.reset(t)
    auth_context.current_oe_credential_cache_key.reset(k)
    auth_context.current_oe_user_token.reset(ut)
    auth_context.current_oe_user_secret.reset(us)
    reset_default_credentials_cache()


@pytest.mark.asyncio
async def test_remote_credentials_401_invalidates_cache() -> None:
    stale = encode_hs256({"exp": int(time.time()) + 5000, "sub": "a"})
    cache_key = credential_cache_key("ut", "us")
    cache = get_default_credentials_cache()
    await cache.set_entry(
        cache_key,
        CachedJwtEntry(jwt=stale, exp_epoch=int(time.time()) + 5000),
    )
    auth_context.current_oe_jwt.set(stale)
    auth_context.current_oe_credential_cache_key.set(cache_key)

    url = "https://mock.ovaledge.com/api/v1/example"
    req1 = httpx.Request("GET", url)
    mock_send = AsyncMock(
        side_effect=[
            httpx.Response(401, request=req1, json={"message": "Unauthorized"}),
        ]
    )
    with patch.object(httpx.AsyncClient, "send", mock_send):
        async with OvalEdgeClient() as client:
            with pytest.raises(OvalEdgeError) as ei:
                await client.get("/api/v1/example", params=None)

    assert ei.value.status_code == 401
    assert mock_send.await_count == 1
    assert await cache.get_entry(cache_key) is None


@pytest.mark.asyncio
async def test_remote_credentials_400_invalid_token_retries_after_refresh() -> None:
    stale = encode_hs256({"exp": int(time.time()) + 5000, "sub": "a"})
    fresh = encode_hs256({"exp": int(time.time()) + 5000, "sub": "b"})
    cache_key = credential_cache_key("utok", "usec")
    cache = get_default_credentials_cache()
    await cache.set_entry(
        cache_key,
        CachedJwtEntry(jwt=stale, exp_epoch=int(time.time()) + 5000),
    )
    auth_context.current_oe_jwt.set(stale)
    auth_context.current_oe_credential_cache_key.set(cache_key)
    auth_context.current_oe_user_token.set("utok")
    auth_context.current_oe_user_secret.set("usec")

    url = "https://mock.ovaledge.com/api/v1/example"
    req1 = httpx.Request("GET", url)
    req2 = httpx.Request("GET", url)
    mock_send = AsyncMock(
        side_effect=[
            httpx.Response(
                400,
                request=req1,
                json={"message": "Invalid token, please generate a new token"},
            ),
            httpx.Response(200, request=req2, json={"ok": True}),
        ]
    )
    with (
        patch.object(httpx.AsyncClient, "send", mock_send),
        patch(
            "server.auth.token_exchange.exchange_user_credentials",
            new_callable=AsyncMock,
            return_value=fresh,
        ) as ex,
    ):
        async with OvalEdgeClient() as client:
            out = await client.get("/api/v1/example", params=None)

    assert out == {"ok": True}
    assert mock_send.await_count == 2
    assert ex.await_count == 1
    entry_after = await cache.get_entry(cache_key)
    assert entry_after is not None
    assert entry_after.jwt == fresh
    assert auth_context.current_oe_jwt.get() == fresh


@pytest.mark.asyncio
async def test_remote_credentials_other_400_does_not_evict_cache() -> None:
    stale = encode_hs256({"exp": int(time.time()) + 5000, "sub": "a"})
    cache_key = credential_cache_key("utok", "usec")
    cache = get_default_credentials_cache()
    await cache.set_entry(
        cache_key,
        CachedJwtEntry(jwt=stale, exp_epoch=int(time.time()) + 5000),
    )
    auth_context.current_oe_jwt.set(stale)
    auth_context.current_oe_credential_cache_key.set(cache_key)

    url = "https://mock.ovaledge.com/api/v1/example"
    req1 = httpx.Request("GET", url)
    mock_send = AsyncMock(
        side_effect=[
            httpx.Response(
                400,
                request=req1,
                json={"message": "Malformed query"},
            ),
        ]
    )
    with patch.object(httpx.AsyncClient, "send", mock_send):
        async with OvalEdgeClient() as client:
            with pytest.raises(OvalEdgeError) as ei:
                await client.get("/api/v1/example", params=None)

    assert ei.value.status_code == 400
    assert mock_send.await_count == 1
    assert await cache.get_entry(cache_key) is not None
