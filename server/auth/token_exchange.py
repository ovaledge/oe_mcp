import json
import time
from typing import Any, cast

import httpx
from jose import jwt  # type: ignore[import-untyped]

from server.auth import context as auth_context
from server.config import settings
from server.constants import JWT_REFRESH_LEEWAY_SECONDS, OVALEDGE_TOKEN_EXCHANGE_PATH


class TokenExchangeError(Exception):
    pass


def _payload_from_token_exchange_response(response: httpx.Response) -> Any:
    """Parse JSON or raw text; fail clearly on empty 200 responses."""
    if not response.content or not response.content.strip():
        raise TokenExchangeError(
            "OvalEdge token exchange returned an empty body (HTTP 200). "
            "Expected JSON with a token field or a raw JWT. "
            "Check that POST /api/user/token/generate accepts your payload and returns a token."
        )
    try:
        return response.json()
    except Exception:
        return response.text


def _extract_token(body: Any) -> str:
    """Extract OvalEdge JWT from API response (JSON object, nested fields, or raw JWT text)."""
    if body is None:
        raise TokenExchangeError("Token exchange response body is null")

    if isinstance(body, str):
        s = body.strip()
        if not s:
            raise TokenExchangeError(
                "Token exchange returned an empty body; expected a JWT or JSON with a token field"
            )
        if s.startswith("{"):
            try:
                return _extract_token(json.loads(s))
            except (json.JSONDecodeError, TokenExchangeError):
                pass
        return s

    if isinstance(body, dict):
        err_msg = body.get("message") or body.get("error") or body.get("error_description")
        if body.get("success") is False and err_msg:
            raise TokenExchangeError(f"OvalEdge token exchange declined: {err_msg}")

        for key in (
            "token",
            "access_token",
            "jwt",
            "accessToken",
            "bearerToken",
            "jwtToken",
            "userToken",
            "result",
        ):
            val = body.get(key)
            if val is not None and str(val).strip():
                if isinstance(val, dict):
                    return _extract_token(val)
                return str(val).strip()

        data = body.get("data")
        if isinstance(data, (dict, str, list)):
            try:
                return _extract_token(data)
            except TokenExchangeError:
                pass

        keys = sorted(body.keys())
        raise TokenExchangeError(
            "Token exchange JSON has no recognizable token field "
            f"(tried token, access_token, jwt, data, …); keys={keys}"
        )

    if isinstance(body, list) and len(body) == 1:
        return _extract_token(body[0])

    raise TokenExchangeError(
        f"Token exchange response unsupported payload type: {type(body).__name__}"
    )


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


async def exchange_oauth_access_token(oauth_access_token: str) -> str:
    """
    Remote MCP path.
    Exchange a validated OAuth access token for an OvalEdge user-scoped JWT.
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
                "userToken": oauth_access_token,
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
        payload = _payload_from_token_exchange_response(response)
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
        payload = _payload_from_token_exchange_response(response)
        return _extract_token(payload)


def invalidate_local_jwt_cache() -> None:
    """
    Drop the in-memory OvalEdge JWT so the next ``get_or_refresh_local_token``
    runs client_credentials again.

    Used when OvalEdge returns 401 (e.g. server-side session TTL) but the JWT
    has no ``exp`` claim, so proactive refresh never ran.
    """
    auth_context.local_cached_oe_jwt = ""
    auth_context.current_oe_jwt.set("")


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
