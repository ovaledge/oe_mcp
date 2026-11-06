import json
from unittest.mock import AsyncMock

from fastmcp import FastMCP
from fastmcp.resources.template import FunctionResourceTemplate

from server.constants import (
    MCP_PATH_ASSET_DETAILS,
    MCP_RESOURCE_CATALOG_FILE,
    MCP_RESOURCE_CATALOG_TABLE,
)
from server.resources import catalog as catalog_res
from tests.conftest import MOCK_ASSET_DETAIL


class TestCatalogResources:
    async def test_table_resource_json(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog_res.register(mcp)
        tmpl = await mcp.get_resource_template(MCP_RESOURCE_CATALOG_TABLE)
        assert tmpl is not None
        assert isinstance(tmpl, FunctionResourceTemplate)
        text = await tmpl.fn("42")
        assert json.loads(text) == MOCK_ASSET_DETAIL
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_ASSET_DETAILS,
            params={"objectId": 42, "objectType": "oetable"},
        )

    async def test_file_resource_json(self, mock_oe_client: AsyncMock) -> None:
        file_detail = {**MOCK_ASSET_DETAIL, "objectType": "oefile", "name": "exports.csv"}
        mock_oe_client.get.return_value = file_detail
        mcp = FastMCP(name="test", version="0.0.1")
        catalog_res.register(mcp)
        tmpl = await mcp.get_resource_template(MCP_RESOURCE_CATALOG_FILE)
        assert tmpl is not None
        text = await tmpl.fn("55")
        assert json.loads(text) == file_detail
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_ASSET_DETAILS,
            params={"objectId": 55, "objectType": "oefile"},
        )
