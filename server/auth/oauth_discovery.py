"""
Fetch Authorization Server metadata for any OIDC / OAuth 2.x compliant IdP.

Tries OpenID Discovery first, then RFC 8414 ``oauth-authorization-server``.
"""

import time
from typing import Any, cast

import httpx

from server.config import settings

_DISCOVERY_TTL_SECONDS = 3600.0
# Normalized issuer base URL -> (monotonic_ts, metadata dict)
_metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class OAuthDiscoveryError(Exception):
    """Issuer URL is missing or discovery documents could not be loaded."""


def _normalize_issuer_base(url: str) -> str:
    return url.strip().rstrip("/")


def _issuer_base_from_settings() -> str:
    raw = settings.oauth_issuer.strip().rstrip("/")
    if not raw:
        raise OAuthDiscoveryError("oauth_issuer is not set (required for remote MCP)")
    return raw


def clear_metadata_cache() -> None:
    """Reset process-local cache (tests)."""
    global _metadata_cache
    _metadata_cache = {}


async def get_authorization_server_metadata_for_base(issuer_base: str) -> dict[str, Any]:
    """
    Load OIDC / OAuth AS metadata for a given issuer origin.

    ``issuer_base`` is typically ``iss`` from the JWT without a trailing slash, e.g.
    ``https://tenant.auth0.com`` or ``https://tenant.auth0.com`` for
    ``iss`` = ``https://tenant.auth0.com/``.

    Auth0: access tokens often use the canonical ``*.auth0.com`` issuer while login may use a
    custom domain — callers validate tokens using the **token's** ``iss``, not only
    ``oauth_issuer`` in settings.
    """
    base = _normalize_issuer_base(issuer_base)
    if not base:
        raise OAuthDiscoveryError("issuer base is empty")

    now = time.monotonic()
    cached = _metadata_cache.get(base)
    if cached is not None:
        ts, data = cached
        if (now - ts) < _DISCOVERY_TTL_SECONDS:
            return data

    oidc_url = f"{base}/.well-known/openid-configuration"
    oauth_url = f"{base}/.well-known/oauth-authorization-server"
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=10) as client:
        for url in (oidc_url, oauth_url):
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    errors.append(f"{url} -> HTTP {response.status_code}")
                    continue
                data = cast(dict[str, Any], response.json())
            except Exception as e:
                errors.append(f"{url} -> {e!s}")
                continue

            issuer = data.get("issuer")
            authz = data.get("authorization_endpoint")
            token_ep = data.get("token_endpoint")
            jwks = data.get("jwks_uri")
            if not all(isinstance(x, str) and x for x in (issuer, authz, token_ep, jwks)):
                errors.append(
                    f"{url} -> missing issuer, authorization_endpoint, token_endpoint, or jwks_uri"
                )
                continue

            _metadata_cache[base] = (now, data)
            return data

    raise OAuthDiscoveryError(
        f"Could not load OIDC or OAuth AS metadata for issuer {base!r}. " + "; ".join(errors)
    )


async def get_authorization_server_metadata() -> dict[str, Any]:
    """
    Metadata for ``oauth_issuer`` in settings (MCP discovery proxy, health, etc.).
    """
    return await get_authorization_server_metadata_for_base(_issuer_base_from_settings())
