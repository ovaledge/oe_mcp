import logging
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from server.auth.bearer_jwt import verify_oauth_access_token
from server.auth.context import current_oe_jwt
from server.auth.oauth_discovery import OAuthDiscoveryError
from server.auth.token_exchange import TokenExchangeError, exchange_oauth_access_token
from server.config import settings

logger = logging.getLogger(__name__)

# Paths that never require authentication
_UNPROTECTED = {
    "/",
    "/favicon.ico",
    "/.well-known/oauth-authorization-server",
    "/register",
    "/health",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Handles auth for both MCP modes.

    Remote (auth_mode=remote):
        1. Validate OAuth access token (JWT) via IdP JWKS from discovery
        2. Either forward that token to OvalEdge (ovaledge_remote_forward_idp_token) or
           exchange via OvalEdge token/generate, then set current_oe_jwt ContextVar

    Local (auth_mode=local):
        OvalEdge JWT already set in ContextVar by lifespan hook
        in entrypoints/local.py — middleware is a no-op.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Local mode — JWT already in context via lifespan, skip
        if settings.auth_mode == "local":
            return await call_next(request)

        # Unprotected endpoints — no auth required
        if request.url.path in _UNPROTECTED:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")

        # Browsers open GET /mcp with no Authorization — not a valid MCP request; avoid noisy 401.
        if (
            request.method == "GET"
            and request.url.path == "/mcp"
            and not auth_header.startswith("Bearer ")
        ):
            return JSONResponse(
                {
                    "message": (
                        "MCP over HTTP expects POST with Authorization: Bearer <access_token>. "
                        "A bare GET (e.g. from the address bar) has no token."
                    ),
                    "see_also": "/",
                },
                status_code=200,
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "error_description": "Bearer token required",
                },
                status_code=401,
            )

        access_token = auth_header.removeprefix("Bearer ")

        # Step 1 — Validate OAuth access token
        try:
            await verify_oauth_access_token(access_token)
        except OAuthDiscoveryError as e:
            return JSONResponse(
                {
                    "error": "server_error",
                    "error_description": str(e),
                },
                status_code=503,
            )
        except Exception as e:
            logger.warning("OAuth access token rejected: %s", e)
            return JSONResponse(
                {
                    "error": "invalid_token",
                    "error_description": str(e),
                },
                status_code=401,
            )

        # Step 2 — OvalEdge credential: forward IdP token or exchange for OvalEdge JWT
        if settings.ovaledge_remote_forward_idp_token:
            current_oe_jwt.set(access_token)
        else:
            try:
                oe_jwt = await exchange_oauth_access_token(access_token)
            except TokenExchangeError as e:
                return JSONResponse(
                    {
                        "error": "server_error",
                        "error_description": str(e),
                    },
                    status_code=502,
                )
            current_oe_jwt.set(oe_jwt)

        return await call_next(request)
