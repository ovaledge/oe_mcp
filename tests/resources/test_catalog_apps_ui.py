"""MCP Apps UI resources for catalog read tools (JSON body unchanged)."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastmcp import FastMCP
from fastmcp.client import Client

from server.app import create_mcp
from server.constants import (
    MCP_UI_ASSET_DETAILS,
    MCP_UI_ASSET_EXPLORER,
    MCP_UI_ASSET_LINEAGE,
    MCP_UI_METADATA_CHANGES,
)
from server.mcp_surface import MCP_UI_RESOURCE_URIS
from server.resources.apps.html import catalog_app_html
from server.tools import catalog
from tests.helpers import get_tool_fn, get_tool_object

_UI_BY_TOOL = {
    "asset_explorer": MCP_UI_ASSET_EXPLORER,
    "asset_details": MCP_UI_ASSET_DETAILS,
    "asset_lineage": MCP_UI_ASSET_LINEAGE,
    "metadata_changes_between_crawls": MCP_UI_METADATA_CHANGES,
}


def test_catalog_app_html_is_self_contained() -> None:
    html = catalog_app_html("explorer")
    assert 'id="root"' in html
    assert "__VIEW__" not in html
    assert "explorer" in html
    assert "https://cdn" not in html
    assert "unpkg.com" not in html


def test_catalog_app_html_views_are_distinct() -> None:
    views = {catalog_app_html(v) for v in ("explorer", "details", "lineage", "drift")}
    assert len(views) == 4


async def test_catalog_read_tools_advertise_ui_resource() -> None:
    mcp = FastMCP(name="test", version="0.0.1")
    catalog.register(mcp)
    for name, uri in _UI_BY_TOOL.items():
        tool = await get_tool_object(mcp, name)
        meta = tool.meta or {}
        ui = meta.get("ui")
        assert isinstance(ui, dict), f"{name} missing meta.ui"
        assert ui.get("resourceUri") == uri
        assert meta.get("openai/outputTemplate") == uri


async def test_catalog_apps_resources_are_html(mock_oe_client: AsyncMock) -> None:
    mcp = create_mcp()
    async with Client(mcp) as client:
        resources = await client.list_resources()
        uris = {str(r.uri) for r in resources}
        assert MCP_UI_RESOURCE_URIS <= uris
        for uri in MCP_UI_RESOURCE_URIS:
            contents = await client.read_resource(uri)
            text = "".join(getattr(c, "text", "") or "" for c in contents)
            assert "<!DOCTYPE html>" in text
            assert "ui/initialize" in text


async def test_asset_explorer_still_returns_json(mock_oe_client: AsyncMock) -> None:
    mock_oe_client.post.return_value = {
        "ok": True,
        "data": {"items": [{"objectId": 1, "objectName": "orders", "objectType": "oetable"}]},
    }
    mcp = FastMCP(name="test", version="0.0.1")
    catalog.register(mcp)
    fn = await get_tool_fn(mcp, "asset_explorer")
    result = await fn(search_terms=["orders"])
    assert result["data"]["items"][0]["objectName"] == "orders"
