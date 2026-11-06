"""Streamable HTTP JSON mode for clients that omit text/event-stream (e.g. Cortex)."""

from __future__ import annotations

import pytest

from server.config import Settings


def test_mcp_json_response_defaults_true() -> None:
    assert Settings().mcp_json_response is True


def test_mcp_json_response_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_JSON_RESPONSE", "false")
    assert Settings().mcp_json_response is False


def test_mcp_http_app_kwargs_enable_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from entrypoints import lambda_handler as lh

    monkeypatch.setattr(lh.settings, "mcp_json_response", True)
    monkeypatch.setattr(lh.settings, "mcp_http_stateless", True)
    kwargs = lh.mcp_http_app_kwargs()
    assert kwargs["json_response"] is True
    assert kwargs["stateless_http"] is True
    assert kwargs["transport"] == "streamable-http"
    assert kwargs["path"] == "/"
