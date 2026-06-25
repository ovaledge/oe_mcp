from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.constants import (
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    MCP_PATH_CREATE_DQ_RULES,
    TOOL_CREATE_DQ_RULES,
)
from server.tools import dataquality
from server.tools.dataquality.helpers import format_create_dq_rules_response
from tests.helpers import get_tool_fn


class TestCreateDqRules:
    async def test_discover_posts_payload(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        out = await fn(
            discover_cde_columns=True,
            prefer_existing_rule=False,
            skip_duplicate_function_on_object=False,
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_CREATE_DQ_RULES,
            {
                "discoverCdeColumns": True,
                "preferExistingRule": False,
                "skipDuplicateFunctionOnObject": False,
                "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
            },
        )
        assert "formattedResponse" in out

    async def test_objects_and_flags_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        out = await fn(
            objects=[{"objectId": 99, "objectType": "oetable"}],
            limit=10,
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_CREATE_DQ_RULES,
            {
                "discoverCdeColumns": False,
                "preferExistingRule": True,
                "skipDuplicateFunctionOnObject": True,
                "limit": 10,
                "objects": [{"objectId": 99, "objectType": "oetable"}],
            },
        )
        assert "formattedResponse" in out

    async def test_rejects_empty_without_discover(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        out = await fn()
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()


def test_format_create_dq_rules_created_with_object_linked():
    body = {
        "data": {
            "createdCount": 1,
            "associatedCount": 1,
            "skippedCount": 0,
            "failedCount": 0,
            "rows": [
                {
                    "objectId": 123,
                    "objectType": "oecolumn",
                    "status": "created",
                    "objectAssociated": True,
                    "dqruleId": 10303,
                    "ruleName": "char_column_tcdensitypercentage",
                }
            ],
        }
    }
    text = format_create_dq_rules_response(body)
    assert "1 created, 1 associated" in text
    assert "object linked" in text
    assert "char_column_tcdensitypercentage" in text
