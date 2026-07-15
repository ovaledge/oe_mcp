from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    MCP_PATH_CREATE_DQ_RULES,
    TOOL_CREATE_DQ_RULES,
)
from server.tools import dataquality
from server.tools.dataquality.helpers import format_create_dq_rules_response
from tests.helpers import get_tool_fn
from tests.tools.confirm_test_helpers import invoke_write_confirmed


class TestCreateDqRules:
    async def test_preview_before_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        preview = await fn(discover_cde_columns=True)
        assert preview["workflowPhase"] == "confirm_create"
        assert preview["doNotCreate"] is True
        assert preview.get("confirmationToken")
        mock_oe_client.post.assert_not_called()

    async def test_discover_posts_payload(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        out = await invoke_write_confirmed(
            fn,
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
        out = await invoke_write_confirmed(
            fn,
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

    async def test_supplemental_criteria_text_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        await invoke_write_confirmed(
            fn,
            objects=[{"objectId": 42, "objectType": "oecolumn"}],
            supplemental_criteria_text="Success criteria: equal to 300",
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_CREATE_DQ_RULES,
            {
                "discoverCdeColumns": False,
                "preferExistingRule": True,
                "skipDuplicateFunctionOnObject": True,
                "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
                "objects": [{"objectId": 42, "objectType": "oecolumn"}],
                "supplementalCriteriaText": "Success criteria: equal to 300",
            },
        )

    async def test_description_term_name_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        await invoke_write_confirmed(
            fn,
            discover_cde_columns=True,
            description_term_name=" Net Revenue ",
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_CREATE_DQ_RULES,
            {
                "discoverCdeColumns": True,
                "preferExistingRule": True,
                "skipDuplicateFunctionOnObject": True,
                "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
                "descriptionTermName": "Net Revenue",
            },
        )

    async def test_rejects_empty_without_discover(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        out = await fn()
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(502, "Bad gateway")
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        out = await invoke_write_confirmed(fn, discover_cde_columns=True)
        assert out["status_code"] == 502

    async def test_rejects_invalid_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        out = await fn(objects=[{"objectId": 1, "objectType": "dqrule"}])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_description_custom_field_name_forwarded(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        await invoke_write_confirmed(
            fn,
            discover_cde_columns=True,
            description_custom_field_name=" Business Definition ",
        )
        body = mock_oe_client.post.call_args[0][1]
        assert body["descriptionCustomFieldName"] == "Business Definition"

    async def test_limit_capped_at_max(self, mock_oe_client: AsyncMock) -> None:
        from server.constants import MCP_DQ_ASSESS_LIMIT_MAX

        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_DQ_RULES)
        await invoke_write_confirmed(fn, discover_cde_columns=True, limit=999)
        body = mock_oe_client.post.call_args[0][1]
        assert body["limit"] == MCP_DQ_ASSESS_LIMIT_MAX


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
