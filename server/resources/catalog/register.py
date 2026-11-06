"""MCP resources for catalog assets."""

from __future__ import annotations

from fastmcp import FastMCP

from server.constants import (
    MCP_PATH_ASSET_DETAILS,
    MCP_RESOURCE_CATALOG_FILE,
    MCP_RESOURCE_CATALOG_TABLE,
)
from server.resources.helpers import fetch_object_details_json


def register(mcp: FastMCP) -> None:

    @mcp.resource(MCP_RESOURCE_CATALOG_TABLE)
    async def table_resource(object_id: str) -> str:
        f"""
        Catalog document for a table (oetable) by internal object id.
        URI: {MCP_RESOURCE_CATALOG_TABLE}

        GET {MCP_PATH_ASSET_DETAILS}?objectId=...&objectType=oetable
        """
        return await fetch_object_details_json(object_id, "oetable")

    @mcp.resource(MCP_RESOURCE_CATALOG_FILE)
    async def file_resource(object_id: str) -> str:
        f"""
        Catalog document for a file (oefile) by internal object id.
        URI: {MCP_RESOURCE_CATALOG_FILE}

        GET {MCP_PATH_ASSET_DETAILS}?objectId=...&objectType=oefile
        """
        return await fetch_object_details_json(object_id, "oefile")
