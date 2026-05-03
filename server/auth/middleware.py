import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt as jose_jwt  # type: ignore[import-untyped]
from starlette.responses import Response

from server.auth.bearer_jwt import verify_oauth_access_token
from server.auth.context import current_oe_credential_cache_key, current_oe_jwt
from server.auth.credentials_cache import credential_cache_key
from server.auth.oauth_discovery import OAuthDiscoveryError
from server.auth.token_exchange import (
    TokenExchangeError,
    exchange_oauth_access_token,
    get_or_refresh_user_token,
)
from server.config import settings
from server.constants import (
    CREDENTIALS_HEADER_MAX_LEN,
    HEADER_OE_USER_SECRET,
    HEADER_OE_USER_TOKEN,
)

logger = logging.getLogger(__name__)


def _is_mcp_mount_root(path: str) -> bool:
    """True for mount root ``/mcp`` or canonical ``/mcp/`` (trailing slash normalization)."""
    return path == "/mcp" or path == "/mcp/"


# Paths that never require authentication
_UNPROTECTED = {
    "/",
    "/favicon.ico",
    "/.well-known/oauth-authorization-server",
    "/.well-known/openid-configuration",
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
    "/mcp-auth/declined",
    "/register",
    "/health",
}


def _request_is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return forwarded == "https"


async def _auth_response_or_none(request: Request) -> Response | None:
    """
    If this returns a Response, send it and skip the app (auth failure / help JSON).
    If this returns None, call the inner ASGI app (after setting ContextVars when required).

    Implemented without BaseHTTPMiddleware so Streamable HTTP / SSE through ``/mcp`` is not
    wrapped in a buffering middleware (Starlette documents incompatibilities).
    """
    if settings.auth_mode == "local":
        return None

    if settings.auth_mode == "remote_credentials":
        if request.url.path in _UNPROTECTED:
            return None

        token_hdr = request.headers.get(HEADER_OE_USER_TOKEN, "")
        secret_hdr = request.headers.get(HEADER_OE_USER_SECRET, "")
        user_token = token_hdr.strip()
        user_secret = secret_hdr.strip()

        accept = (request.headers.get("accept") or "").lower()
        wants_event_stream = "text/event-stream" in accept
        if (
            request.method == "GET"
            and _is_mcp_mount_root(request.url.path)
            and not user_token
            and not wants_event_stream
        ):
            return JSONResponse(
                {
                    "message": (
                        "MCP over HTTP expects POST with "
                        f"{HEADER_OE_USER_TOKEN} and {HEADER_OE_USER_SECRET}."
                    ),
                    "see_also": "/",
                },
                status_code=200,
            )

        if not _request_is_https(request):
            return JSONResponse(
                {
                    "error": "tls_required",
                    "error_description": "HTTPS is required for credential headers",
                },
                status_code=400,
            )

        if (
            not user_token
            or not user_secret
            or len(user_token) > CREDENTIALS_HEADER_MAX_LEN
            or len(user_secret) > CREDENTIALS_HEADER_MAX_LEN
            or any(c.isspace() for c in user_token)
            or any(c.isspace() for c in user_secret)
        ):
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "error_description": (
                        f"Missing or invalid {HEADER_OE_USER_TOKEN} or "
                        f"{HEADER_OE_USER_SECRET} header"
                    ),
                },
                status_code=401,
            )

        try:
            oe_jwt = await get_or_refresh_user_token(user_token, user_secret)
        except TokenExchangeError as e:
            status = 401 if e.status_code == 401 else 502
            body_key = "invalid_credentials" if status == 401 else "server_error"
            return JSONResponse(
                {
                    "error": body_key,
                    "error_description": str(e),
                },
                status_code=status,
            )
        except Exception as e:
            logger.warning("OvalEdge token exchange upstream failure: %s", e)
            return JSONResponse(
                {
                    "error": "server_error",
                    "error_description": str(e),
                },
                status_code=502,
            )

        try:
            jose_jwt.get_unverified_claims(oe_jwt)
        except Exception:
            return JSONResponse(
                {
                    "error": "invalid_token",
                    "error_description": "Invalid OvalEdge JWT from token exchange",
                },
                status_code=401,
            )

        current_oe_jwt.set(oe_jwt)
        current_oe_credential_cache_key.set(credential_cache_key(user_token, user_secret))
        return None

    if request.url.path in _UNPROTECTED:
        return None

    auth_header = request.headers.get("Authorization", "")

    if (
        request.method == "GET"
        and _is_mcp_mount_root(request.url.path)
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

    return None


class AuthMiddleware:
    """
    Handles auth for MCP modes.

    Remote (auth_mode=remote):
        1. Validate OAuth access token (JWT) via IdP JWKS from discovery
        2. Either forward that token to OvalEdge (ovaledge_remote_forward_idp_token) or
           exchange via OvalEdge token/generate, then set current_oe_jwt ContextVar

    Remote credentials (auth_mode=remote_credentials):
        X-OvalEdge-Token + X-OvalEdge-Secret → cached OvalEdge JWT in ContextVar

    Local (auth_mode=local):
        OvalEdge JWT already set in ContextVar via lifespan (stdio); middleware is a no-op.

    This is **pure ASGI** (not ``BaseHTTPMiddleware``) so MCP Streamable HTTP responses are not
    broken by response buffering.
    """

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        response = await _auth_response_or_none(request)
        if response is not None:
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
