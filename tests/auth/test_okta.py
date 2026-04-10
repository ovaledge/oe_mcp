from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.auth import okta


@pytest.mark.asyncio
async def test_verify_okta_token_decodes_with_jwks() -> None:
    claims = {"sub": "user-1", "email": "u@example.com"}
    fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA", "n": "abc", "e": "AQAB"}]}

    with patch.object(okta, "_get_jwks", new=AsyncMock(return_value=fake_jwks)):
        with patch("server.auth.okta.jwt.decode", return_value=claims) as dec:
            out = await okta.verify_okta_token("header.payload.sig")

    assert out == claims
    dec.assert_called_once()


@pytest.mark.asyncio
async def test_get_jwks_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    okta._jwks_cache = None  # noqa: SLF001
    okta._jwks_fetched_at = 0.0  # noqa: SLF001

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"keys": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("server.config.settings.okta_domain", "https://dev.okta.com")
    monkeypatch.setattr("server.config.settings.okta_auth_server_id", "aus1")

    with patch("server.auth.okta.httpx.AsyncClient", return_value=mock_client):
        j1 = await okta._get_jwks()  # noqa: SLF001
        j2 = await okta._get_jwks()  # noqa: SLF001

    assert j1 == j2 == {"keys": []}
    assert mock_client.get.await_count == 1
