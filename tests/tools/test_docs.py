from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import MCP_PATH_SEARCH_PLATFORM_DOCS
from server.tools import docs as docs_tools
from tests.conftest import MOCK_DOCS_SEARCH
from tests.helpers import get_tool_fn


class TestSearchPlatformDocs:
    async def test_limit_cap(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "search_platform_docs")
        await fn("how to", limit=100)
        assert mock_oe_client.get.call_args[0][0] == MCP_PATH_SEARCH_PLATFORM_DOCS
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["query"] == "how to"
        assert params["limit"] == 50
        assert params["numCandidates"] == 128

    async def test_limit_only_sets_num_candidates(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "search_platform_docs")
        await fn("dq rules", limit=15)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 15
        assert params["numCandidates"] == 128

    async def test_num_candidates_query_param(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "search_platform_docs")
        await fn("x", limit=5, num_candidates=200)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 5
        assert params["numCandidates"] == 200

    async def test_num_candidates_clamped_below_limit(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "search_platform_docs")
        await fn("x", limit=20, num_candidates=5)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 20
        assert params["numCandidates"] == 20

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(500, "Internal error")
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "search_platform_docs")
        out = await fn("failure query")
        assert out["status_code"] == 500
        assert "500" in out["error"]
