"""ASGI middleware: MCP HTTP request timing and 5xx logging for CloudWatch."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.types import Receive, Send

logger = logging.getLogger(__name__)

ASGIApp = Callable[..., Awaitable[None]]


def _request_id(scope: dict[str, Any]) -> str | None:
    headers = scope.get("headers") or ()
    for name, value in headers:
        if name.lower() == b"x-amzn-requestid" and isinstance(value, bytes):
            return value.decode("latin-1", errors="replace")
    return None


class McpObservabilityMiddleware:
    """
    Pure ASGI middleware (no response buffering).

    Logs slow or failed ``/mcp`` HTTP calls. Does not read request bodies or headers
    that may contain credentials.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        aws_request_id = _request_id(scope)
        start = time.monotonic()
        status_code = 500

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception(
                "mcp_http method=%s path=%s status=exception duration_ms=%.0f request_id=%s",
                method,
                path,
                duration_ms,
                aws_request_id or "-",
            )
            raise
        else:
            duration_ms = (time.monotonic() - start) * 1000
            if status_code >= 500:
                logger.error(
                    "mcp_http method=%s path=%s status=%s duration_ms=%.0f request_id=%s",
                    method,
                    path,
                    status_code,
                    duration_ms,
                    aws_request_id or "-",
                )
            elif status_code >= 400 or duration_ms >= 25_000:
                logger.warning(
                    "mcp_http method=%s path=%s status=%s duration_ms=%.0f request_id=%s",
                    method,
                    path,
                    status_code,
                    duration_ms,
                    aws_request_id or "-",
                )
