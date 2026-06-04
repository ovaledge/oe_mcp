from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.constants import MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS, TOOL_ASSOCIATE_DQ_RULE_OBJECTS
from server.tools import governance
from tests.helpers import get_tool_fn


class TestAssociateDqRuleObjects:
    async def test_posts_normalized_payload(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"results": []}
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        await fn(
            dqrule_id=42,
            objects=[{"object_id": 10, "object_type": "column"}],
            skip_already_associated=False,
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS,
            json={
                "dqruleId": 42,
                "skipAlreadyAssociated": False,
                "objects": [{"objectId": 10, "objectType": "oecolumn"}],
            },
        )

    async def test_rejects_invalid_dqrule_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        out = await fn(dqrule_id=0, objects=[{"objectId": 1, "objectType": "oecolumn"}])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_empty_objects(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        out = await fn(dqrule_id=5, objects=[])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()
