import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt as jose_jwt
from starlette.responses import Response
from starlette.types import Receive, Send

from server.auth.bearer_jwt import verify_oauth_access_token
from server.auth.context import (
    current_oe_credential_cache_key,
    current_oe_jwt,
    current_oe_user_secret,
    current_oe_user_token,
)
from server.auth.credentials_cache import credential_cache_key
from server.auth.oauth_discovery import OAuthDiscoveryError
from server.auth.remote_credentials_parse import (
    parse_remote_user_credentials,
    remote_credentials_auth_hint,
)
from server.auth.token_exchange import (
    TokenExchangeError,
    exchange_oauth_access_token,
    get_or_refresh_user_token,
)
from server.branding import MCP_BRAND_ICON_ROUTE
from server.config import settings
from server.constants import (
    HEADER_OE_USER_COMBINED,
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
    MCP_BRAND_ICON_ROUTE,
}


def _request_is_https(request: Request) -> bool:
    """True when the request is HTTPS or behind a trusted proxy that sets x-forwarded-proto."""
    if request.url.scheme == "https":
        return True
    # Trusted-proxy assumption: ALB/API Gateway terminate TLS and set this header.
    # Do not expose this process directly to clients without a proxy that strips spoofed values.
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

        parsed = parse_remote_user_credentials(
            combined_hdr=request.headers.get(HEADER_OE_USER_COMBINED, ""),
            token_hdr=request.headers.get(HEADER_OE_USER_TOKEN, ""),
            secret_hdr=request.headers.get(HEADER_OE_USER_SECRET, ""),
        )
        has_any_credential_header = any(
            request.headers.get(h, "").strip()
            for h in (
                HEADER_OE_USER_COMBINED,
                HEADER_OE_USER_TOKEN,
                HEADER_OE_USER_SECRET,
            )
        )

        accept = (request.headers.get("accept") or "").lower()
        wants_event_stream = "text/event-stream" in accept
        if (
            request.method == "GET"
            and _is_mcp_mount_root(request.url.path)
            and not has_any_credential_header
            and not wants_event_stream
        ):
            return JSONResponse(
                {
                    "message": (
                        "MCP over HTTP expects POST with "
                        f"{remote_credentials_auth_hint()}."
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

        if parsed is None:
            return JSONResponse(
                {
                    "error": "unauthorized",
                    "error_description": (
                        f"Missing or invalid credential headers ({remote_credentials_auth_hint()})"
                    ),
                },
                status_code=401,
            )

        user_token, user_secret = parsed

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
        current_oe_user_token.set(user_token)
        current_oe_user_secret.set(user_secret)
        return None

    if request.url.path in _UNPROTECTED:
        return None

    if not _request_is_https(request):
        return JSONResponse(
            {
                "error": "tls_required",
                "error_description": "HTTPS is required for remote MCP requests",
            },
            status_code=400,
        )

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
        X-OvalEdge-Credentials (token::secret) or X-OvalEdge-Token + X-OvalEdge-Secret
        → cached OvalEdge JWT in ContextVar

    Local (auth_mode=local):
        OvalEdge JWT already set in ContextVar via lifespan (stdio); middleware is a no-op.

    This is **pure ASGI** (not ``BaseHTTPMiddleware``) so MCP Streamable HTTP responses are not
    broken by response buffering.
    """

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        response = await _auth_response_or_none(request)
        if response is not None:
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
