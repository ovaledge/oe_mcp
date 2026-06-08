from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.constants import MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS, TOOL_ASSOCIATE_DQ_RULE_OBJECTS
from server.tools import governance
from server.tools.governance.helpers import format_associate_dq_rule_objects_response
from tests.helpers import get_tool_fn


class TestAssociateDqRuleObjects:
    async def test_posts_normalized_payload(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "data": {
                "dqruleId": 42,
                "associatedCount": 1,
                "skippedCount": 0,
                "failedCount": 0,
                "statusMessage": "Added 1 out of 1 object(s) added to the DQ rule.",
                "rows": [
                    {
                        "objectId": 10,
                        "objectType": "oecolumn",
                        "status": "associated",
                    }
                ],
            }
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        out = await fn(
            dqrule_id=42,
            objects=[{"object_id": 10, "object_type": "column"}],
            skip_already_associated=False,
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS,
            {
                "dqruleId": 42,
                "skipAlreadyAssociated": False,
                "objects": [{"objectId": 10, "objectType": "oecolumn"}],
            },
        )
        assert "formattedResponse" in out
        assert "associated" in out["formattedResponse"]

    def test_format_associate_response_includes_function_support_summary(self) -> None:
        formatted = format_associate_dq_rule_objects_response(
            {
                "data": {
                    "dqruleId": 10163,
                    "associatedCount": 2,
                    "skippedCount": 1,
                    "failedCount": 0,
                    "statusMessage": (
                        "Added 2 out of 3 object(s) added to the DQ rule. "
                        "Skipped 1 object(s) due to unsupported column data type."
                    ),
                    "rows": [
                        {
                            "objectId": 1,
                            "objectType": "oecolumn",
                            "status": "associated",
                        },
                        {
                            "objectId": 2,
                            "objectType": "oecolumn",
                            "status": "skipped",
                            "message": "Object data type or connector is not supported.",
                        },
                    ],
                }
            }
        )
        assert "Function support:" in formatted
        assert "2 associated, 1 skipped" in formatted

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
