from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.auth import bearer_jwt, oauth_discovery


@pytest.fixture(autouse=True)
def clear_caches() -> Generator[None, None, None]:
    oauth_discovery.clear_metadata_cache()
    bearer_jwt.clear_jwks_cache()
    yield
    oauth_discovery.clear_metadata_cache()
    bearer_jwt.clear_jwks_cache()


@pytest.mark.asyncio
async def test_verify_oauth_access_token_decodes(monkeypatch: pytest.MonkeyPatch) -> None:
    # No client_id → JWKS path (introspect not configured).
    monkeypatch.setattr("server.config.settings.oauth_client_id", "")
    monkeypatch.setattr("server.config.settings.oauth_audience", "api://my-api")
    monkeypatch.setattr(
        "server.config.settings.oauth_issuer",
        "https://idp.example.com",
    )

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
    assert "audience" in dec.call_args.kwargs


@pytest.mark.asyncio
async def test_verify_jwt_without_audience_skips_aud_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("server.config.settings.oauth_client_id", "")
    monkeypatch.setattr("server.config.settings.oauth_audience", "")
    monkeypatch.setattr("server.config.settings.oauth_issuer", "https://idp.example.com")

    claims = {"sub": "user-1"}
    fake_meta = {
        "issuer": "https://idp.example.com",
        "jwks_uri": "https://idp.example.com/jwks",
    }
    unverified = {"iss": "https://idp.example.com"}
    with (
        patch(
            "server.auth.bearer_jwt.get_authorization_server_metadata_for_base",
            new=AsyncMock(return_value=fake_meta),
        ),
        patch("server.auth.bearer_jwt.jwt.get_unverified_claims", return_value=unverified),
        patch("server.auth.bearer_jwt._get_jwks", new=AsyncMock(return_value={"keys": []})),
        patch("server.auth.bearer_jwt.jwt.decode", return_value=claims) as dec,
    ):
        out = await bearer_jwt.verify_oauth_access_token("header.payload.sig")

    assert out == claims
    assert "audience" not in dec.call_args.kwargs


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
async def test_verify_rejects_issuer_not_in_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("server.config.settings.oauth_client_id", "")
    monkeypatch.setattr("server.config.settings.oauth_audience", "api://my-api")
    monkeypatch.setattr("server.config.settings.oauth_issuer", "https://trusted.example.com")
    unverified = {"iss": "https://evil.example.com", "aud": "api://my-api"}
    with patch("server.auth.bearer_jwt.jwt.get_unverified_claims", return_value=unverified):
        with pytest.raises(ValueError, match="not in the OAuth allowlist"):
            await bearer_jwt.verify_oauth_access_token("header.payload.sig")


@pytest.mark.asyncio
async def test_verify_prefers_introspection_when_client_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("server.config.settings.oauth_client_id", "0oa-test")
    monkeypatch.setattr("server.config.settings.oauth_client_secret", "secret")
    monkeypatch.setattr(
        "server.config.settings.oauth_introspection_url",
        "https://idp.example.com/oauth2/default/v1/introspect",
    )
    monkeypatch.setattr(
        "server.config.settings.oauth_issuer", "https://idp.example.com/oauth2/default"
    )
    monkeypatch.setattr("server.config.settings.oauth_audience", "")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "active": True,
        "iss": "https://idp.example.com/oauth2/default",
        "sub": "user@example.com",
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("server.auth.bearer_jwt.httpx.AsyncClient", return_value=mock_client),
        patch(
            "server.auth.bearer_jwt._verify_jwt_access_token",
            new=AsyncMock(side_effect=AssertionError("should not use JWKS")),
        ),
    ):
        # JWT-shaped token still uses introspect first when client_id is set.
        out = await bearer_jwt.verify_oauth_access_token("header.payload.sig")

    assert out["active"] is True
    mock_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_opaque_via_introspection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.config.settings.oauth_client_id", "0oa-test")
    monkeypatch.setattr("server.config.settings.oauth_client_secret", "secret")
    monkeypatch.setattr(
        "server.config.settings.oauth_introspection_url",
        "https://idp.example.com/oauth2/default/v1/introspect",
    )
    monkeypatch.setattr("server.config.settings.oauth_issuer", "https://idp.example.com/oauth2/default")
    monkeypatch.setattr("server.config.settings.oauth_audience", "")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "active": True,
        "iss": "https://idp.example.com/oauth2/default",
        "sub": "user@example.com",
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.bearer_jwt.httpx.AsyncClient", return_value=mock_client):
        out = await bearer_jwt.verify_oauth_access_token("opaque-access-token")

    assert out["active"] is True
    assert out["sub"] == "user@example.com"
    mock_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_opaque_rejects_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("server.config.settings.oauth_client_id", "0oa-test")
    monkeypatch.setattr("server.config.settings.oauth_client_secret", "secret")
    monkeypatch.setattr(
        "server.config.settings.oauth_introspection_url",
        "https://idp.example.com/introspect",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"active": False}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("server.auth.bearer_jwt.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="not active"):
            await bearer_jwt.verify_oauth_access_token("dead-token")
