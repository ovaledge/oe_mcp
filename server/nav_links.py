"""Normalize OvalEdge in-app navigation links for MCP tool responses."""

from __future__ import annotations

from server.config import settings

_HASH_PREFIX = "#nav/"


def extract_hash_nav_link(nav: str | None) -> str:
    """Return the in-app hash route (#nav/...) from a nav link or hyperlink."""
    trimmed = (nav or "").strip()
    if not trimmed:
        return ""
    idx = trimmed.find(_HASH_PREFIX)
    if idx >= 0:
        return trimmed[idx:]
    return ""


def build_absolute_nav_url(relative: str | None) -> str:
    """Build a full URL: {OVALEDGE_BASE_URL}/#nav/..."""
    rel = extract_hash_nav_link(relative)
    if not rel:
        return ""
    base = settings.ovaledge_base_url.strip().rstrip("/") + "/"
    return base + rel


def normalize_nav_link(
    nav: str | None,
    *,
    hyperlink: str | None = None,
) -> tuple[str, str]:
    """
    Return (relative_hash_route, absolute_url).

    Always rebuilds the absolute URL from the hash route and OVALEDGE_BASE_URL so
  malformed backend values (e.g. duplicated base URL) are not passed through.
    """
    relative = extract_hash_nav_link(nav) or extract_hash_nav_link(hyperlink)
    absolute = build_absolute_nav_url(relative) if relative else ""
    return relative, absolute
