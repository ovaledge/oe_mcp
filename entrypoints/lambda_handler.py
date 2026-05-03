"""
Remote MCP entrypoint — Streamable HTTP via Mangum.

Auth depends on ``AUTH_MODE``:

- ``remote``: OAuth 2.x / OIDC ``Authorization: Bearer`` → OvalEdge JWT (per request).
  Registers OAuth discovery + dynamic registration routes.

- ``remote_credentials``: ``X-OvalEdge-Token`` + ``X-OvalEdge-Secret`` → cached OvalEdge JWT.
  Set ``AUTH_MODE=remote_credentials`` in the process environment (Lambda console, SAM template,
  or ``.env`` when using uvicorn). Same ``app`` object as other modes; mounts discovery stubs only
  (not full OAuth) so MCP HTTP clients do not see 404 on ``/.well-known/oauth-*``.

Routes:
    GET  /.well-known/oauth-authorization-server  → IdP metadata (``remote``) or discovery stub
                                                      (``remote_credentials``)
    POST /register                                 → Dynamic client registration (remote only)
    GET  /health                                   → Health check
    POST /mcp                                      → MCP (protected)

Lambda note:
    Mangum runs ASGI **lifespan startup and shutdown on every invocation**. FastMCP's
    ``StreamableHTTPSessionManager.run()`` may only be entered **once per instance**; re-entry
    raises ``RuntimeError``. On Lambda we therefore use ``Mangum(..., lifespan="off")`` and pin
    ``mcp_http``'s lifespan on a background task for the container lifetime (see ``handler``).
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp.utilities.lifespan import combine_lifespans
from mangum import Mangum
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route

from server.app import mcp
from server.asgi_normalize_mcp_path import NormalizeMcpMountSlashMiddleware
from server.auth.metadata import router as metadata_router
from server.auth.middleware import AuthMiddleware
from server.auth.registration import router as registration_router
from server.auth.remote_credentials_discovery import router as remote_credentials_discovery_router
from server.config import settings
from server.constants import HEADER_OE_USER_SECRET, HEADER_OE_USER_TOKEN
from server.logging_config import configure_stderr_logging

logger = logging.getLogger(__name__)

mcp_http = mcp.http_app(
    path="/",
    transport="streamable-http",
    stateless_http=settings.mcp_http_stateless,
)


def _running_on_aws_lambda() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


@asynccontextmanager
async def _fastapi_lifespan(_app: object) -> AsyncIterator[dict[str, Any]]:
    configure_stderr_logging()
    yield {}


# Uvicorn: one process lifespan runs both. Lambda: Mangum would start/stop every invoke and break
# StreamableHTTPSessionManager — MCP sub-app lifespan is pinned separately (see handler).
_app_lifespan: Any = (
    _fastapi_lifespan
    if _running_on_aws_lambda()
    else combine_lifespans(_fastapi_lifespan, mcp_http.lifespan)
)

app = FastAPI(
    title="OvalEdge MCP Server",
    lifespan=_app_lifespan,
)

app.add_middleware(AuthMiddleware)
app.add_middleware(NormalizeMcpMountSlashMiddleware)

if settings.auth_mode == "remote":
    app.include_router(metadata_router)
    app.include_router(registration_router)

if settings.auth_mode == "remote_credentials":
    app.include_router(remote_credentials_discovery_router)


@app.get("/")
async def root() -> JSONResponse:
    """Avoid 401 in the browser; remote modes document how to call POST /mcp."""
    if settings.auth_mode == "remote_credentials":
        mcp_doc = (
            f"POST /mcp with {HEADER_OE_USER_TOKEN} and {HEADER_OE_USER_SECRET} (see .env.example)"
        )
        note = (
            "GET / without auth is only this page; /mcp requires OvalEdge user credentials headers."
        )
    else:
        mcp_doc = "POST /mcp with Authorization: Bearer <access_token>"
        note = "GET / without auth is only this page; /mcp requires Bearer (remote OAuth mode)."

    payload: dict[str, object] = {
        "service": "OvalEdge MCP",
        "auth_mode": settings.auth_mode,
        "health": "/health",
        "mcp": mcp_doc,
        "note": note,
    }
    if settings.auth_mode == "remote":
        payload["oauth_discovery"] = "/.well-known/oauth-authorization-server"

    return JSONResponse(payload)


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "healthy",
            "version": settings.mcp_server_version,
            "auth_mode": settings.auth_mode,
        }
    )


app.mount("/mcp", mcp_http)

_mangum = Mangum(app, lifespan="off" if _running_on_aws_lambda() else "auto")

_mcp_holder_lock = threading.Lock()
_mcp_holder_task: asyncio.Task[Any] | None = None


def _streamable_http_session_manager(starlette_app: Starlette) -> Any:
    """Reach FastMCP's ``StreamableHTTPSessionManager`` so we can wait for ``_task_group``."""
    from fastmcp.server.http import StreamableHTTPASGIApp

    for route in starlette_app.routes:
        if isinstance(route, Route) and isinstance(route.endpoint, StreamableHTTPASGIApp):
            return route.endpoint.session_manager
    raise RuntimeError(
        "StreamableHTTPASGIApp route not found on mcp_http — FastMCP layout may have changed"
    )


def _ensure_lambda_mcp_http_lifespan_pinned() -> None:
    """
    Keep ``mcp_http``'s StreamableHTTPSessionManager ``run()`` entered for the whole warm
    container. Mangum ``lifespan=auto`` exits that context after each invoke, which trips the
    library's single-use guard and yields 500s on the next POST /mcp.
    """
    global _mcp_holder_task
    with _mcp_holder_lock:
        if _mcp_holder_task is not None and not _mcp_holder_task.done():
            sm = _streamable_http_session_manager(mcp_http)
            # StreamableHTTPSessionManager does not expose a public readiness API.
            if getattr(sm, "_task_group", None) is not None:
                return

        if _mcp_holder_task is not None and _mcp_holder_task.done():
            exc = _mcp_holder_task.exception()
            if exc is not None:
                logger.exception("MCP http lifespan holder task ended with error", exc_info=exc)
            _mcp_holder_task = None

        loop = asyncio.get_event_loop()

        async def _hold_mcp_http_lifespan_forever() -> None:
            async with mcp_http.router.lifespan_context(mcp_http):
                await asyncio.Event().wait()

        _mcp_holder_task = loop.create_task(_hold_mcp_http_lifespan_forever())
        sm = _streamable_http_session_manager(mcp_http)
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if getattr(sm, "_task_group", None) is not None:
                logger.info("MCP StreamableHTTP session manager ready (Lambda pinned lifespan)")
                return
            loop.run_until_complete(asyncio.sleep(0.01))

        raise RuntimeError(
            "StreamableHTTPSessionManager did not start within 15s — check FastMCP / MCP versions"
        )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if _running_on_aws_lambda():
        _ensure_lambda_mcp_http_lifespan_pinned()
    return _mangum(event, context)
