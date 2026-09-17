"""GET /.well-known/openai-apps-challenge (OpenAI plugin domain verification)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth.directory_well_known import OPENAI_APPS_CHALLENGE_PATH, router
from server.auth.middleware import AuthMiddleware
from server.config import settings


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_openai_apps_challenge_404_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openai_apps_challenge", "")
    with _client() as client:
        r = client.get(OPENAI_APPS_CHALLENGE_PATH)
    assert r.status_code == 404


def test_openai_apps_challenge_returns_exact_plaintext_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "oe-openai-challenge-token"
    monkeypatch.setattr(settings, "openai_apps_challenge", f"  {token}  ")
    with _client() as client:
        r = client.get(OPENAI_APPS_CHALLENGE_PATH)
    assert r.status_code == 200
    assert r.text == token
    assert r.headers["content-type"].startswith("text/plain")
    assert r.headers.get("cache-control") == "no-store"


def test_openai_apps_challenge_skips_bearer_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "remote")
    monkeypatch.setattr(settings, "openai_apps_challenge", "verify-me")
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)
    with TestClient(app) as client:
        r = client.get(
            OPENAI_APPS_CHALLENGE_PATH,
            headers={"x-forwarded-proto": "https"},
        )
    assert r.status_code == 200
    assert r.text == "verify-me"
