import asyncio
import hashlib
import json
import time
from typing import Any, cast

import httpx
from jose import jwt

from server.auth import context as auth_context
from server.config import settings
from server.constants import (
    CREDENTIALS_REFRESH_LEEWAY_SECONDS,
    JWT_REFRESH_LEEWAY_SECONDS,
    OVALEDGE_TOKEN_EXCHANGE_PATH,
)

_local_token_lock: asyncio.Lock | None = None


def _get_local_token_lock() -> asyncio.Lock:
    global _local_token_lock
    if _local_token_lock is None:
        _local_token_lock = asyncio.Lock()
    return _local_token_lock


class TokenExchangeError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def jwt_exp_epoch(token: str) -> int:
    """Unix seconds from JWT ``exp`` claim, or 0 if missing / unparsable."""
    try:
        claims = cast(dict[str, Any], jwt.get_unverified_claims(token))
        exp = claims.get("exp")
        if exp is None:
            return 0
        return int(exp)
    except Exception:
        return 0


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

    Wire contract (OvalEdge ``POST /api/user/token/generate``): JSON body
    ``{"userToken": "<IdP access token>"}``. Response JWT is parsed by
    ``_extract_token`` (supports ``token``, ``access_token``, ``jwt``, ``data``, or raw text).
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
                f"OvalEdge token exchange failed: {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        payload = _payload_from_token_exchange_response(response)
        return _extract_token(payload)


def _oauth_exchange_cache_key(oauth_access_token: str) -> str:
    """Stable cache key for the OAuth->OvalEdge JWT exchange; never logged."""
    h = hashlib.sha256()
    h.update(b"oauth-exchange:")
    h.update(oauth_access_token.encode("utf-8"))
    return h.hexdigest()


async def get_or_refresh_oauth_exchanged_token(oauth_access_token: str) -> str:
    """
    Remote OAuth path: return a cached OvalEdge JWT for this IdP access token when still
    fresh, otherwise exchange via ``POST /api/user/token/generate`` and cache the result.

    Removes a token/generate round-trip on every MCP request when
    ``ovaledge_remote_forward_idp_token`` is False. The cache key is a digest of the
    access token (never logged); entries expire with the OvalEdge JWT's own ``exp``.
    """
    from server.auth.credentials_cache import (
        CachedJwtEntry,
        get_default_credentials_cache,
    )

    key = _oauth_exchange_cache_key(oauth_access_token)
    cache = get_default_credentials_cache()

    entry = await cache.get_entry(key)
    if entry and not is_token_expiring(
        entry.jwt, leeway_seconds=CREDENTIALS_REFRESH_LEEWAY_SECONDS
    ):
        return entry.jwt

    async with cache.refresh_lock(key):
        entry = await cache.get_entry(key)
        if entry and not is_token_expiring(
            entry.jwt, leeway_seconds=CREDENTIALS_REFRESH_LEEWAY_SECONDS
        ):
            return entry.jwt
        new_jwt = await exchange_oauth_access_token(oauth_access_token)
        await cache.set_entry(
            key,
            CachedJwtEntry(jwt=new_jwt, exp_epoch=jwt_exp_epoch(new_jwt)),
        )
        return new_jwt


async def exchange_client_credentials() -> str:
    """
    Local MCP path.
    Exchange OvalEdge user token + user secret for an OvalEdge JWT at startup.

    Wire contract: ``POST /api/user/token/generate`` with
    ``{"userToken": "...", "userSecret": "..."}``; JWT via ``_extract_token``.
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
                f"{response.status_code} {response.text}",
                status_code=response.status_code,
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


async def exchange_user_credentials(user_token: str, user_secret: str) -> str:
    """
    Remote multi-user credentials path (headers → OvalEdge JWT).

    Same wire format as ``exchange_client_credentials``, but credentials come from
    request headers rather than process env. Prefer ``get_or_refresh_user_token`` so
    JWT is cached per credential key.
    """
    async with httpx.AsyncClient(
        base_url=settings.ovaledge_base_url,
        timeout=settings.ovaledge_timeout_seconds,
    ) as client:
        response = await client.post(
            OVALEDGE_TOKEN_EXCHANGE_PATH,
            json={
                "userToken": user_token,
                "userSecret": user_secret,
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        if response.status_code == 401:
            raise TokenExchangeError(
                "Invalid OvalEdge user token or secret",
                status_code=401,
            )
        if response.status_code != 200:
            raise TokenExchangeError(
                f"OvalEdge user-cred exchange failed: {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        payload = _payload_from_token_exchange_response(response)
        return _extract_token(payload)


async def get_or_refresh_user_token(user_token: str, user_secret: str) -> str:
    """
    Return cached OvalEdge JWT for this credential key when fresh; otherwise exchange.

    Cache key is ``credential_cache_key(user_token, user_secret)`` — never logged.
    """
    from server.auth.credentials_cache import (
        CachedJwtEntry,
        credential_cache_key,
        get_default_credentials_cache,
        get_default_negative_credentials_cache,
    )

    key = credential_cache_key(user_token, user_secret)
    cache = get_default_credentials_cache()
    negative = get_default_negative_credentials_cache()

    if await negative.is_blocked(key):
        raise TokenExchangeError(
            "Invalid OvalEdge user token or secret",
            status_code=401,
        )

    entry = await cache.get_entry(key)
    if entry and not is_token_expiring(
        entry.jwt,
        leeway_seconds=CREDENTIALS_REFRESH_LEEWAY_SECONDS,
    ):
        return entry.jwt

    async with cache.refresh_lock(key):
        if await negative.is_blocked(key):
            raise TokenExchangeError(
                "Invalid OvalEdge user token or secret",
                status_code=401,
            )
        entry = await cache.get_entry(key)
        if entry and not is_token_expiring(
            entry.jwt,
            leeway_seconds=CREDENTIALS_REFRESH_LEEWAY_SECONDS,
        ):
            return entry.jwt
        try:
            new_jwt = await exchange_user_credentials(user_token, user_secret)
        except TokenExchangeError as e:
            if e.status_code == 401:
                await negative.mark_blocked(key)
            raise
        await negative.forget(key)
        await cache.set_entry(
            key,
            CachedJwtEntry(jwt=new_jwt, exp_epoch=jwt_exp_epoch(new_jwt)),
        )
        return new_jwt


async def get_or_refresh_local_token() -> str:
    """
    Return cached local JWT if still valid, otherwise exchange for a new one.
    Cache is process-memory only. A refresh lock prevents concurrent token/generate
    stampedes (OvalEdge allows one active JWT per user token+secret).
    """
    cached = auth_context.local_cached_oe_jwt
    if cached and not is_token_expiring(cached):
        auth_context.current_oe_jwt.set(cached)
        return cached

    async with _get_local_token_lock():
        cached = auth_context.local_cached_oe_jwt
        if cached and not is_token_expiring(cached):
            auth_context.current_oe_jwt.set(cached)
            return cached
        token = await exchange_client_credentials()
        auth_context.local_cached_oe_jwt = token
        auth_context.current_oe_jwt.set(token)
        return token
