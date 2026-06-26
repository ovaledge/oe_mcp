from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS, TOOL_ASSOCIATE_DQ_RULE_OBJECTS
from server.tools import dataquality
from server.tools.dataquality.helpers import format_associate_dq_rule_objects_response
from tests.helpers import get_tool_fn
from tests.tools.confirm_test_helpers import invoke_write_confirmed


class TestAssociateDqRuleObjects:
    async def test_preview_before_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        preview = await fn(
            dqrule_id=42,
            objects=[{"object_id": 10, "object_type": "column"}],
            skip_already_associated=False,
        )
        assert preview["workflowPhase"] == "confirm_update"
        assert preview["doNotUpdate"] is True
        assert preview.get("confirmationToken")
        mock_oe_client.post.assert_not_called()

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
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        out = await invoke_write_confirmed(
            fn,
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

    def test_format_associate_response_includes_outcome_summary(self) -> None:
        formatted = format_associate_dq_rule_objects_response(
            {
                "data": {
                    "dqruleId": 10163,
                    "associatedCount": 2,
                    "skippedCount": 1,
                    "failedCount": 0,
                    "statusMessage": (
                        "2 associated, 1 skipped, 0 failed out of 3 object(s)."
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
        assert "Outcome:" in formatted
        assert "2 associated, 1 skipped" in formatted

    def test_format_associate_response_already_linked_idempotent(self) -> None:
        formatted = format_associate_dq_rule_objects_response(
            {
                "data": {
                    "dqruleId": 10264,
                    "associatedCount": 1,
                    "skippedCount": 0,
                    "failedCount": 0,
                    "statusMessage": (
                        "All 1 of 1 object(s) are already associated with the DQ rule."
                    ),
                    "rows": [
                        {
                            "objectId": 10006,
                            "objectType": "oetable",
                            "status": "associated",
                            "message": "Object is already associated to this DQ rule.",
                        }
                    ],
                }
            }
        )
        assert "1 associated, 0 skipped" in formatted
        assert "already associated" in formatted

    async def test_rejects_invalid_dqrule_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        out = await fn(dqrule_id=0, objects=[{"objectId": 1, "objectType": "oecolumn"}])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_empty_objects(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        out = await fn(dqrule_id=5, objects=[])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(409, "Conflict")
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSOCIATE_DQ_RULE_OBJECTS)
        out = await invoke_write_confirmed(
            fn,
            dqrule_id=42,
            objects=[{"object_id": 10, "object_type": "column"}],
        )
        assert out["status_code"] == 409
