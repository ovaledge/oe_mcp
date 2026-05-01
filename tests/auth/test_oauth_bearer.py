from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.auth import bearer_jwt, oauth_discovery
from server.auth.oauth_discovery import OAuthDiscoveryError


@pytest.fixture(autouse=True)
def clear_caches() -> Generator[None, None, None]:
    oauth_discovery.clear_metadata_cache()
    bearer_jwt.clear_jwks_cache()
    yield
    oauth_discovery.clear_metadata_cache()
    bearer_jwt.clear_jwks_cache()


@pytest.mark.asyncio
async def test_verify_oauth_access_token_decodes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.config.settings.oauth_audience", "api://my-api")

    claims = {"sub": "user-1", "email": "u@example.com"}
    fake_meta = {
        "issuer": "https://idp.example.com",
        "jwks_uri": "https://idp.example.com/jwks",
    }
    fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA", "n": "abc", "e": "AQAB"}]}

    unverified = {"iss": "https://idp.example.com", "aud": "api://my-api"}
    with (
        patch(
            "server.auth.bearer_jwt.get_authorization_server_metadata_for_base",
            new=AsyncMock(return_value=fake_meta),
        ),
        patch("server.auth.bearer_jwt.jwt.get_unverified_claims", return_value=unverified),
        patch("server.auth.bearer_jwt._get_jwks", new=AsyncMock(return_value=fake_jwks)),
        patch("server.auth.bearer_jwt.jwt.decode", return_value=claims) as dec,
    ):
        out = await bearer_jwt.verify_oauth_access_token("header.payload.sig")

    assert out == claims
    dec.assert_called_once()


@pytest.mark.asyncio
async def test_get_jwks_fetches_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"keys": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.bearer_jwt.httpx.AsyncClient", return_value=mock_client):
        j1 = await bearer_jwt._get_jwks("https://idp.example.com/jwks")  # noqa: SLF001
        j2 = await bearer_jwt._get_jwks("https://idp.example.com/jwks")  # noqa: SLF001

    assert j1 == j2 == {"keys": []}
    assert mock_client.get.await_count == 1


@pytest.mark.asyncio
async def test_verify_requires_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.config.settings.oauth_audience", "  ")
    with pytest.raises(OAuthDiscoveryError, match="oauth_audience"):
        await bearer_jwt.verify_oauth_access_token("t")
