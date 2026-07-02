"""Trusted OAuth/OIDC issuer allowlist for remote MCP JWT validation."""

from __future__ import annotations

from server.config import settings


def normalize_issuer(value: str) -> str:
    return value.strip().rstrip("/")


def oauth_allowed_issuer_set() -> frozenset[str]:
    """
    Trusted JWT ``iss`` values and discovered issuer URLs.

    Built from ``OAUTH_ISSUER`` plus comma-separated ``OAUTH_ALLOWED_ISSUERS``.
    Register both Auth0 custom-domain and canonical ``*.auth0.com`` issuers when both
    appear in tokens.
    """
    allowed: set[str] = set()
    if settings.oauth_issuer.strip():
        allowed.add(normalize_issuer(settings.oauth_issuer))
    raw = settings.oauth_allowed_issuers.strip()
    if raw:
        for part in raw.split(","):
            if part.strip():
                allowed.add(normalize_issuer(part))
    return frozenset(allowed)


def assert_issuer_allowed(issuer: str, *, context: str) -> None:
    allowed = oauth_allowed_issuer_set()
    if not allowed:
        from server.auth.oauth_discovery import OAuthDiscoveryError

        raise OAuthDiscoveryError(
            "No OAuth issuers configured. Set OAUTH_ISSUER and/or OAUTH_ALLOWED_ISSUERS "
            "before enabling AUTH_MODE=remote."
        )
    normalized = normalize_issuer(issuer)
    if normalized not in allowed:
        raise ValueError(f"{context} issuer {normalized!r} is not in the OAuth allowlist")
