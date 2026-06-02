"""Query/body parameter helpers for OvalEdge MCP tools."""

from __future__ import annotations

from typing import Any


def drop_none(**kwargs: object) -> dict[str, Any]:
    """Omit keys whose values are None (OvalEdge query params)."""
    return {k: v for k, v in kwargs.items() if v is not None}
