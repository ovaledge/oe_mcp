import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth.middleware import AuthMiddleware
from server.config import settings


@pytest.fixture
def minimal_remote_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """FastAPI app with auth middleware only (no MCP mount — avoids streamable HTTP lifespan)."""
    monkeypatch.setattr(settings, "auth_mode", "remote")
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post("/mcp")
    async def placeholder_mcp() -> dict:
        return {"ok": True}

    return app


def test_health_style_route_not_in_unprotected_returns_401(minimal_remote_app: FastAPI) -> None:
    with TestClient(minimal_remote_app) as client:
        r = client.post("/mcp", headers={"x-forwarded-proto": "https"})
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers
    assert "resource_metadata=" in r.headers["WWW-Authenticate"]


def test_mcp_http_requires_tls_for_bearer(minimal_remote_app: FastAPI) -> None:
    with TestClient(minimal_remote_app, base_url="http://testserver") as client:
        r = client.post("/mcp", headers={"Authorization": "Bearer token"})
    assert r.status_code == 400
    assert r.json()["error"] == "tls_required"


def test_mcp_with_bearer_calls_verify_and_exchange(
    minimal_remote_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ovaledge_remote_forward_idp_token", False)
    with TestClient(minimal_remote_app) as client:
        with (
            patch(
                "server.auth.middleware.verify_oauth_access_token",
                new=AsyncMock(return_value={"sub": "u"}),
            ),
            patch(
                "server.auth.middleware.get_or_refresh_oauth_exchanged_token",
                new=AsyncMock(return_value="oe-jwt"),
            ),
        ):
            r = client.post(
                "/mcp",
                headers={
                    "Authorization": "Bearer okta-token",
                    "x-forwarded-proto": "https",
                },
            )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_mcp_forward_idp_skips_exchange(
    minimal_remote_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ovaledge_remote_forward_idp_token", True)
    exchange = AsyncMock()
    with TestClient(minimal_remote_app) as client:
        with (
            patch(
                "server.auth.middleware.verify_oauth_access_token",
                new=AsyncMock(return_value={"sub": "u"}),
            ),
            patch("server.auth.middleware.get_or_refresh_oauth_exchanged_token", exchange),
        ):
            r = client.post(
                "/mcp",
                headers={
                    "Authorization": "Bearer idp-token",
                    "x-forwarded-proto": "https",
                },
            )
    assert r.status_code == 200
    exchange.assert_not_called()


def test_invalid_token_hides_exception_details(minimal_remote_app: FastAPI) -> None:
    """Clients must not receive raw exception / stack details (py/stack-trace-exposure)."""
    leak = "Signature verification failed: /secret/path/jwks.json line 42"
    with (
        TestClient(minimal_remote_app) as client,
        patch(
            "server.auth.middleware.verify_oauth_access_token",
            new=AsyncMock(side_effect=ValueError(leak)),
        ),
    ):
        r = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer bad-token",
                "x-forwarded-proto": "https",
            },
        )
    assert r.status_code == 401
    body = r.json()
    assert body["error"] == "invalid_token"
    assert body["error_description"] == "Invalid or expired access token"
    assert leak not in body["error_description"]
    assert leak not in r.headers.get("WWW-Authenticate", "")


def test_oauth_discovery_error_hides_exception_details(minimal_remote_app: FastAPI) -> None:
    from server.auth.oauth_discovery import OAuthDiscoveryError

    leak = "oauth_issuer probe failed at https://internal.idp/metadata"
    with (
        TestClient(minimal_remote_app) as client,
        patch(
            "server.auth.middleware.verify_oauth_access_token",
            new=AsyncMock(side_effect=OAuthDiscoveryError(leak)),
        ),
    ):
        r = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer tok",
                "x-forwarded-proto": "https",
            },
        )
    assert r.status_code == 503
    body = r.json()
    assert body["error"] == "server_error"
    assert body["error_description"] == "OAuth discovery unavailable"
    assert leak not in body["error_description"]


def test_token_exchange_error_hides_exception_details(
    minimal_remote_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    from server.auth.token_exchange import TokenExchangeError

    monkeypatch.setattr(settings, "ovaledge_remote_forward_idp_token", False)
    leak = "OvalEdge token exchange declined: internal stack detail"
    with (
        TestClient(minimal_remote_app) as client,
        patch(
            "server.auth.middleware.verify_oauth_access_token",
            new=AsyncMock(return_value={"sub": "u"}),
        ),
        patch(
            "server.auth.middleware.get_or_refresh_oauth_exchanged_token",
            new=AsyncMock(side_effect=TokenExchangeError(leak)),
        ),
    ):
        r = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer okta-token",
                "x-forwarded-proto": "https",
            },
        )
    assert r.status_code == 502
    body = r.json()
    assert body["error"] == "server_error"
    assert body["error_description"] == "Token exchange failed"
    assert leak not in body["error_description"]


async def test_lambda_health_route_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke: Lambda health handler returns healthy payload."""
    monkeypatch.setattr(settings, "auth_mode", "remote")
    from entrypoints.lambda_handler import health

    resp = await health()
    assert json.loads(resp.body)["status"] == "healthy"
