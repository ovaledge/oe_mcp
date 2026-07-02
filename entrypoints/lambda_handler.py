"""
Remote MCP entrypoint — Streamable HTTP via Mangum.

Auth depends on ``AUTH_MODE``:

- ``remote``: OAuth 2.x / OIDC ``Authorization: Bearer`` → OvalEdge JWT (per request).
  Registers OAuth discovery + dynamic registration routes.

- ``remote_credentials``: ``X-OvalEdge-Credentials`` (``token::secret``) or
  ``X-OvalEdge-Token`` + ``X-OvalEdge-Secret`` → cached OvalEdge JWT.
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
import sys
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastmcp.utilities.lifespan import combine_lifespans
from mangum import Mangum

from server.app import mcp
from server.asgi_mcp_observability import McpObservabilityMiddleware
from server.asgi_normalize_mcp_path import NormalizeMcpMountSlashMiddleware
from server.auth.local_lifespan import local_oe_jwt_lifespan
from server.auth.metadata import router as metadata_router
from server.auth.middleware import AuthMiddleware
from server.auth.registration import router as registration_router
from server.auth.remote_credentials_discovery import router as remote_credentials_discovery_router
from server.branding import MCP_BRAND_ICON_ROUTE, brand_icon_file, mcp_server_icons
from server.config import settings
from server.constants import HEADER_OE_USER_SECRET, HEADER_OE_USER_TOKEN
from server.logging_config import configure_stderr_logging

logger = logging.getLogger(__name__)

mcp_http = mcp.http_app(
    path="/",
    transport="streamable-http",
    stateless_http=settings.mcp_http_stateless,
)

# Icons are resolved at ``server.app`` import; refresh here so HTTP entrypoints pick up
# ``MCP_PUBLIC_BASE_URL`` from env / ``.env`` (stdio sets ``MCP_STDIO_TRANSPORT`` earlier).
_refreshed_icons = mcp_server_icons()
if _refreshed_icons is not None:
    mcp._mcp_server.icons = _refreshed_icons  # noqa: SLF001


def _running_on_aws_lambda() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


@asynccontextmanager
async def _fastapi_lifespan(_app: object) -> AsyncIterator[dict[str, Any]]:
    configure_stderr_logging()
    yield {}


# Uvicorn: one process lifespan runs both. Lambda: Mangum would start/stop every invoke and break
# StreamableHTTPSessionManager — MCP sub-app lifespan is pinned separately (see handler).
def _uvicorn_lifespans() -> tuple[Any, ...]:
    parts: list[Any] = [_fastapi_lifespan, mcp_http.lifespan]
    if (
        settings.auth_mode == "local"
        and settings.ovaledge_user_token.strip()
        and settings.ovaledge_user_secret.strip()
    ):
        parts.append(local_oe_jwt_lifespan)
    return tuple(parts)


@asynccontextmanager
async def _uvicorn_combined_lifespan(app: object) -> AsyncIterator[dict[str, Any]]:
    """Build lifespan chain at startup (tests, oe-mcp-http env overrides)."""
    parts = _uvicorn_lifespans()
    combined = combine_lifespans(*parts) if len(parts) > 1 else parts[0]
    async with combined(app) as state:
        yield state


_app_lifespan: Any = (
    _fastapi_lifespan
    if _running_on_aws_lambda()
    else _uvicorn_combined_lifespan
)

app = FastAPI(
    title="OvalEdge MCP Server",
    lifespan=_app_lifespan,
)

app.add_middleware(McpObservabilityMiddleware)
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
async def favicon() -> FileResponse:
    """Same PNG as ``/brand/...`` — some MCP clients probe origin favicon for branding."""
    return FileResponse(brand_icon_file(), media_type="image/png")


@app.get(MCP_BRAND_ICON_ROUTE)
async def brand_icon() -> FileResponse:
    """Public MCP branding icon (``server/static/``); no auth required."""
    return FileResponse(brand_icon_file(), media_type="image/png")


@app.get("/health")
async def health() -> JSONResponse:
    ready = mcp_lifespan_ready()
    payload: dict[str, object] = {
        "status": "healthy" if ready or not _running_on_aws_lambda() else "degraded",
        "version": settings.mcp_server_version,
        "auth_mode": settings.auth_mode,
        "mcp_lifespan_ready": ready,
    }
    if _running_on_aws_lambda() and not ready:
        payload["mcp_lifespan_detail"] = (
            "MCP HTTP lifespan not started yet on this Lambda instance "
            "(cold start or holder task failed)."
        )
    return JSONResponse(payload)


app.mount("/mcp", mcp_http)

_mangum = Mangum(app, lifespan="off" if _running_on_aws_lambda() else "auto")

_mcp_holder_lock = threading.Lock()
_mcp_holder_loop_pump_lock = threading.Lock()
_mcp_holder_task: asyncio.Task[Any] | None = None
_mcp_holder_started = threading.Event()


def _lambda_mcp_lifespan_startup_timeout_seconds() -> float:
    """Seconds to wait for Streamable HTTP lifespan during cold start (INIT or first invoke)."""
    raw = os.environ.get("LAMBDA_MCP_LIFESPAN_STARTUP_TIMEOUT_SECONDS", "").strip()
    if raw:
        return max(1.0, float(raw))
    return 28.0


def _lambda_mcp_lifespan_eager_bootstrap_enabled() -> bool:
    raw = os.environ.get("LAMBDA_MCP_LIFESPAN_EAGER_BOOTSTRAP", "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def mcp_lifespan_ready() -> bool:
    """
    Whether Streamable HTTP MCP is ready to accept requests.

    On Lambda, True after the pinned ``mcp_http`` lifespan context has started.
    Off Lambda, True (uvicorn runs ``combine_lifespans`` for the mounted app).
    """
    if not _running_on_aws_lambda():
        return True
    if not _mcp_holder_started.is_set():
        return False
    if _mcp_holder_task is None or _mcp_holder_task.done():
        return False
    return True


def _lambda_mcp_event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def _pump_lambda_mcp_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Drive the shared loop briefly (thread-safe for concurrent Lambda invokes)."""
    with _mcp_holder_loop_pump_lock:
        loop.run_until_complete(asyncio.sleep(0.01))


def _wait_for_lambda_mcp_lifespan_ready() -> None:
    timeout = _lambda_mcp_lifespan_startup_timeout_seconds()
    deadline = time.monotonic() + timeout
    loop = _lambda_mcp_event_loop()
    while time.monotonic() < deadline:
        if _mcp_holder_started.is_set():
            logger.info("MCP HTTP lifespan pinned and ready (Lambda)")
            return
        task = _mcp_holder_task
        if task is not None and task.done():
            exc = task.exception()
            if exc is not None:
                raise RuntimeError(
                    "MCP HTTP lifespan holder task failed during startup"
                ) from exc
            raise RuntimeError("MCP HTTP lifespan holder task exited during startup")
        _pump_lambda_mcp_event_loop(loop)

    raise RuntimeError(
        "StreamableHTTPSessionManager did not start within "
        f"{timeout:.0f}s — check FastMCP / MCP versions. "
        "Increase LAMBDA_MCP_LIFESPAN_STARTUP_TIMEOUT_SECONDS or Lambda memory if cold "
        "starts are slow; see CloudWatch for holder task errors."
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
            if _mcp_holder_started.is_set():
                return
            # Another caller is already starting the holder — wait outside the lock.
        elif _mcp_holder_task is not None and _mcp_holder_task.done():
            exc = _mcp_holder_task.exception()
            if exc is not None:
                logger.exception("MCP http lifespan holder task ended with error", exc_info=exc)
            _mcp_holder_task = None
            _mcp_holder_started.clear()

        if _mcp_holder_task is None:
            loop = _lambda_mcp_event_loop()

            async def _hold_mcp_http_lifespan_forever() -> None:
                async with mcp_http.router.lifespan_context(mcp_http):
                    _mcp_holder_started.set()
                    logger.info("MCP HTTP lifespan entered (Lambda holder task)")
                    await asyncio.Event().wait()

            _mcp_holder_started.clear()
            _mcp_holder_task = loop.create_task(_hold_mcp_http_lifespan_forever())

    _wait_for_lambda_mcp_lifespan_ready()


def _eager_bootstrap_lambda_mcp_lifespan_at_import() -> None:
    if not _running_on_aws_lambda() or not _lambda_mcp_lifespan_eager_bootstrap_enabled():
        return
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    try:
        _ensure_lambda_mcp_http_lifespan_pinned()
    except Exception:
        logger.exception(
            "MCP HTTP lifespan eager bootstrap did not finish during Lambda import; "
            "handler will retry on first request"
        )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if _running_on_aws_lambda():
        _ensure_lambda_mcp_http_lifespan_pinned()
    try:
        return _mangum(event, context)
    except Exception:
        request_id = getattr(context, "aws_request_id", None) if context else None
        logger.exception(
            "Lambda handler uncaught error request_id=%s",
            request_id or "-",
        )
        raise


_eager_bootstrap_lambda_mcp_lifespan_at_import()
