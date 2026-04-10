import json

from fastmcp import FastMCP

from server.resources import catalog as catalog_res
from tests.conftest import MOCK_ASSET_DETAIL


class TestCatalogResources:
    async def test_table_resource_json(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog_res.register(mcp)
        tmpl = await mcp.get_resource_template("ovaledge://catalog/table/{object_id}")
        assert tmpl is not None
        text = await tmpl.fn("obj-1")
        assert json.loads(text) == MOCK_ASSET_DETAIL
        mock_oe_client.get.assert_called_once()
