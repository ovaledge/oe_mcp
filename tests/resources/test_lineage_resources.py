import json

from fastmcp import FastMCP

from server.resources import lineage as lineage_res
from tests.conftest import MOCK_LINEAGE_RESPONSE


class TestLineageResource:
    async def test_default_depth_direction(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_LINEAGE_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        lineage_res.register(mcp)
        tmpl = await mcp.get_resource_template("ovaledge://lineage/{object_id}")
        assert tmpl is not None
        text = await tmpl.fn("obj-1")
        assert json.loads(text) == MOCK_LINEAGE_RESPONSE
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["direction"] == "BOTH"
        assert params["depth"] == 2
