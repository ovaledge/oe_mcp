from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.auth import oauth_discovery
from server.auth.oauth_discovery import OAuthDiscoveryError, get_authorization_server_metadata


@pytest.fixture(autouse=True)
def clear_discovery_cache() -> Generator[None, None, None]:
    oauth_discovery.clear_metadata_cache()
    yield
    oauth_discovery.clear_metadata_cache()


@pytest.mark.asyncio
async def test_discovery_prefers_oidc_document(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.config.settings.oauth_issuer", "https://idp.example.com/realms/r1")

    oidc_doc = {
        "issuer": "https://idp.example.com/realms/r1",
        "authorization_endpoint": "https://idp.example.com/realms/r1/protocol/openid-connect/auth",
        "token_endpoint": "https://idp.example.com/realms/r1/protocol/openid-connect/token",
        "jwks_uri": "https://idp.example.com/realms/r1/protocol/openid-connect/certs",
    }

    async def fake_get(url: str) -> MagicMock:
        r = MagicMock()
        if "openid-configuration" in url:
            r.status_code = 200
            r.json = MagicMock(return_value=oidc_doc)
        else:
            r.status_code = 404
            r.json = MagicMock(return_value={})
        return r

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.oauth_discovery.httpx.AsyncClient", return_value=mock_client):
        meta = await get_authorization_server_metadata()

    assert meta["issuer"] == oidc_doc["issuer"]
    assert mock_client.get.await_count == 1


@pytest.mark.asyncio
async def test_discovery_falls_back_to_rfc8414(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.config.settings.oauth_issuer", "https://as.example.com/custom")

    oauth_doc = {
        "issuer": "https://as.example.com/custom",
        "authorization_endpoint": "https://as.example.com/custom/authorize",
        "token_endpoint": "https://as.example.com/custom/token",
        "jwks_uri": "https://as.example.com/custom/jwks",
    }

    call_n = 0

    async def fake_get(url: str) -> MagicMock:
        nonlocal call_n
        call_n += 1
        r = MagicMock()
        if "openid-configuration" in url:
            r.status_code = 404
        else:
            r.status_code = 200
            r.json = MagicMock(return_value=oauth_doc)
        return r

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.oauth_discovery.httpx.AsyncClient", return_value=mock_client):
        meta = await get_authorization_server_metadata()

    assert meta["jwks_uri"] == oauth_doc["jwks_uri"]
    assert call_n == 2


@pytest.mark.asyncio
async def test_discovery_raises_when_issuer_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.config.settings.oauth_issuer", "   ")
    with pytest.raises(OAuthDiscoveryError, match="oauth_issuer"):
        await get_authorization_server_metadata()


@pytest.mark.asyncio
async def test_discovery_caches_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.config.settings.oauth_issuer", "https://idp.example.com")

    doc = {
        "issuer": "https://idp.example.com",
        "authorization_endpoint": "https://idp.example.com/a",
        "token_endpoint": "https://idp.example.com/t",
        "jwks_uri": "https://idp.example.com/jwks",
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = doc

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.oauth_discovery.httpx.AsyncClient", return_value=mock_client):
        await get_authorization_server_metadata()
        await get_authorization_server_metadata()

    assert mock_client.get.await_count == 1
