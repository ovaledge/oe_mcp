import time
from typing import Any

import httpx
from jose import jwt

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


def _looks_like_jwt(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 3 and all(p.strip() for p in parts)


def _introspection_configured() -> bool:
    """True when we can call Okta (or other) introspect — preferred for OvalEdge RS pods."""
    return bool((settings.oauth_client_id or "").strip()) and bool(
        (settings.oauth_introspection_url or "").strip()
        or (settings.oauth_issuer or "").strip()
    )


def introspection_url() -> str:
    configured = (settings.oauth_introspection_url or "").strip()
    if configured:
        return configured.rstrip("/")
    issuer = (settings.oauth_issuer or "").strip().rstrip("/")
    if not issuer:
        raise OAuthDiscoveryError(
            "oauth_introspection_url is not set and oauth_issuer is empty "
            "(cannot derive {issuer}/v1/introspect)"
        )
    return f"{issuer}/v1/introspect"


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


async def _verify_jwt_access_token(token: str) -> dict[str, Any]:
    """
    Validate JWT access token using IdP JWKS from discovery.

    ``OAUTH_AUDIENCE`` is optional: when set, ``aud`` must match; when empty,
    signature + issuer are still verified (typical for Okta default AS JWTs).
    """
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

    decode_kwargs: dict[str, Any] = {
        "algorithms": ["RS256", "RS384", "RS512"],
        "issuer": issuer,
    }
    audience = (settings.oauth_audience or "").strip()
    if audience:
        decode_kwargs["audience"] = audience

    claims: dict[str, Any] = jwt.decode(token, jwks, **decode_kwargs)
    return claims


async def _verify_opaque_access_token(token: str) -> dict[str, Any]:
    """
    RFC 7662 token introspection (Okta access tokens — JWT or opaque).

    Matches OvalEdge ``CustomAuthoritiesOpaqueTokenIntrospector``: the API pod
    introspects the same token; MCP validates before forwarding.
    """
    client_id = (settings.oauth_client_id or "").strip()
    if not client_id:
        raise OAuthDiscoveryError(
            "oauth_client_id is not set (required to introspect opaque access tokens)"
        )

    url = introspection_url()
    data: dict[str, str] = {"token": token}
    secret = (settings.oauth_client_secret or "").strip()
    post_kwargs: dict[str, Any] = {
        "data": data,
        "headers": {"Accept": "application/json"},
    }
    if secret:
        post_kwargs["auth"] = (client_id, secret)
    else:
        data["client_id"] = client_id

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, **post_kwargs)

    if response.status_code != 200:
        raise ValueError(
            f"Token introspection failed: HTTP {response.status_code} {response.text[:200]}"
        )

    try:
        body = response.json()
    except Exception as e:
        raise ValueError(f"Token introspection returned non-JSON: {e}") from e

    if not isinstance(body, dict):
        raise ValueError("Token introspection returned non-object JSON")

    if body.get("active") is not True:
        raise ValueError("Access token is not active (introspection)")

    token_iss = body.get("iss")
    if isinstance(token_iss, str) and token_iss.strip():
        assert_issuer_allowed(normalize_issuer(token_iss), context="Introspection")

    audience = (settings.oauth_audience or "").strip()
    if audience:
        aud = body.get("aud")
        if isinstance(aud, str) and aud.strip() and aud.strip() != audience:
            raise ValueError(f"Token audience mismatch: expected {audience!r}, got {aud!r}")
        if isinstance(aud, list) and aud and audience not in aud:
            raise ValueError(f"Token audience mismatch: expected {audience!r} in {aud!r}")

    return body


async def verify_oauth_access_token(token: str) -> dict[str, Any]:
    """
    Validate OAuth access token.

    Prefer **introspection** when ``OAUTH_CLIENT_ID`` (+ issuer/introspect URL) is
    configured — same path OvalEdge uses for Okta. Falls back to JWT JWKS when
    introspection is unavailable or fails for a JWT-shaped token.

    ``OAUTH_AUDIENCE`` is optional for both paths.
    Credentials stay on the server (``OAUTH_CLIENT_ID`` / ``OAUTH_CLIENT_SECRET``);
    MCP clients must not put them in ``mcp.json``.
    """
    token = (token or "").strip()
    if not token:
        raise ValueError("Empty access token")

    if _introspection_configured():
        try:
            return await _verify_opaque_access_token(token)
        except Exception:
            if not _looks_like_jwt(token):
                raise
            # JWT-shaped: allow JWKS fallback if introspect is down / misconfigured.
            return await _verify_jwt_access_token(token)

    if _looks_like_jwt(token):
        return await _verify_jwt_access_token(token)

    return await _verify_opaque_access_token(token)
