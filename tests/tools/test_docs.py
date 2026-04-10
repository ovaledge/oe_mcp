from fastmcp import FastMCP

from server.tools import docs as docs_tools
from tests.conftest import MOCK_DOCS_SEARCH
from tests.helpers import get_tool_fn


class TestSearchPlatformDocs:
    async def test_top_k_cap(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "search_platform_docs")
        await fn("how to", top_k=100)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["topK"] == 10
