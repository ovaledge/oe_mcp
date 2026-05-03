"""Discovery stubs for AUTH_MODE=remote_credentials (MCP HTTP clients)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth.remote_credentials_discovery import router as remote_credentials_discovery_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(remote_credentials_discovery_router)
    return TestClient(app)


def test_oauth_authorization_server_metadata() -> None:
    with _client() as client:
        r = client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["issuer"], str)
    assert data["issuer"].startswith("http://")
    assert "authorization_endpoint" in data
    assert "token_endpoint" in data


def test_openid_configuration() -> None:
    with _client() as client:
        r = client.get("/.well-known/openid-configuration")
    assert r.status_code == 200
    assert "issuer" in r.json()


def test_oauth_protected_resource_mcp() -> None:
    with _client() as client:
        r = client.get("/.well-known/oauth-protected-resource/mcp")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"].endswith("/mcp")


def test_mcp_auth_declined_returns_rfc6749_shape() -> None:
    with _client() as client:
        r = client.post("/mcp-auth/declined")
    assert r.status_code == 400
    data = r.json()
    assert isinstance(data["error"], str)
    assert data["error"] == "unsupported_grant_type"
    assert isinstance(data["error_description"], str)
