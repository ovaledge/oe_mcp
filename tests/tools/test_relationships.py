from fastmcp import FastMCP

from server.tools import relationships
from tests.conftest import MOCK_RELATIONSHIPS
from tests.helpers import get_tool_fn


class TestGetEntityRelationships:
    async def test_depth_cap(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_RELATIONSHIPS
        mcp = FastMCP(name="test", version="0.0.1")
        relationships.register(mcp)
        fn = await get_tool_fn(mcp, "get_entity_relationships")
        await fn("t1", depth=10)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["depth"] == 3
