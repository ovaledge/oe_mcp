"""MCP Apps UI metadata for hosts that render ``ui://`` resources.

Non-Apps hosts ignore this metadata and still receive the tool's JSON body.
Do not use Prefab ``app=True`` — that replaces the model-visible result.
"""

from __future__ import annotations

from fastmcp.apps import AppConfig


def catalog_app_config(resource_uri: str) -> AppConfig:
    """Point a catalog read tool at a self-contained HTML view (no CDN)."""
    return AppConfig(resource_uri=resource_uri, prefers_border=True)


def catalog_app_meta(resource_uri: str) -> dict[str, str]:
    """ChatGPT Apps SDK looks for this key in addition to MCP Apps ``meta.ui``."""
    return {"openai/outputTemplate": resource_uri}
