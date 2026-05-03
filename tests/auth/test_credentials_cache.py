"""Per-user JWT cache: LRU, expiry, single-flight, eviction."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt as jose_jwt

from server.auth.credentials_cache import (
    CachedJwtEntry,
    InMemoryCredentialsCache,
    credential_cache_key,
    reset_default_credentials_cache,
)
from server.auth.token_exchange import get_or_refresh_user_token, is_token_expiring
from server.constants import CREDENTIALS_REFRESH_LEEWAY_SECONDS


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    reset_default_credentials_cache()
    yield
    reset_default_credentials_cache()


def _fresh_jwt(seconds: int = 3600) -> str:
    exp = int(time.time()) + seconds
    return jose_jwt.encode({"exp": exp, "sub": "u"}, "k", algorithm="HS256")


@pytest.mark.asyncio
async def test_cache_hit_skips_exchange() -> None:
    t = _fresh_jwt()
    with patch(
        "server.auth.token_exchange.exchange_user_credentials",
        new_callable=AsyncMock,
        return_value=t,
    ) as ex:
        a = await get_or_refresh_user_token("ut", "us")
        b = await get_or_refresh_user_token("ut", "us")
    assert a == b == t
    ex.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_miss_then_exchange() -> None:
    t = _fresh_jwt()
    with patch(
        "server.auth.token_exchange.exchange_user_credentials",
        new_callable=AsyncMock,
        return_value=t,
    ) as ex:
        out = await get_or_refresh_user_token("a", "b")
    assert out == t
    ex.assert_awaited_once()
    assert credential_cache_key("a", "b") == credential_cache_key("a", "b")


@pytest.mark.asyncio
async def test_refresh_within_credentials_leeway() -> None:
    soon_exp = int(time.time()) + max(2, CREDENTIALS_REFRESH_LEEWAY_SECONDS // 2)
    old = jose_jwt.encode({"exp": soon_exp, "sub": "x"}, "k", algorithm="HS256")
    assert is_token_expiring(old, leeway_seconds=CREDENTIALS_REFRESH_LEEWAY_SECONDS) is True
    new = _fresh_jwt(7200)
    with patch(
        "server.auth.token_exchange.exchange_user_credentials",
        new_callable=AsyncMock,
        return_value=new,
    ) as ex:
        first = await get_or_refresh_user_token("x", "y")
        second = await get_or_refresh_user_token("x", "y")
    assert first == new
    assert second == new
    ex.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_refresh_single_exchange() -> None:
    new = _fresh_jwt()
    call_count = {"n": 0}

    async def counted(_ut: str, _us: str) -> str:
        call_count["n"] += 1
        await asyncio.sleep(0.05)
        return new

    with patch(
        "server.auth.token_exchange.exchange_user_credentials",
        side_effect=counted,
    ) as ex:
        results = await asyncio.gather(
            *[get_or_refresh_user_token("same", "cred") for _ in range(8)]
        )
    assert all(r == new for r in results)
    assert ex.await_count == 1
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_different_users_separate_cache() -> None:
    j1, j2 = _fresh_jwt(4000), _fresh_jwt(5000)

    async def ex(ut: str, us: str) -> str:
        if ut == "u1":
            return j1
        return j2

    with patch(
        "server.auth.token_exchange.exchange_user_credentials",
        side_effect=ex,
    ):
        a = await get_or_refresh_user_token("u1", "s")
        b = await get_or_refresh_user_token("u2", "s")
    assert a == j1 and b == j2


@pytest.mark.asyncio
async def test_lru_eviction_at_max_entries() -> None:
    cache = InMemoryCredentialsCache(max_entries=3)

    def key(i: int) -> str:
        return credential_cache_key(f"t{i}", "s")

    e1 = CachedJwtEntry(jwt=_fresh_jwt(8000), exp_epoch=int(time.time()) + 8000)
    e2 = CachedJwtEntry(jwt=_fresh_jwt(8001), exp_epoch=int(time.time()) + 8001)
    e3 = CachedJwtEntry(jwt=_fresh_jwt(8002), exp_epoch=int(time.time()) + 8002)
    e4 = CachedJwtEntry(jwt=_fresh_jwt(8003), exp_epoch=int(time.time()) + 8003)

    await cache.set_entry(key(1), e1)
    await cache.set_entry(key(2), e2)
    await cache.set_entry(key(3), e3)
    await cache.set_entry(key(4), e4)

    assert await cache.get_entry(key(1)) is None
    assert await cache.get_entry(key(2)) is not None
    assert await cache.get_entry(key(3)) is not None
    assert await cache.get_entry(key(4)) is not None


@pytest.mark.asyncio
async def test_delete_entry_removes() -> None:
    from server.auth.credentials_cache import get_default_credentials_cache

    t = _fresh_jwt()
    with patch(
        "server.auth.token_exchange.exchange_user_credentials",
        new_callable=AsyncMock,
        return_value=t,
    ):
        await get_or_refresh_user_token("u", "s")
    k = credential_cache_key("u", "s")
    cache = get_default_credentials_cache()
    assert await cache.get_entry(k) is not None
    await cache.delete_entry(k)
    assert await cache.get_entry(k) is None


@pytest.mark.asyncio
async def test_no_exp_jwt_stays_cached_until_invalidated() -> None:
    opaque = jose_jwt.encode({"sub": "opaque"}, "k", algorithm="HS256")
    assert is_token_expiring(opaque, leeway_seconds=CREDENTIALS_REFRESH_LEEWAY_SECONDS) is False

    with patch(
        "server.auth.token_exchange.exchange_user_credentials",
        new_callable=AsyncMock,
        return_value=opaque,
    ) as ex:
        a = await get_or_refresh_user_token("op", "sec")
        b = await get_or_refresh_user_token("op", "sec")
    assert a == b == opaque
    ex.assert_awaited_once()


@pytest.mark.asyncio
async def test_secret_rotation_changes_cache_key() -> None:
    j1, j2 = _fresh_jwt(4000), _fresh_jwt(5000)
    with patch(
        "server.auth.token_exchange.exchange_user_credentials",
        new_callable=AsyncMock,
        side_effect=[j1, j2],
    ) as ex:
        a = await get_or_refresh_user_token("u", "oldsecret")
        b = await get_or_refresh_user_token("u", "newsecret")
    assert a == j1 and b == j2
    assert ex.await_count == 2
