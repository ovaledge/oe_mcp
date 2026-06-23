"""Tests for MCP tool invocation logging."""

from __future__ import annotations

import logging

import pytest

from server.client import OvalEdgeError
from server.tools.common.tool_logging import logged_tool_invocation


@logged_tool_invocation
async def _invoke_sample_ok() -> dict[str, str]:
    return {"ok": True}


@logged_tool_invocation
async def _invoke_sample_oe_error() -> None:
    raise OvalEdgeError(503, "upstream down")


@logged_tool_invocation
async def _invoke_sample_crash() -> None:
    raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_logged_tool_invocation_ok(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    result = await _invoke_sample_ok()
    assert result == {"ok": True}
    assert any("mcp_tool" in r.message and "outcome=ok" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_logged_tool_invocation_ovaledge_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    with pytest.raises(OvalEdgeError):
        await _invoke_sample_oe_error()
    assert any(
        "outcome=ovaledge_error" in r.message and "status=503" in r.message
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_logged_tool_invocation_unhandled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    with pytest.raises(RuntimeError, match="boom"):
        await _invoke_sample_crash()
    assert any("outcome=error" in r.message for r in caplog.records)
