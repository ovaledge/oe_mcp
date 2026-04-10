from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from server.auth.context import current_oe_jwt
from server.auth.okta import verify_okta_token
from server.auth.token_exchange import TokenExchangeError, exchange_okta_token
from server.config import settings

# Paths that never require authentication
_UNPROTECTED = {
    "/.well-known/oauth-authorization-server",
    "/register",
    "/health",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Handles auth for both MCP modes.

    Remote (auth_mode=remote):
        1. Validate Okta JWT from Authorization header
        2. Exchange Okta JWT → OvalEdge user-scoped JWT
        3. Set OvalEdge JWT in current_oe_jwt ContextVar

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

        # Extract Bearer token from header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "error_description": "Bearer token required",
                },
                status_code=401,
            )

        okta_token = auth_header.removeprefix("Bearer ")

        # Step 1 — Validate Okta JWT
        try:
            await verify_okta_token(okta_token)
        except Exception as e:
            return JSONResponse(
                {
                    "error": "invalid_token",
                    "error_description": str(e),
                },
                status_code=401,
            )

        # Step 2 — Exchange Okta JWT for OvalEdge user-scoped JWT
        try:
            oe_jwt = await exchange_okta_token(okta_token)
        except TokenExchangeError as e:
            return JSONResponse(
                {
                    "error": "server_error",
                    "error_description": str(e),
                },
                status_code=502,
            )

        # Step 3 — Make OvalEdge JWT available to all tools this request
        current_oe_jwt.set(oe_jwt)

        return await call_next(request)
