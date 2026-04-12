"""
Remote MCP entrypoint — Streamable HTTP via Mangum.
Auth: Okta OAuth 2.1 PKCE → Okta JWT → OvalEdge JWT (per request)

Routes:
    GET  /.well-known/oauth-authorization-server  → OAuth discovery
    POST /register                                 → Dynamic client registration
    GET  /health                                   → Health check
    POST /mcp                                      → MCP (protected)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp.utilities.lifespan import combine_lifespans
from mangum import Mangum

from server.app import mcp
from server.auth.metadata import router as metadata_router
from server.auth.middleware import AuthMiddleware
from server.auth.registration import router as registration_router
from server.config import settings
from server.logging_config import configure_stderr_logging

mcp_http = mcp.http_app(
    path="/",
    transport="streamable-http",
    stateless_http=True,
)


@asynccontextmanager
async def _fastapi_lifespan(_app: object) -> AsyncIterator[dict[str, Any]]:
    configure_stderr_logging()
    yield {}


app = FastAPI(
    title="OvalEdge MCP Server",
    lifespan=combine_lifespans(_fastapi_lifespan, mcp_http.lifespan),
)

app.add_middleware(AuthMiddleware)

app.include_router(metadata_router)
app.include_router(registration_router)


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

# Use auto lifespan so ASGI startup runs the MCP streamable-http session manager.
# (Literal ``lifespan="off"`` prevents sub-app lifespan from running and breaks MCP.)
handler = Mangum(app, lifespan="auto")
