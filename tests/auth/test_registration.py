"""Tests for POST /register (AUTH_MODE=remote)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth.registration import router as registration_router
from server.config import settings


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(registration_router)
    return TestClient(app)


def test_register_returns_configured_okta_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oauth_client_id", "0oa124ev9ftSqswfQ698")
    monkeypatch.setattr(settings, "oauth_client_secret", "")
    monkeypatch.setattr(settings, "oauth_scopes", "openid profile email")
    with _client() as client:
        r = client.post(
            "/register",
            json={
                "client_name": "Cursor",
                "redirect_uris": ["http://127.0.0.1:1234/callback"],
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["client_id"] == "0oa124ev9ftSqswfQ698"
    assert data["scope"] == "openid profile email"
    assert data["token_endpoint_auth_method"] == "none"
    assert "client_secret" not in data
    assert "client_id_issued_at" in data


def test_register_returns_secret_for_confidential_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "oauth_client_id", "0oa-confidential")
    monkeypatch.setattr(settings, "oauth_client_secret", "super-secret")
    monkeypatch.setattr(settings, "oauth_scopes", "openid")
    with _client() as client:
        r = client.post(
            "/register",
            json={
                "client_name": "Cursor",
                "redirect_uris": ["http://localhost:8787/callback"],
                "token_endpoint_auth_method": "none",
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["client_id"] == "0oa-confidential"
    assert data["client_secret"] == "super-secret"
    assert data["token_endpoint_auth_method"] == "client_secret_post"


def test_register_503_without_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oauth_client_id", "")
    with _client() as client:
        r = client.post(
            "/register",
            json={"client_name": "x", "redirect_uris": ["http://localhost/cb"]},
        )
    assert r.status_code == 503
    assert "OAUTH_CLIENT_ID" in r.json()["detail"]
