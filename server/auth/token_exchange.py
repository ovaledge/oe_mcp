import time
from typing import Any, cast

import httpx
from jose import jwt  # type: ignore[import-untyped]

from server.auth import context as auth_context
from server.config import settings
from server.constants import JWT_REFRESH_LEEWAY_SECONDS, OVALEDGE_TOKEN_EXCHANGE_PATH


class TokenExchangeError(Exception):
    pass


def _extract_token(body: Any) -> str:
    """Extract token from OvalEdge response (dict or raw JWT string)."""
    token: str | None
    if isinstance(body, str):
        token = body
    elif isinstance(body, dict):
        token = body.get("token") or body.get("access_token") or body.get("jwt")
    else:
        token = None
    if not token:
        raise TokenExchangeError(
            "Token exchange response missing token field "
            f"or unsupported payload type: {type(body).__name__}"
        )
    return str(token)


def is_token_expiring(token: str, leeway_seconds: int = JWT_REFRESH_LEEWAY_SECONDS) -> bool:
    """
    Return True when the token is expired or within leeway_seconds of expiry.

    If `exp` is missing (opaque or non-JWT token), treat as not expiring so we do not
    call token/generate on every tool invocation. If parsing fails, refresh to be safe.
    """
    try:
        claims = cast(dict[str, Any], jwt.get_unverified_claims(token))
    except Exception:
        return True
    if "exp" not in claims:
        return False
    exp = int(claims["exp"])
    if exp <= 0:
        return True
    now = int(time.time())
    return exp <= (now + leeway_seconds)


async def exchange_okta_token(okta_jwt: str) -> str:
    """
    Remote MCP path.
    Exchange a validated Okta JWT for an OvalEdge user-scoped JWT.
    Called per MCP request — fully stateless.

    TODO: confirm exact request body format from OvalEdge API docs.
    TODO: confirm exact response field name (token / access_token / jwt).
    """
    async with httpx.AsyncClient(
        base_url=settings.ovaledge_base_url,
        timeout=settings.ovaledge_timeout_seconds,
    ) as client:
        response = await client.post(
            OVALEDGE_TOKEN_EXCHANGE_PATH,
            json={
                "userToken": okta_jwt,
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        if response.status_code != 200:
            raise TokenExchangeError(
                f"OvalEdge token exchange failed: {response.status_code} {response.text}"
            )
        # OvalEdge may return either a JSON object or raw JWT text.
        try:
            payload: Any = response.json()
        except Exception:
            payload = response.text
        return _extract_token(payload)


async def exchange_client_credentials() -> str:
    """
    Local MCP path.
    Exchange OvalEdge user token + user secret for an OvalEdge JWT.
    Called via FastMCP lifespan hook at startup.

    TODO: confirm exact request body format from OvalEdge API docs.
    TODO: confirm exact response field name.
    """
    async with httpx.AsyncClient(
        base_url=settings.ovaledge_base_url,
        timeout=settings.ovaledge_timeout_seconds,
    ) as client:
        response = await client.post(
            OVALEDGE_TOKEN_EXCHANGE_PATH,
            json={
                "userToken": settings.ovaledge_user_token,
                "userSecret": settings.ovaledge_user_secret,
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        if response.status_code != 200:
            raise TokenExchangeError(
                f"OvalEdge client_credentials exchange failed: "
                f"{response.status_code} {response.text}"
            )
        try:
            payload: Any = response.json()
        except Exception:
            payload = response.text
        return _extract_token(payload)


async def get_or_refresh_local_token() -> str:
    """
    Return cached local JWT if still valid, otherwise exchange for a new one.
    Cache is process-memory only.
    """
    cached = auth_context.local_cached_oe_jwt
    if cached and not is_token_expiring(cached):
        auth_context.current_oe_jwt.set(cached)
        return cached
    token = await exchange_client_credentials()
    auth_context.local_cached_oe_jwt = token
    auth_context.current_oe_jwt.set(token)
    return token
