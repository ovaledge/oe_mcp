import time
from typing import Any

import httpx
from jose import jwt  # type: ignore[import-untyped]

from server.config import settings

# Module-level JWKS cache with TTL.
# Safe — Okta rotates keys rarely (weeks/months).
# Refreshed on cold start and after TTL expiry.
_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS: float = 3600  # 1 hour


async def _get_jwks() -> dict[str, Any]:
    """
    Fetch JWKS from Okta custom auth server.
    Cached in module-level variable with 1-hour TTL.
    Uses async httpx to avoid blocking the event loop.
    """
    global _jwks_cache, _jwks_fetched_at

    now = time.monotonic()
    if _jwks_cache is not None and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    url = f"{settings.okta_domain}/oauth2/{settings.okta_auth_server_id}/v1/keys"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url)
        response.raise_for_status()
        body = response.json()

    _jwks_cache = body
    _jwks_fetched_at = now
    return _jwks_cache


async def verify_okta_token(token: str) -> dict[str, Any]:
    """
    Validate Okta JWT from custom auth server.
    Returns decoded claims. Raises JWTError if invalid or expired.

    Expected claims:
        sub    — Okta user ID
        email  — user email
        groups — Okta groups (if configured in custom auth server)
    """
    jwks = await _get_jwks()
    issuer = f"{settings.okta_domain}/oauth2/{settings.okta_auth_server_id}"
    claims: dict[str, Any] = jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=settings.okta_audience,
        issuer=issuer,
    )
    return claims
