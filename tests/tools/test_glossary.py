from fastmcp import FastMCP

from server.tools import glossary
from tests.conftest import MOCK_GLOSSARY_RESULT
from tests.helpers import get_tool_fn


class TestLookupBusinessTerm:
    async def test_lookup_params(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_GLOSSARY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        glossary.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_business_term")
        out = await fn("churn", domain="Marketing")
        assert out == MOCK_GLOSSARY_RESULT
        mock_oe_client.get.assert_called_once()
        (_path,) = mock_oe_client.get.call_args[0]
        assert _path == "/api/mcp/glossary/search"
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["q"] == "churn"
        assert params["domain"] == "Marketing"
