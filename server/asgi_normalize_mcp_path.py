"""Normalize MCP mount path so Starlette does not emit a trailing-slash redirect."""

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.types import Receive, Send

ASGIApp = Callable[..., Awaitable[None]]


class NormalizeMcpMountSlashMiddleware:
    """
    Starlette's router issues **307** from ``POST /mcp`` to ``POST /mcp/`` when the MCP app is
    mounted at ``/mcp``. Many MCP HTTP clients do not follow that redirect correctly, which can
    surface as uvicorn ``Invalid HTTP request received``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
        await self.app(scope, receive, send)
