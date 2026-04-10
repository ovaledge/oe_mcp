from fastmcp import FastMCP

from server.tools import lineage
from tests.conftest import MOCK_LINEAGE_RESPONSE
from tests.helpers import get_tool_fn


class TestGetAssetLineage:
    async def test_depth_capped(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_LINEAGE_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        lineage.register(mcp)
        fn = await get_tool_fn(mcp, "get_asset_lineage")
        await fn("obj-1", depth=99)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["depth"] == 5
