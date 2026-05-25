"""Public HTTP routes on entrypoints.lambda_handler (direct handlers, no MCP lifespan)."""

import json
from unittest.mock import patch

import pytest

from server.config import settings


class TestLambdaHandlerPublicRoutes:
    async def test_health(self) -> None:
        from entrypoints.lambda_handler import health

        resp = await health()
        body = json.loads(resp.body)
        assert body["status"] == "healthy"
        assert "auth_mode" in body

    async def test_favicon_no_content(self) -> None:
        from entrypoints.lambda_handler import favicon

        resp = await favicon()
        assert resp.status_code == 204

    async def test_root_remote_credentials_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_mode", "remote_credentials")
        from entrypoints.lambda_handler import root

        resp = await root()
        body = json.loads(resp.body)
        assert body["auth_mode"] == "remote_credentials"
        assert "X-OvalEdge" in body["mcp"] or "credentials" in body["mcp"].lower()
        assert "oauth_discovery" not in body

    async def test_root_remote_oauth_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "auth_mode", "remote")
        from entrypoints.lambda_handler import root

        resp = await root()
        body = json.loads(resp.body)
        assert body["auth_mode"] == "remote"
        assert "Bearer" in body["mcp"]
        assert body["oauth_discovery"] == "/.well-known/oauth-authorization-server"


class TestLambdaHandlerEntry:
    def test_handler_delegates_to_mangum_without_lambda_lifespan_pin(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
        with patch(
            "entrypoints.lambda_handler._mangum",
            return_value={"statusCode": 200},
        ) as mangum:
            with patch(
                "entrypoints.lambda_handler._ensure_lambda_mcp_http_lifespan_pinned",
            ) as pin:
                from entrypoints.lambda_handler import handler

                out = handler({"httpMethod": "GET"}, None)
        assert out == {"statusCode": 200}
        mangum.assert_called_once()
        pin.assert_not_called()

    def test_handler_pins_mcp_lifespan_on_lambda(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "fn")
        with patch("entrypoints.lambda_handler._mangum", return_value={"statusCode": 200}):
            with patch(
                "entrypoints.lambda_handler._ensure_lambda_mcp_http_lifespan_pinned",
            ) as pin:
                from entrypoints.lambda_handler import handler

                handler({}, None)
        pin.assert_called_once()
