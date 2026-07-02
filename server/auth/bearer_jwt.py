import time
from typing import Any

import httpx
from jose import jwt  # type: ignore[import-untyped]

from server.auth.issuer_allowlist import assert_issuer_allowed, normalize_issuer
from server.auth.oauth_discovery import (
    OAuthDiscoveryError,
    get_authorization_server_metadata_for_base,
)
from server.config import settings

_JWKS_TTL_SECONDS = 3600.0
_jwks_cache: dict[str, Any] | None = None
_jwks_url_cached: str | None = None
_jwks_fetched_at: float = 0.0


def clear_jwks_cache() -> None:
    global _jwks_cache, _jwks_url_cached, _jwks_fetched_at
    _jwks_cache = None
    _jwks_url_cached = None
    _jwks_fetched_at = 0.0


async def _get_jwks(jwks_uri: str) -> dict[str, Any]:
    global _jwks_cache, _jwks_url_cached, _jwks_fetched_at

    now = time.monotonic()
    cached = _jwks_cache
    if (
        _jwks_url_cached == jwks_uri
        and cached is not None
        and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS
    ):
        return cached

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(jwks_uri)
        response.raise_for_status()
        body = response.json()

    if not isinstance(body, dict):
        raise ValueError("JWKS endpoint returned non-object JSON")
    jwks: dict[str, Any] = body
    _jwks_cache = jwks
    _jwks_url_cached = jwks_uri
    _jwks_fetched_at = now
    return jwks


async def verify_oauth_access_token(token: str) -> dict[str, Any]:
    """
    Validate OAuth access token (JWT) using IdP JWKS from discovery.

    Discovery is loaded from the token's ``iss`` claim (not only ``oauth_issuer``), so Auth0
    tokens that use the canonical ``*.auth0.com`` issuer still validate when
    ``oauth_issuer`` is a custom domain used for the MCP metadata proxy.

    The token ``iss`` and discovered issuer must both appear in ``OAUTH_ISSUER`` /
    ``OAUTH_ALLOWED_ISSUERS``. ``aud`` must match ``oauth_audience``.
    """
    if not settings.oauth_audience.strip():
        raise OAuthDiscoveryError("oauth_audience is not set (required for remote MCP)")

    try:
        unverified: dict[str, Any] = jwt.get_unverified_claims(token)
    except Exception as e:
        raise ValueError(f"Not a readable JWT: {e}") from e

    token_iss = unverified.get("iss")
    if not isinstance(token_iss, str) or not token_iss.strip():
        raise ValueError("Token missing iss claim")

    token_iss_norm = normalize_issuer(token_iss)
    assert_issuer_allowed(token_iss_norm, context="Token")

    meta = await get_authorization_server_metadata_for_base(token_iss_norm)
    issuer = meta["issuer"]
    assert_issuer_allowed(normalize_issuer(issuer), context="Discovered")
    jwks_uri = meta["jwks_uri"]
    jwks = await _get_jwks(jwks_uri)

    claims: dict[str, Any] = jwt.decode(
        token,
        jwks,
        algorithms=["RS256", "RS384", "RS512"],
        audience=settings.oauth_audience,
        issuer=issuer,
    )
    return claims
