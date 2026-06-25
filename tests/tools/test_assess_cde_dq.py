from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.constants import (
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    MCP_PATH_ASSESS_CDE_DQ,
    TOOL_ASSESS_CDE_DQ,
)
from server.tools import dataquality
from server.tools.dataquality import helpers as dataquality_helpers
from tests.helpers import get_tool_fn


class TestAssessCdeDq:
    async def test_discover_cde_columns_posts_payload(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": [], "assessedCount": 0}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        out = await fn(discover_cde_columns=True)
        assert out["assessedCount"] == 0
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_ASSESS_CDE_DQ,
            {
                "discoverCdeColumns": True,
                "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
            },
        )

    async def test_objects_normalized_to_camel_case(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": [{"objectId": 10}], "assessedCount": 1}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        await fn(
            objects=[{"object_id": 10, "object_type": "column"}],
            limit=25,
            description_custom_field_name=" Business Definition ",
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_ASSESS_CDE_DQ,
            {
                "discoverCdeColumns": False,
                "limit": 25,
                "descriptionCustomFieldName": "Business Definition",
                "objects": [{"objectId": 10, "objectType": "oecolumn"}],
            },
        )

    async def test_rejects_empty_without_discover(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        out = await fn()
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_invalid_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        out = await fn(objects=[{"objectId": 1, "objectType": "dqrule"}])
        assert out["status_code"] == 400
        assert "objectType" in out["error"]
        mock_oe_client.post.assert_not_called()

    def test_description_routing_phrases(self) -> None:
        desc = dataquality_helpers._DESC_ASSESS_CDE_DQ
        assert "lookup_dq_rule" in desc
        assert "search_catalog_assets" in desc
        assert "associate_dq_rule_objects" in desc
        assert "description_custom_field_name" in desc
        assert "descriptionSource" in desc
        assert "Read-only" in desc
        assert MCP_PATH_ASSESS_CDE_DQ in desc
