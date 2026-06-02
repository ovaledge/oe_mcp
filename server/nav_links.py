"""Normalize OvalEdge in-app navigation links for MCP tool responses."""

from __future__ import annotations

from server.config import get_settings

_HASH_PREFIX = "#nav/"


def get_link_base_url() -> str:
    """
    Base URL for user-facing links (tag summary, redirect, audit).

    Uses OVALEDGE_LINK_BASE_URL when set (pod/custom hostname), else OVALEDGE_BASE_URL.
    For local dev, 127.0.0.1 is rewritten to localhost so links match typical browser URLs.
    """
    cfg = get_settings()
    override = cfg.ovaledge_link_base_url.strip().rstrip("/")
    base = override or cfg.ovaledge_base_url.strip().rstrip("/")
    if cfg.ovaledge_prefer_localhost_links and "127.0.0.1" in base:
        base = base.replace("127.0.0.1", "localhost")
    return base


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
    """Build a full URL: {link_base}/#nav/..."""
    rel = extract_hash_nav_link(relative)
    if not rel:
        return ""
    base = get_link_base_url() + "/"
    return base + rel


def markdown_link(label: str, url: str) -> str:
    """Markdown hyperlink for chat clients that render MD."""
    safe_label = (label or "link").replace("[", "\\[").replace("]", "\\]")
    trimmed = (url or "").strip()
    if not trimmed:
        return safe_label
    return f"[{safe_label}]({trimmed})"


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
