"""Span helpers for MCP tool invocations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

_TRACER_NAME = "oe-mcp.tools"


def get_tool_tracer() -> trace.Tracer:
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def tool_invocation_span(
    tool_name: str,
    *,
    arg_summary: str,
) -> Iterator[trace.Span]:
    """Create a span for one MCP tool call; records outcome and duration on exit."""
    tracer = get_tool_tracer()
    with tracer.start_as_current_span(
        f"mcp.tool.{tool_name}",
        attributes={
            "mcp.tool.name": tool_name,
            "mcp.tool.args_summary": arg_summary,
        },
    ) as span:
        yield span


def record_tool_success(span: trace.Span, *, duration_ms: float) -> None:
    span.set_attribute("mcp.tool.outcome", "ok")
    span.set_attribute("mcp.tool.duration_ms", duration_ms)


def record_tool_ovaledge_error(
    span: trace.Span,
    *,
    duration_ms: float,
    status_code: int,
) -> None:
    span.set_attribute("mcp.tool.outcome", "ovaledge_error")
    span.set_attribute("mcp.tool.duration_ms", duration_ms)
    span.set_attribute("mcp.tool.ovaledge_status_code", status_code)
    span.set_status(Status(StatusCode.ERROR, f"OvalEdge API error {status_code}"))


def record_tool_error(span: trace.Span, *, duration_ms: float, message: str) -> None:
    span.set_attribute("mcp.tool.outcome", "error")
    span.set_attribute("mcp.tool.duration_ms", duration_ms)
    span.set_status(Status(StatusCode.ERROR, message))
