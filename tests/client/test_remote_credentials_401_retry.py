"""remote_credentials: OvalEdge 401 invalidates user JWT cache; no in-request retry."""

import time
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from jose import jwt as jose_jwt

from server.auth import context as auth_context
from server.auth.credentials_cache import (
    CachedJwtEntry,
    credential_cache_key,
    get_default_credentials_cache,
    reset_default_credentials_cache,
)
from server.client import OvalEdgeClient, OvalEdgeError
from server.config import settings


@pytest.fixture(autouse=True)
def _ctx(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setattr(settings, "auth_mode", "remote_credentials")
    reset_default_credentials_cache()
    t = auth_context.current_oe_jwt.set("")
    k = auth_context.current_oe_credential_cache_key.set("")
    yield
    auth_context.current_oe_jwt.reset(t)
    auth_context.current_oe_credential_cache_key.reset(k)
    reset_default_credentials_cache()


@pytest.mark.asyncio
async def test_remote_credentials_401_invalidates_cache() -> None:
    stale = jose_jwt.encode({"exp": int(time.time()) + 5000, "sub": "a"}, "k", algorithm="HS256")
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
