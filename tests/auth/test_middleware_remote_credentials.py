"""AUTH_MODE=remote_credentials — headers, TLS, OvalEdge JWT."""

import time
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from server.auth.middleware import AuthMiddleware
from server.auth.remote_credentials_discovery import router as remote_credentials_discovery_router
from server.auth.token_exchange import TokenExchangeError
from server.config import settings
from server.constants import HEADER_OE_USER_SECRET, HEADER_OE_USER_TOKEN


@pytest.fixture
def rc_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr(settings, "auth_mode", "remote_credentials")
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post("/mcp")
    async def placeholder_mcp() -> dict:
        return {"ok": True}

    @app.get("/mcp")
    async def placeholder_mcp_get() -> dict:
        return {"ok": True}

    app.include_router(remote_credentials_discovery_router)

    return app


@pytest.fixture(autouse=True)
def _https_and_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr("server.auth.middleware._request_is_https", lambda _r: True)
    from server.auth.credentials_cache import reset_default_credentials_cache

    reset_default_credentials_cache()
    yield
    reset_default_credentials_cache()


def test_well_known_oauth_skips_auth(rc_app: FastAPI) -> None:
    with TestClient(rc_app) as client:
        r = client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    assert "issuer" in r.json()


def test_get_mcp_event_stream_without_headers_401(rc_app: FastAPI) -> None:
    """SSE-style probe must not receive the browser JSON help (200)."""
    with TestClient(rc_app) as client:
        r = client.get("/mcp", headers={"Accept": "text/event-stream"})
    assert r.status_code == 401


def test_get_mcp_without_accept_still_help_json(rc_app: FastAPI) -> None:
    with TestClient(rc_app) as client:
        r = client.get("/mcp")
    assert r.status_code == 200
    assert "message" in r.json()


def test_missing_headers_401(rc_app: FastAPI) -> None:
    with TestClient(rc_app) as client:
        r = client.post("/mcp")
    assert r.status_code == 401


def test_missing_secret_401(rc_app: FastAPI) -> None:
    with TestClient(rc_app) as client:
        r = client.post("/mcp", headers={HEADER_OE_USER_TOKEN: "t"})
    assert r.status_code == 401


def test_credentials_post_requires_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "remote_credentials")
    monkeypatch.setattr("server.auth.middleware._request_is_https", lambda _r: False)
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.post("/mcp")
    async def _p() -> dict:
        return {"ok": True}

    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            headers={HEADER_OE_USER_TOKEN: "t", HEADER_OE_USER_SECRET: "s"},
        )
    assert r.status_code == 400
    assert r.json()["error"] == "tls_required"


def test_upstream_exchange_502(rc_app: FastAPI) -> None:
    with (
        TestClient(rc_app) as client,
        patch(
            "server.auth.middleware.get_or_refresh_user_token",
            new=AsyncMock(side_effect=TokenExchangeError("boom", status_code=500)),
        ),
    ):
        r = client.post(
            "/mcp",
            headers={HEADER_OE_USER_TOKEN: "t", HEADER_OE_USER_SECRET: "s"},
        )
    assert r.status_code == 502


def test_bad_credentials_401(rc_app: FastAPI) -> None:
    with (
        TestClient(rc_app) as client,
        patch(
            "server.auth.middleware.get_or_refresh_user_token",
            new=AsyncMock(side_effect=TokenExchangeError("nope", status_code=401)),
        ),
    ):
        r = client.post(
            "/mcp",
            headers={HEADER_OE_USER_TOKEN: "t", HEADER_OE_USER_SECRET: "s"},
        )
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_credentials"


def test_success_with_valid_oe_jwt(rc_app: FastAPI) -> None:
    valid = jose_jwt.encode({"exp": int(time.time()) + 3600, "sub": "s"}, "k", algorithm="HS256")
    with (
        TestClient(rc_app) as client,
        patch(
            "server.auth.middleware.get_or_refresh_user_token",
            new=AsyncMock(return_value=valid),
        ),
    ):
        r = client.post(
            "/mcp",
            headers={HEADER_OE_USER_TOKEN: "t", HEADER_OE_USER_SECRET: "s"},
        )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_malformed_oe_token_401(rc_app: FastAPI) -> None:
    with (
        TestClient(rc_app) as client,
        patch(
            "server.auth.middleware.get_or_refresh_user_token",
            new=AsyncMock(return_value="not-a-jwt"),
        ),
    ):
        r = client.post(
            "/mcp",
            headers={HEADER_OE_USER_TOKEN: "t", HEADER_OE_USER_SECRET: "s"},
        )
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_token"


def test_whitespace_inside_header_value_401(rc_app: FastAPI) -> None:
    with TestClient(rc_app) as client:
        r = client.post(
            "/mcp",
            headers={
                HEADER_OE_USER_TOKEN: "tok en",
                HEADER_OE_USER_SECRET: "sec",
            },
        )
    assert r.status_code == 401
