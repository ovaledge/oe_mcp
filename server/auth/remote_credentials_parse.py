"""
Parse OvalEdge user credentials from remote_credentials HTTP headers.

Supports:
- ``X-OvalEdge-Credentials: <token>::<secret>`` (single header; Copilot Studio API key)
- ``X-OvalEdge-Token`` + ``X-OvalEdge-Secret`` (legacy / multi-header MCP clients)

OvalEdge issuance guarantees neither token nor secret contains ``::``.
"""

from __future__ import annotations

from server.constants import (
    CREDENTIALS_COMBINED_MAX_LEN,
    CREDENTIALS_COMBINED_SEPARATOR,
    CREDENTIALS_HEADER_MAX_LEN,
    HEADER_OE_USER_COMBINED,
    HEADER_OE_USER_SECRET,
    HEADER_OE_USER_TOKEN,
)


def _part_is_valid(value: str) -> bool:
    return bool(value) and len(value) <= CREDENTIALS_HEADER_MAX_LEN and not any(c.isspace() for c in value)


def _parse_combined(raw: str) -> tuple[str, str] | None:
    value = raw.strip()
    if not value or len(value) > CREDENTIALS_COMBINED_MAX_LEN:
        return None
    if CREDENTIALS_COMBINED_SEPARATOR not in value:
        return None
    token, secret = value.split(CREDENTIALS_COMBINED_SEPARATOR, 1)
    token = token.strip()
    secret = secret.strip()
    if not _part_is_valid(token) or not _part_is_valid(secret):
        return None
    return token, secret


def parse_remote_user_credentials(
    *,
    combined_hdr: str = "",
    token_hdr: str = "",
    secret_hdr: str = "",
) -> tuple[str, str] | None:
    """
    Return (user_token, user_secret) when credentials are present and valid; else None.
    Combined header wins when non-empty after strip.
    """
    combined = combined_hdr.strip()
    if combined:
        return _parse_combined(combined)

    user_token = token_hdr.strip()
    user_secret = secret_hdr.strip()
    if not _part_is_valid(user_token) or not _part_is_valid(user_secret):
        return None
    return user_token, user_secret


def remote_credentials_auth_hint() -> str:
    """Human-readable auth hint for error JSON (no secret values)."""
    return (
        f"{HEADER_OE_USER_COMBINED} (<token>{CREDENTIALS_COMBINED_SEPARATOR}<secret>), or "
        f"{HEADER_OE_USER_TOKEN} and {HEADER_OE_USER_SECRET}"
    )
