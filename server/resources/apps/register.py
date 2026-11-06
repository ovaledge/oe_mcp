"""MCP Apps HTML resources for catalog read tools."""

from __future__ import annotations

from fastmcp import FastMCP

from server.constants import (
    MCP_UI_ASSET_DETAILS,
    MCP_UI_ASSET_EXPLORER,
    MCP_UI_ASSET_LINEAGE,
    MCP_UI_METADATA_CHANGES,
)
from server.resources.apps.html import catalog_app_html


def register(mcp: FastMCP) -> None:
    @mcp.resource(
        MCP_UI_ASSET_EXPLORER,
        mime_type="text/html;profile=mcp-app",
        title="OvalEdge catalog search view",
        description="Table of asset_explorer hits for MCP Apps hosts.",
    )
    def asset_explorer_view() -> str:
        return catalog_app_html("explorer")

    @mcp.resource(
        MCP_UI_ASSET_DETAILS,
        mime_type="text/html;profile=mcp-app",
        title="OvalEdge asset details view",
        description="Property card for asset_details on MCP Apps hosts.",
    )
    def asset_details_view() -> str:
        return catalog_app_html("details")

    @mcp.resource(
        MCP_UI_ASSET_LINEAGE,
        mime_type="text/html;profile=mcp-app",
        title="OvalEdge lineage graph view",
        description="SVG lineage graph for asset_lineage on MCP Apps hosts.",
    )
    def asset_lineage_view() -> str:
        return catalog_app_html("lineage")

    @mcp.resource(
        MCP_UI_METADATA_CHANGES,
        mime_type="text/html;profile=mcp-app",
        title="OvalEdge metadata-drift view",
        description="Tables for metadata_changes_between_crawls on MCP Apps hosts.",
    )
    def metadata_changes_view() -> str:
        return catalog_app_html("drift")
