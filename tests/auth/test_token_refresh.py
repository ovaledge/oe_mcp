"""JWT cache + expiry logic for local stdio auth."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from server.auth import context as auth_context
from server.auth.jwt_util import encode_hs256
from server.auth.token_exchange import (
    JWT_REFRESH_LEEWAY_SECONDS,
    get_or_refresh_local_token,
    is_token_expiring,
)


@pytest.fixture(autouse=True)
def _reset_local_jwt_cache() -> object:
    token = auth_context.current_oe_jwt.set("")
    auth_context.local_cached_oe_jwt = ""
    yield
    auth_context.local_cached_oe_jwt = ""
    auth_context.current_oe_jwt.reset(token)


def _jwt_expires_in(seconds: int) -> str:
    exp = int(time.time()) + seconds
    return encode_hs256({"exp": exp, "sub": "t"})


def test_is_token_expiring_false_when_no_exp_claim() -> None:
    opaque = encode_hs256({"sub": "opaque"})
    assert is_token_expiring(opaque) is False


def test_is_token_expiring_true_when_expired() -> None:
    past = encode_hs256({"exp": int(time.time()) - 60})
    assert is_token_expiring(past) is True


def test_is_token_expiring_true_within_leeway() -> None:
    soon = encode_hs256(
        {"exp": int(time.time()) + max(1, JWT_REFRESH_LEEWAY_SECONDS // 2)},
    )
    assert is_token_expiring(soon) is True


def test_is_token_expiring_false_when_fresh() -> None:
    fresh = _jwt_expires_in(3600)
    assert is_token_expiring(fresh) is False


def test_is_token_expiring_invalid_jwt_returns_true() -> None:
    assert is_token_expiring("not-a-jwt") is True


@pytest.mark.asyncio
async def test_get_or_refresh_uses_cache_without_exchange() -> None:
    cached = _jwt_expires_in(3600)
    auth_context.local_cached_oe_jwt = cached
    with patch(
        "server.auth.token_exchange.exchange_client_credentials",
        new_callable=AsyncMock,
    ) as ex:
        out = await get_or_refresh_local_token()
    assert out == cached
    ex.assert_not_awaited()
    assert auth_context.current_oe_jwt.get() == cached


@pytest.mark.asyncio
async def test_get_or_refresh_exchanges_when_cached_token_expired() -> None:
    auth_context.local_cached_oe_jwt = encode_hs256(
        {"exp": int(time.time()) - 120},
    )
    new_t = _jwt_expires_in(7200)
    with patch(
        "server.auth.token_exchange.exchange_client_credentials",
        new_callable=AsyncMock,
        return_value=new_t,
    ) as ex:
        out = await get_or_refresh_local_token()
    assert out == new_t
    ex.assert_awaited_once()
    assert auth_context.local_cached_oe_jwt == new_t
    assert auth_context.current_oe_jwt.get() == new_t


@pytest.mark.asyncio
async def test_get_or_refresh_exchanges_when_cache_empty() -> None:
    new_t = _jwt_expires_in(3600)
    with patch(
        "server.auth.token_exchange.exchange_client_credentials",
        new_callable=AsyncMock,
        return_value=new_t,
    ) as ex:
        out = await get_or_refresh_local_token()
    assert out == new_t
    ex.assert_awaited_once()
    assert auth_context.local_cached_oe_jwt == new_t
    assert auth_context.current_oe_jwt.get() == new_t


@pytest.mark.asyncio
async def test_get_or_refresh_single_exchange_under_concurrency() -> None:
    new_t = _jwt_expires_in(3600)
    with patch(
        "server.auth.token_exchange.exchange_client_credentials",
        new_callable=AsyncMock,
        return_value=new_t,
    ) as ex:
        import asyncio

        results = await asyncio.gather(*[get_or_refresh_local_token() for _ in range(8)])
    assert all(r == new_t for r in results)
    ex.assert_awaited_once()
