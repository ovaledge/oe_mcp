import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.auth.credentials_cache import reset_default_credentials_cache
from server.auth.jwt_util import encode_hs256
from server.auth.token_exchange import (
    TokenExchangeError,
    exchange_client_credentials,
    exchange_oauth_access_token,
    exchange_user_credentials,
    get_or_refresh_oauth_exchanged_token,
)


@pytest.mark.asyncio
async def test_exchange_oauth_access_token_extracts_access_token() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "oe-from-okta"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
        token = await exchange_oauth_access_token("oauth-jwt")

    assert token == "oe-from-okta"
    mock_client.post.assert_awaited_once()
    assert mock_client.post.await_args.kwargs["json"]["userToken"] == "oauth-jwt"


@pytest.mark.asyncio
async def test_exchange_oauth_access_token_failure_raises() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "boom"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(TokenExchangeError):
            await exchange_oauth_access_token("x")


@pytest.mark.asyncio
async def test_exchange_client_credentials_extracts_token_field() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"token": "machine-token"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
        token = await exchange_client_credentials()

    assert token == "machine-token"
    body = mock_client.post.await_args.kwargs["json"]
    assert body["userToken"] == "test-user-token"
    assert body["userSecret"] == "test-user-secret"


@pytest.mark.asyncio
async def test_exchange_rejects_empty_200_body() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b""
    mock_response.text = ""

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(TokenExchangeError, match="empty body"):
            await exchange_oauth_access_token("oauth-jwt")


@pytest.mark.asyncio
async def test_exchange_handles_raw_text_token_response() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "raw.jwt.token"
    mock_response.json.side_effect = ValueError("not json")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
        token = await exchange_oauth_access_token("oauth-jwt")

    assert token == "raw.jwt.token"


@pytest.mark.asyncio
async def test_exchange_user_credentials_extracts_token() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"token": "oe-from-user-creds"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
        token = await exchange_user_credentials("my-token", "my-secret")

    assert token == "oe-from-user-creds"
    body = mock_client.post.await_args.kwargs["json"]
    assert body["userToken"] == "my-token"
    assert body["userSecret"] == "my-secret"


@pytest.mark.asyncio
async def test_exchange_user_credentials_401_sets_status() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "nope"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(TokenExchangeError) as ei:
            await exchange_user_credentials("t", "s")

    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_exchange_user_credentials_5xx_sets_status() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "upstream"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(TokenExchangeError) as ei:
            await exchange_user_credentials("t", "s")

    assert ei.value.status_code == 503


@pytest.mark.asyncio
async def test_get_or_refresh_oauth_exchanged_token_caches() -> None:
    reset_default_credentials_cache()
    oe_jwt = encode_hs256({"exp": int(time.time()) + 3600})
    ex = AsyncMock(return_value=oe_jwt)
    try:
        with patch("server.auth.token_exchange.exchange_oauth_access_token", ex):
            first = await get_or_refresh_oauth_exchanged_token("idp-token")
            second = await get_or_refresh_oauth_exchanged_token("idp-token")
        assert first == second == oe_jwt
        ex.assert_awaited_once()
    finally:
        reset_default_credentials_cache()


@pytest.mark.asyncio
async def test_get_or_refresh_oauth_exchanged_token_distinct_tokens_dont_collide() -> None:
    reset_default_credentials_cache()
    oe_jwt = encode_hs256({"exp": int(time.time()) + 3600})
    ex = AsyncMock(return_value=oe_jwt)
    try:
        with patch("server.auth.token_exchange.exchange_oauth_access_token", ex):
            await get_or_refresh_oauth_exchanged_token("token-a")
            await get_or_refresh_oauth_exchanged_token("token-b")
        assert ex.await_count == 2
    finally:
        reset_default_credentials_cache()
