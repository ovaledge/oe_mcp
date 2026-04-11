from fastmcp import FastMCP

from server.constants import MCP_PATH_SEARCH_PLATFORM_DOCS
from server.tools import docs as docs_tools
from tests.conftest import MOCK_DOCS_SEARCH
from tests.helpers import get_tool_fn


class TestSearchPlatformDocs:
    async def test_limit_cap(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "search_platform_docs")
        await fn("how to", limit=100)
        assert mock_oe_client.get.call_args[0][0] == MCP_PATH_SEARCH_PLATFORM_DOCS
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["query"] == "how to"
        assert params["limit"] == 50

    async def test_num_candidates_query_param(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "search_platform_docs")
        await fn("x", limit=5, num_candidates=200)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 5
        assert params["numCandidates"] == 200
