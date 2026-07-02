"""MCP server branding icon (static asset + public route)."""

from __future__ import annotations

import pytest

from server.branding import (
    MCP_BRAND_ICON_ROUTE,
    brand_icon_file,
    brand_icon_public_url,
    mcp_server_icons,
    resolve_mcp_icon_src,
)
from server.config import settings


class TestBrandingHelpers:
    def test_brand_icon_file_exists(self) -> None:
        assert brand_icon_file().is_file()

    def test_resolve_icon_src_uses_public_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MCP_STDIO_TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "mcp_brand_icon_base_url", "")
        monkeypatch.setattr(settings, "mcp_public_base_url", "https://mcp.example.com")
        src = resolve_mcp_icon_src()
        assert src == f"https://mcp.example.com{MCP_BRAND_ICON_ROUTE}"

    def test_resolve_icon_src_prefers_brand_icon_base_url(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("MCP_STDIO_TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "mcp_brand_icon_base_url", "https://brand.example.com")
        monkeypatch.setattr(settings, "mcp_public_base_url", "http://127.0.0.1:8000")
        src = resolve_mcp_icon_src()
        assert src == f"https://brand.example.com{MCP_BRAND_ICON_ROUTE}"

    def test_resolve_icon_src_stdio_uses_data_uri_even_with_public_base_url(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MCP_STDIO_TRANSPORT", "true")
        monkeypatch.setattr(settings, "mcp_public_base_url", "https://mcp.example.com")
        src = resolve_mcp_icon_src()
        assert src is not None
        assert src.startswith("data:image/png;base64,")

    def test_resolve_icon_src_localhost_http_falls_back_to_data_uri(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("MCP_STDIO_TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "mcp_brand_icon_base_url", "")
        monkeypatch.setattr(settings, "mcp_public_base_url", "http://127.0.0.1:8000")
        src = resolve_mcp_icon_src()
        assert src is not None
        assert src.startswith("data:image/png;base64,")

    def test_resolve_icon_src_data_uri_when_no_public_url(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("MCP_STDIO_TRANSPORT", raising=False)
        monkeypatch.setattr(settings, "mcp_brand_icon_base_url", "")
        monkeypatch.setattr(settings, "mcp_public_base_url", "")
        src = resolve_mcp_icon_src()
        assert src is not None
        assert src.startswith("data:image/png;base64,")

    def test_brand_icon_public_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "mcp_brand_icon_base_url", "https://x.example.com")
        assert brand_icon_public_url() == f"https://x.example.com{MCP_BRAND_ICON_ROUTE}"

    def test_mcp_server_icons_returns_png_icons(self) -> None:
        icons = mcp_server_icons()
        assert icons is not None
        assert len(icons) >= 2
        assert all(i.mimeType == "image/png" for i in icons)


class TestBrandIconRoute:
    async def test_brand_icon_route_returns_png(self) -> None:
        from entrypoints.lambda_handler import brand_icon

        resp = await brand_icon()
        assert resp.status_code == 200
        assert resp.media_type == "image/png"
        assert resp.path == brand_icon_file()

    async def test_favicon_route_returns_png(self) -> None:
        from entrypoints.lambda_handler import favicon

        resp = await favicon()
        assert resp.status_code == 200
        assert resp.media_type == "image/png"

    async def test_brand_icon_unauthenticated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from starlette.testclient import TestClient

        from entrypoints.lambda_handler import app
        from server.config import settings

        monkeypatch.setattr(settings, "ovaledge_user_token", "")
        monkeypatch.setattr(settings, "ovaledge_user_secret", "")

        with TestClient(app) as client:
            r = client.get(MCP_BRAND_ICON_ROUTE)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")

    async def test_create_mcp_registers_icons(self) -> None:
        from server.app import create_mcp

        mcp = create_mcp()
        assert mcp._mcp_server.icons is not None  # noqa: SLF001
