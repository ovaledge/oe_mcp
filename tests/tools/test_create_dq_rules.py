from unittest.mock import AsyncMock, call

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    MCP_PATH_ASSESS_CDE_DQ,
    MCP_PATH_CREATE_DQ_RULES,
    TOOL_DQ_RULE_MANAGER,
)
from server.tools import dataquality
from server.tools.dataquality import helpers as dataquality_helpers
from server.tools.dataquality.helpers import format_create_dq_rules_response
from tests.helpers import get_tool_fn
from tests.tools.confirm_test_helpers import invoke_write_confirmed


class TestCreateDqRules:
    def test_description_scoped_objects_guidance(self) -> None:
        desc = dataquality_helpers._DESC_DQ_RULE_MANAGER
        assert "create_standard" in desc
        assert "dq_rule_advisor" in desc
        assert MCP_PATH_CREATE_DQ_RULES in desc

    async def test_stringified_objects_json_accepted(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_standard",
            objects='[{"objectId": 42, "objectType": "oecolumn"}]',
        )
        assess_payload = {
            "discoverCdeColumns": False,
            "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
            "objects": [{"objectId": 42, "objectType": "oecolumn"}],
        }
        create_payload = {
            **assess_payload,
            "preferExistingRule": True,
            "skipDuplicateFunctionOnObject": True,
        }
        mock_oe_client.post.assert_has_awaits(
            [
                call(MCP_PATH_ASSESS_CDE_DQ, assess_payload),
                call(MCP_PATH_CREATE_DQ_RULES, create_payload),
            ]
        )
        assert "formattedResponse" in out

    async def test_single_object_dict_accepted(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_standard",
            objects={"objectId": 42, "objectType": "column"},
        )
        assess_payload = {
            "discoverCdeColumns": False,
            "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
            "objects": [{"objectId": 42, "objectType": "oecolumn"}],
        }
        create_payload = {
            **assess_payload,
            "preferExistingRule": True,
            "skipDuplicateFunctionOnObject": True,
        }
        mock_oe_client.post.assert_has_awaits(
            [
                call(MCP_PATH_ASSESS_CDE_DQ, assess_payload),
                call(MCP_PATH_CREATE_DQ_RULES, create_payload),
            ]
        )
        assert "formattedResponse" in out

    async def test_preview_before_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        preview = await fn(step="create_standard", discover_cde_columns=True)
        assert preview["workflowPhase"] == "confirm_create"
        assert preview["doNotCreate"] is True
        assert preview.get("confirmationToken")
        mock_oe_client.post.assert_awaited_once_with(
            MCP_PATH_ASSESS_CDE_DQ,
            {
                "discoverCdeColumns": True,
                "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
            },
        )

    async def test_preview_identifies_existing_rule_association(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "data": {
                "rows": [
                    {
                        "objectId": 42,
                        "objectType": "oecolumn",
                        "existingRulesForFunction": [
                            {
                                "dqruleId": 101,
                                "name": "Inventory Quantity Required",
                                "purpose": "Quantity must be populated",
                                "successOperator": "Greater Than",
                                "successValue1": "0",
                                "purposeSimilarity": 0.2,
                            },
                            {
                                "dqruleId": 1618,
                                "name": "DESCRIPTION_datalengthrange",
                                "purpose": "Description should be more than 50 characters",
                                "purposeSimilarity": 0.0,
                            },
                        ],
                    }
                ]
            }
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)

        preview = await fn(
            step="create_standard",
            objects={"objectId": 42, "objectType": "oecolumn"},
        )

        assert preview["workflowPhase"] == "select_existing_rule"
        assert preview["requiresRuleSelection"] is True
        assert preview.get("confirmationToken") is None
        assert "Inventory Quantity Required" in preview["formattedResponse"]
        assert "ID 101" in preview["formattedResponse"]
        assert "DESCRIPTION_datalengthrange" in preview["formattedResponse"]
        assert "ID 1618" in preview["formattedResponse"]
        assert "prefer_existing_rule=false" in preview["formattedResponse"]
        assert preview["existingRuleChoices"][0]["rules"][1]["dqruleId"] == 1618

    async def test_discover_posts_payload(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_standard",
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
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_standard",
            objects=[{"objectId": 99, "objectType": "oetable"}],
            limit=10,
        )
        assess_payload = {
            "discoverCdeColumns": False,
            "limit": 10,
            "objects": [{"objectId": 99, "objectType": "oetable"}],
        }
        create_payload = {
            **assess_payload,
            "preferExistingRule": True,
            "skipDuplicateFunctionOnObject": True,
        }
        mock_oe_client.post.assert_has_awaits(
            [
                call(MCP_PATH_ASSESS_CDE_DQ, assess_payload),
                call(MCP_PATH_CREATE_DQ_RULES, create_payload),
            ]
        )
        assert "formattedResponse" in out

    async def test_supplemental_criteria_text_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        await invoke_write_confirmed(
            fn,
            step="create_standard",
            objects=[{"objectId": 42, "objectType": "oecolumn"}],
            supplemental_criteria_text="Success criteria: equal to 300",
        )
        assess_payload = {
            "discoverCdeColumns": False,
            "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
            "objects": [{"objectId": 42, "objectType": "oecolumn"}],
            "supplementalCriteriaText": "Success criteria: equal to 300",
        }
        create_payload = {
            **assess_payload,
            "preferExistingRule": True,
            "skipDuplicateFunctionOnObject": True,
        }
        mock_oe_client.post.assert_has_awaits(
            [
                call(MCP_PATH_ASSESS_CDE_DQ, assess_payload),
                call(MCP_PATH_CREATE_DQ_RULES, create_payload),
            ]
        )

    async def test_description_term_name_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        await invoke_write_confirmed(
            fn,
            step="create_standard",
            discover_cde_columns=True,
            description_term_name=" Net Revenue ",
        )
        assess_payload = {
            "discoverCdeColumns": True,
            "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
            "descriptionTermName": "Net Revenue",
        }
        create_payload = {
            **assess_payload,
            "preferExistingRule": True,
            "skipDuplicateFunctionOnObject": True,
        }
        mock_oe_client.post.assert_has_awaits(
            [
                call(MCP_PATH_ASSESS_CDE_DQ, assess_payload),
                call(MCP_PATH_CREATE_DQ_RULES, create_payload),
            ]
        )

    async def test_rejects_empty_without_discover(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(step="create_standard")
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = [
            {"rows": []},
            OvalEdgeError(502, "Bad gateway"),
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_standard", discover_cde_columns=True)
        assert out["status_code"] == 502

    async def test_rejects_invalid_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(step="create_standard", objects=[{"objectId": 1, "objectType": "dqrule"}])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_description_custom_field_name_forwarded(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {"rows": []}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        await invoke_write_confirmed(
            fn,
            step="create_standard",
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
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        await invoke_write_confirmed(
            fn,
            step="create_standard", discover_cde_columns=True, limit=999)
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


def test_format_create_dq_rules_surfaces_default_criteria_warning():
    body = {
        "data": {
            "createdCount": 1,
            "associatedCount": 1,
            "rows": [
                {
                    "objectId": 123,
                    "objectType": "oecolumn",
                    "status": "created",
                    "criteriaSource": "function_default",
                    "criteriaMessage": (
                        "Business metadata criteria could not be parsed. "
                        "Default criteria were applied."
                    ),
                }
            ],
        }
    }

    text = format_create_dq_rules_response(body)

    assert "criteriaSource=function_default" in text
    assert "Warning: Business metadata criteria could not be parsed" in text
