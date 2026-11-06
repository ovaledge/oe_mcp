"""Self-contained MCP Apps HTML for catalog read tools (no CDN)."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE = (Path(__file__).with_name("catalog_app.html")).read_text(encoding="utf-8")

_VIEWS = frozenset({"explorer", "details", "lineage", "drift"})


def catalog_app_html(view: str) -> str:
    """Return the catalog MCP App document for one view id."""
    if view not in _VIEWS:
        raise ValueError(f"unknown catalog app view: {view!r}")
    return _TEMPLATE.replace("__VIEW__", view)
