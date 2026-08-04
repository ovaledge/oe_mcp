"""HTTP route for AUTH_MODE=remote OAuth AS metadata (server/auth/metadata.py)."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth.metadata import router as metadata_router
from server.config import settings


def _client(base_url: str = "http://testserver") -> TestClient:
    app = FastAPI()
    app.include_router(metadata_router)
    return TestClient(app, base_url=base_url)


def test_oauth_metadata_proxies_idp_and_adds_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mcp_public_base_url", "https://mcp.example.com")
    idp_doc = {
        "issuer": "https://idp.example.com/",
        "authorization_endpoint": "https://idp.example.com/authorize",
        "token_endpoint": "https://idp.example.com/token",
        "jwks_uri": "https://idp.example.com/jwks",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["openid"],
    }
    with patch(
        "server.auth.metadata.get_authorization_server_metadata",
        new=AsyncMock(return_value=idp_doc),
    ):
        with _client() as client:
            r = client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    data = r.json()
    assert data["issuer"] == "https://mcp.example.com"
    assert data["registration_endpoint"] == "https://mcp.example.com/register"
    assert data["authorization_endpoint"] == idp_doc["authorization_endpoint"]
    assert data["jwks_uri"] == idp_doc["jwks_uri"]


def test_oauth_metadata_uses_request_base_url_when_public_base_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mcp_public_base_url", "")
    idp_doc = {
        "issuer": "https://idp.example.com/",
        "authorization_endpoint": "https://idp.example.com/authorize",
        "token_endpoint": "https://idp.example.com/token",
        "jwks_uri": "https://idp.example.com/jwks",
    }
    with patch(
        "server.auth.metadata.get_authorization_server_metadata",
        new=AsyncMock(return_value=idp_doc),
    ):
        with _client(base_url="https://from-request.test/") as client:
            r = client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    assert r.json()["registration_endpoint"] == "https://from-request.test/register"


def test_oauth_metadata_returns_503_when_discovery_fails() -> None:
    from server.auth.oauth_discovery import OAuthDiscoveryError

    with patch(
        "server.auth.metadata.get_authorization_server_metadata",
        new=AsyncMock(side_effect=OAuthDiscoveryError("oauth_issuer is not set")),
    ):
        with _client() as client:
            r = client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 503
    assert "oauth_issuer" in r.json()["detail"]


def test_openid_configuration_and_protected_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mcp_public_base_url", "https://mcp.example.com")
    monkeypatch.setattr(settings, "oauth_issuer", "https://idp.example.com/oauth2/default")
    monkeypatch.setattr(settings, "oauth_scopes", "openid profile email")
    idp_doc = {
        "issuer": "https://idp.example.com/oauth2/default",
        "authorization_endpoint": "https://idp.example.com/authorize",
        "token_endpoint": "https://idp.example.com/token",
        "jwks_uri": "https://idp.example.com/jwks",
    }
    with patch(
        "server.auth.metadata.get_authorization_server_metadata",
        new=AsyncMock(return_value=idp_doc),
    ):
        with _client() as client:
            oidc = client.get("/.well-known/openid-configuration")
            pr = client.get("/.well-known/oauth-protected-resource/mcp")
    assert oidc.status_code == 200
    assert oidc.json()["issuer"] == "https://mcp.example.com"
    assert oidc.json()["registration_endpoint"] == "https://mcp.example.com/register"
    assert pr.status_code == 200
    body = pr.json()
    assert body["resource"] == "https://mcp.example.com/mcp"
    assert body["authorization_servers"] == ["https://mcp.example.com"]
