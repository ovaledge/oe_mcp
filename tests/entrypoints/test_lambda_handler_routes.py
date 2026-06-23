"""Public HTTP routes and Lambda lifespan pinning on entrypoints.lambda_handler."""

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

from server.config import settings


def _reset_lambda_mcp_holder_state() -> None:
    import entrypoints.lambda_handler as lh

    if lh._mcp_holder_task is not None and not lh._mcp_holder_task.done():
        lh._mcp_holder_task.cancel()
    lh._mcp_holder_task = None
    lh._mcp_holder_started.clear()


class TestLambdaHandlerPublicRoutes:
    async def test_health_non_lambda_reports_mcp_ready(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
        from entrypoints.lambda_handler import health

        resp = await health()
        body = json.loads(resp.body)
        assert body["status"] == "healthy"
        assert body["mcp_lifespan_ready"] is True
        assert "auth_mode" in body

    async def test_health_lambda_not_ready_before_pin(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "fn")
        _reset_lambda_mcp_holder_state()
        from entrypoints.lambda_handler import health

        resp = await health()
        body = json.loads(resp.body)
        assert body["mcp_lifespan_ready"] is False
        assert body["status"] == "degraded"
        assert "mcp_lifespan_detail" in body

    async def test_favicon_returns_png(self) -> None:
        from entrypoints.lambda_handler import favicon

        resp = await favicon()
        assert resp.status_code == 200
        assert resp.media_type == "image/png"

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


class TestLambdaMcpLifespanPinning:
    def test_ensure_pin_sets_ready_when_lifespan_enters(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import entrypoints.lambda_handler as lh

        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "fn")
        _reset_lambda_mcp_holder_state()

        @asynccontextmanager
        async def fake_lifespan(_app: object):
            yield

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            with patch.object(lh.mcp_http.router, "lifespan_context", fake_lifespan):
                lh._ensure_lambda_mcp_http_lifespan_pinned()
            assert lh._mcp_holder_started.is_set()
            assert lh.mcp_lifespan_ready() is True
        finally:
            if lh._mcp_holder_task is not None and not lh._mcp_holder_task.done():
                lh._mcp_holder_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    loop.run_until_complete(lh._mcp_holder_task)
            _reset_lambda_mcp_holder_state()
            loop.close()

    def test_ensure_pin_timeout_error_is_actionable(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import entrypoints.lambda_handler as lh

        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "fn")
        _reset_lambda_mcp_holder_state()

        @asynccontextmanager
        async def hanging_lifespan(_app: object):
            await asyncio.Event().wait()
            yield  # pragma: no cover

        loop = asyncio.new_event_loop()
        clock = {"t": 0.0}

        def fake_monotonic() -> float:
            clock["t"] += 5.0
            return clock["t"]

        try:
            asyncio.set_event_loop(loop)
            with (
                patch.object(lh.mcp_http.router, "lifespan_context", hanging_lifespan),
                patch.object(lh.time, "monotonic", fake_monotonic),
            ):
                with pytest.raises(
                    RuntimeError,
                    match="StreamableHTTPSessionManager did not start within",
                ):
                    lh._ensure_lambda_mcp_http_lifespan_pinned()
        finally:
            if lh._mcp_holder_task is not None and not lh._mcp_holder_task.done():
                lh._mcp_holder_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    loop.run_until_complete(lh._mcp_holder_task)
            _reset_lambda_mcp_holder_state()
            loop.close()

    def test_ensure_pin_waits_when_holder_task_already_running(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import entrypoints.lambda_handler as lh

        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "fn")
        _reset_lambda_mcp_holder_state()

        loop = asyncio.new_event_loop()
        running_task = loop.create_task(asyncio.sleep(3600))
        lh._mcp_holder_task = running_task

        try:
            with patch.object(lh, "_wait_for_lambda_mcp_lifespan_ready") as wait_mock:
                lh._ensure_lambda_mcp_http_lifespan_pinned()
            wait_mock.assert_called_once()
            assert lh._mcp_holder_task is running_task
        finally:
            running_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                loop.run_until_complete(running_task)
            _reset_lambda_mcp_holder_state()
            loop.close()
