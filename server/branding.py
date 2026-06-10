"""MCP server branding (icon served from ``server/static/``)."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from urllib.parse import urlparse

from mcp.types import Icon

from server.config import settings

MCP_BRAND_ICON_FILENAME = "ovaledge-mcp-icon.png"
MCP_BRAND_ICON_ROUTE = f"/brand/{MCP_BRAND_ICON_FILENAME}"

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def brand_icon_file() -> Path:
    return _STATIC_DIR / MCP_BRAND_ICON_FILENAME


def _stdio_transport() -> bool:
    """True for ``oe-mcp-local`` stdio; HTTP/Lambda must not set ``MCP_STDIO_TRANSPORT``."""
    return os.environ.get("MCP_STDIO_TRANSPORT", "").strip().lower() in ("1", "true", "yes")


def _is_localhost_host(host: str | None) -> bool:
    return (host or "").lower() in ("127.0.0.1", "localhost", "::1")


def brand_icon_http_base() -> str:
    """
    Base URL for the public icon route.

    Prefers ``MCP_BRAND_ICON_BASE_URL`` (HTTPS deploy) over ``MCP_PUBLIC_BASE_URL``.
    """
    for candidate in (settings.mcp_brand_icon_base_url, settings.mcp_public_base_url):
        base = (candidate or "").strip().rstrip("/")
        if base:
            return base
    return ""


def brand_icon_public_url() -> str | None:
    base = brand_icon_http_base()
    if not base:
        return None
    return f"{base}{MCP_BRAND_ICON_ROUTE}"


def _data_uri_icon_src() -> str:
    payload = base64.standard_b64encode(brand_icon_file().read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def resolve_mcp_icon_src() -> str | None:
    """
    Icon URL for MCP ``initialize`` metadata.

    - **stdio**: embedded data URI (Cursor usually shows a letter avatar anyway).
    - **HTTP / Lambda**: HTTPS ``GET /brand/...`` when configured. Cursor generally
      **does not** load icons from ``http://127.0.0.1`` — set ``MCP_BRAND_ICON_BASE_URL``
      to your deployed API Gateway URL for local dev.
    """
    icon_file = brand_icon_file()
    if not icon_file.is_file():
        return None
    if _stdio_transport():
        return _data_uri_icon_src()

    public_url = brand_icon_public_url()
    if public_url:
        host = urlparse(public_url).hostname
        if not _is_localhost_host(host):
            return public_url
    return _data_uri_icon_src()


def mcp_server_icons() -> list[Icon] | None:
    src = resolve_mcp_icon_src()
    if src is None:
        return None
    icons = [
        Icon(
            src=src,
            mimeType="image/png",
            sizes=["48x48"],
        ),
        Icon(
            src=src,
            mimeType="image/png",
            sizes=["96x96"],
        ),
    ]
    if src.startswith("data:"):
        icons.append(Icon(src=src, mimeType="image/png", sizes=["any"]))
    return icons
