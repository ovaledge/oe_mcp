"""Structured logging, error mapping, and response slimming for MCP tool invocations."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from server.client import OvalEdgeError
from server.mcp_response_slim import slim_tool_response
from server.tools.common.errors import error_payload, map_ovaledge_error

logger = logging.getLogger(__name__)


def _summarize_args(kwargs: dict[str, Any]) -> str:
    """Compact, non-secret argument summary for logs."""
    parts: list[str] = []
    for key, value in kwargs.items():
        if value is None:
            continue
        if key in ("object_id", "limit", "depth", "page", "object_type"):
            parts.append(f"{key}={value!r}")
        elif key in ("search_terms", "tags") and isinstance(value, list):
            preview = value[:3]
            suffix = "…" if len(value) > 3 else ""
            parts.append(f"{key}={preview!r}{suffix}")
        elif key in ("context_query", "term_name", "query") and isinstance(value, str):
            text = value.replace("\n", " ")[:80]
            if len(value) > 80:
                text += "…"
            parts.append(f"{key}={text!r}")
    return ", ".join(parts) if parts else "(no logged args)"


def _finalize_tool_result[R](result: R) -> R | dict[str, Any]:
    if isinstance(result, dict):
        return slim_tool_response(result)
    return result


def logged_tool_invocation[**P, R](
    fn: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R | dict[str, Any]]]:
    """
    Log tool name, duration, and outcome; map OvalEdge errors; slim large dict responses.

    Never logs credential headers or full API payloads.
    """

    tool_name = fn.__name__.removeprefix("_invoke_")

    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | dict[str, Any]:
        start = time.monotonic()
        arg_summary = _summarize_args(dict(kwargs))
        try:
            result = await fn(*args, **kwargs)
        except OvalEdgeError as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning(
                "mcp_tool tool=%s outcome=ovaledge_error status=%s duration_ms=%.0f %s",
                tool_name,
                exc.status_code,
                duration_ms,
                arg_summary,
            )
            return map_ovaledge_error(exc)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception(
                "mcp_tool tool=%s outcome=error duration_ms=%.0f %s",
                tool_name,
                duration_ms,
                arg_summary,
            )
            return error_payload(
                "An unexpected error occurred while executing the tool.",
                status_code=500,
            )
        else:
            duration_ms = (time.monotonic() - start) * 1000
            level = logging.WARNING if duration_ms > 25_000 else logging.INFO
            logger.log(
                level,
                "mcp_tool tool=%s outcome=ok duration_ms=%.0f %s",
                tool_name,
                duration_ms,
                arg_summary,
            )
            return _finalize_tool_result(result)

    return wrapper
