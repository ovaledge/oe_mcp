"""In-process FastMCP Client exercises the MCP surface (names, args, prompts, resources)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from mcp.types import TextContent, TextResourceContents

from server.app import create_mcp
from server.constants import MCP_RESOURCE_CATALOG_TABLE
from tests.conftest import MOCK_ASSET_DETAIL, MOCK_SEARCH_RESPONSE


@pytest.fixture
def mcp_client(mock_oe_client: AsyncMock) -> FastMCP:  # noqa: ARG001 — uses OvalEdge patches
    """Full app with mocked OvalEdge HTTP for in-process FastMCP Client tests."""
    return create_mcp()


class TestMcpClientTools:
    async def test_list_tools_includes_catalog_search(self, mcp_client: FastMCP) -> None:
        async with Client(mcp_client) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
        assert "search_catalog_assets" in names
        assert "catalog_asset_details" in names
        assert "lookup_glossary_term" in names
        assert "lookup_datastory" in names
        assert "create_tag" in names

    async def test_call_tool_search_catalog_assets(
        self,
        mcp_client: FastMCP,
        mock_oe_client: AsyncMock,
    ) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        async with Client(mcp_client) as client:
            result = await client.call_tool(
                "search_catalog_assets",
                {"search_terms": ["customer"], "object_type": "oetable", "limit": 5},
            )
        assert result.is_error is False
        assert result.data == MOCK_SEARCH_RESPONSE

    async def test_call_tool_validation_error_is_structured_payload(
        self,
        mcp_client: FastMCP,
    ) -> None:
        async with Client(mcp_client) as client:
            result = await client.call_tool(
                "search_catalog_assets",
                {"search_terms": ["x"], "object_type": "TABLE"},
            )
        assert result.is_error is False
        body = result.data
        assert isinstance(body, dict)
        assert body.get("status_code") == 400


class TestMcpClientResourcesAndPrompts:
    async def test_read_catalog_table_resource(
        self,
        mcp_client: FastMCP,
        mock_oe_client: AsyncMock,
    ) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        uri = MCP_RESOURCE_CATALOG_TABLE.format(object_id="42")
        async with Client(mcp_client) as client:
            rr = await client.read_resource(uri)
        # FastMCP Client returns resource contents; this server uses text/JSON bodies.
        assert isinstance(rr, list) and rr
        first = rr[0]
        assert isinstance(first, TextResourceContents)
        text = first.text
        assert json.loads(text) == MOCK_ASSET_DETAIL

    async def test_get_data_discovery_prompt(self, mcp_client: FastMCP) -> None:
        async with Client(mcp_client) as client:
            pr = await client.get_prompt("data_discovery", {"query": "payroll tables"})
        assert pr.messages
        content = pr.messages[0].content
        assert isinstance(content, TextContent)
        assert "search_catalog_assets" in content.text
