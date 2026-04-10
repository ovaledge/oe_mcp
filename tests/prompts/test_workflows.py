from fastmcp import FastMCP

from server.constants import TOOL_SEARCH_CATALOG
from server.prompts import workflows


class TestWorkflowPrompts:
    async def test_data_discovery_references_tool_constant(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        workflows.register(mcp)
        prompt = await mcp.get_prompt("data_discovery")
        assert prompt is not None
        messages = prompt.fn("customer data")
        assert len(messages) == 1
        content = messages[0].content
        assert hasattr(content, "text")
        assert TOOL_SEARCH_CATALOG in content.text
