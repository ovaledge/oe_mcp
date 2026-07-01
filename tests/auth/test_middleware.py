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


def test_mcp_http_requires_tls_for_bearer(minimal_remote_app: FastAPI) -> None:
    with TestClient(minimal_remote_app, base_url="http://testserver") as client:
        r = client.post("/mcp", headers={"Authorization": "Bearer token"})
    assert r.status_code == 400
    assert r.json()["error"] == "tls_required"


def test_mcp_with_bearer_calls_verify_and_exchange(minimal_remote_app: FastAPI) -> None:
    with TestClient(minimal_remote_app) as client:
        with (
            patch(
                "server.auth.middleware.verify_oauth_access_token",
                new=AsyncMock(return_value={"sub": "u"}),
            ),
            patch(
                "server.auth.middleware.exchange_oauth_access_token",
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
            patch("server.auth.middleware.exchange_oauth_access_token", exchange),
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


async def test_lambda_health_route_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke: Lambda health handler returns healthy payload."""
    monkeypatch.setattr(settings, "auth_mode", "remote")
    from entrypoints.lambda_handler import health

    resp = await health()
    assert json.loads(resp.body)["status"] == "healthy"
