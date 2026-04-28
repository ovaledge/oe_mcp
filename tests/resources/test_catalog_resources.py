import json

from fastmcp import FastMCP

from server.constants import MCP_PATH_OBJECT_DETAILS, MCP_RESOURCE_CATALOG_TABLE
from server.resources import catalog as catalog_res
from tests.conftest import MOCK_ASSET_DETAIL


class TestCatalogResources:
    async def test_table_resource_json(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog_res.register(mcp)
        tmpl = await mcp.get_resource_template(MCP_RESOURCE_CATALOG_TABLE)
        assert tmpl is not None
        text = await tmpl.fn("42")
        assert json.loads(text) == MOCK_ASSET_DETAIL
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_OBJECT_DETAILS,
            params={"objectId": 42, "objectType": "oetable"},
        )
