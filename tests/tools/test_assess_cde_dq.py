from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    MCP_PATH_ASSESS_CDE_DQ,
    TOOL_DQ_RULE_ADVISOR,
)
from server.tools import dataquality
from server.tools.dataquality import helpers as dataquality_helpers
from tests.helpers import get_tool_fn


class TestAssessCdeDq:
    async def test_discover_cde_columns_posts_payload(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"rows": [], "assessedCount": 0}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="assess", discover_cde_columns=True)
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
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        await fn(
            step="assess",
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
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="assess")
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_invalid_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="assess", objects=[{"objectId": 1, "objectType": "dqrule"}])
        assert out["status_code"] == 400
        assert "objectType" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(500, "Internal error")
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="assess", discover_cde_columns=True)
        assert out["status_code"] == 500

    def test_description_routing_phrases(self) -> None:
        desc = dataquality_helpers._DESC_DQ_RULE_ADVISOR
        assert "lookup" in desc
        assert "dq_rule_manager" in desc
        assert "assess" in desc
        assert MCP_PATH_ASSESS_CDE_DQ in desc
        assert "Read/recommend" in desc or "no rule create" in desc
        assert "docs://ovaledge/mcp_workflows" in desc
        assert "Ladder (do not skip)" not in desc

    def test_build_payload_includes_description_term_name(self) -> None:
        payload = dataquality_helpers.build_assess_cde_dq_payload(
            False,
            [{"objectId": 1, "objectType": "oecolumn"}],
            10,
            description_term_name=" Net Revenue ",
        )
        assert payload["descriptionTermName"] == "Net Revenue"
        assert "descriptionCustomFieldName" not in payload

    async def test_description_term_name_forwarded_on_invoke(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {"rows": [], "assessedCount": 0}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        await fn(step="assess", discover_cde_columns=True, description_term_name=" Net Revenue ")
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_ASSESS_CDE_DQ,
            {
                "discoverCdeColumns": True,
                "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
                "descriptionTermName": "Net Revenue",
            },
        )

    async def test_limit_capped_at_max(self, mock_oe_client: AsyncMock) -> None:
        from server.constants import MCP_DQ_ASSESS_LIMIT_MAX

        mock_oe_client.post.return_value = {"rows": [], "assessedCount": 0}
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        await fn(step="assess", discover_cde_columns=True, limit=999)
        body = mock_oe_client.post.call_args[0][1]
        assert body["limit"] == MCP_DQ_ASSESS_LIMIT_MAX

    async def test_rejects_missing_object_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="assess", objects=[{"objectType": "oecolumn"}])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_non_positive_object_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="assess", objects=[{"objectId": 0, "objectType": "oecolumn"}])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_happy_path_sets_formatted_response(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "assessedCount": 1,
            "rows": [
                {
                    "tableColumnName": "film.rating",
                    "objectId": 11,
                    "objectType": "oecolumn",
                    "descriptionSource": "none",
                    "descriptionMessage": "No description found",
                }
            ],
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="assess", objects=[{"objectId": 11, "objectType": "oecolumn"}])
        assert "formattedResponse" in out
        assert "film.rating" in out["formattedResponse"]
        assert "descriptionSource=none" in out["formattedResponse"]

    def test_build_payload_includes_preferred_and_excluded_functions(self) -> None:
        payload = dataquality_helpers.build_assess_cde_dq_payload(
            False,
            [{"objectId": 1, "objectType": "oecolumn"}],
            10,
            preferred_function_name=" Non-Null Validation ",
            excluded_function_names=["Average", " Average ", ""],
        )
        assert payload["preferredFunctionName"] == "Non-Null Validation"
        assert payload["excludedFunctionNames"] == ["Average"]

    def test_format_assess_includes_function_candidates(self) -> None:
        text = dataquality_helpers.format_assess_cde_dq_response(
            {
                "assessedCount": 1,
                "rows": [
                    {
                        "tableColumnName": "stockquantity",
                        "objectId": 1,
                        "objectType": "oecolumn",
                        "descriptionSource": "object_description",
                        "recommendedFunction": "Non-Empty and Non-Null Validation",
                        "recommendedWorkflow": "function_based",
                        "recommendedFunctionCandidates": [
                            {
                                "functionName": "Non-Empty and Non-Null Validation",
                                "score": 0.72,
                                "matchReason": "keyword_match",
                            },
                            {
                                "functionName": "Non-Null Validation",
                                "score": 0.41,
                                "matchReason": "keyword_match",
                            },
                        ],
                        "existingRulesForFunction": [
                            {
                                "dqruleId": 1618,
                                "name": "DESCRIPTION_datalengthrange",
                                "purpose": "Description must be more than 50 characters",
                                "purposeSimilarity": 0.0,
                            }
                        ],
                    }
                ],
            }
        )
        assert "recommendedFunctionCandidates" in text
        assert "Non-Empty and Non-Null Validation" in text
        assert "excluded_function_names" in text
        assert "Existing rules using this function" in text or "existingRulesForFunction" in text
        assert "DESCRIPTION_datalengthrange" in text
        assert "ID 1618" in text

    def test_format_assess_hides_dbt_function_candidates(self) -> None:
        text = dataquality_helpers.format_assess_cde_dq_response(
            {
                "assessedCount": 1,
                "rows": [
                    {
                        "tableColumnName": "CHARTTYPE",
                        "objectId": 37883,
                        "objectType": "oecolumn",
                        "recommendedFunction": "DBT_NOT_NULL",
                        "recommendedFunctionCandidates": [
                            {
                                "functionName": "DBT_NOT_NULL",
                                "score": 0.9,
                            },
                            {
                                "functionName": "Non-Null Validation",
                                "score": 0.72,
                            },
                        ],
                    }
                ],
            }
        )
        assert "DBT_NOT_NULL" not in text
        assert "Non-Null Validation" in text

    def test_format_assess_hides_dbt_function_in_custom_sql_next_step(self) -> None:
        text = dataquality_helpers.format_assess_cde_dq_response(
            {
                "assessedCount": 1,
                "rows": [
                    {
                        "tableColumnName": "CHARTTYPE",
                        "objectId": 37883,
                        "objectType": "oecolumn",
                        "recommendedFunction": "DBT_NOT_NULL",
                        "recommendedWorkflow": "custom_sql",
                        "recommendedFunctionCandidates": [
                            {
                                "functionName": "DBT_NOT_NULL",
                                "score": 0.9,
                            },
                            {
                                "functionName": "dbt_unique",
                                "score": 0.8,
                            },
                        ],
                    }
                ],
            }
        )
        assert "DBT_NOT_NULL" not in text
        assert "dbt_unique" not in text
        assert "use recommendedFunction" not in text
        assert "generate_query" in text

    def test_format_assess_routes_sql_candidates_only_to_custom_sql_workflow(self) -> None:
        text = dataquality_helpers.format_assess_cde_dq_response(
            {
                "assessedCount": 1,
                "rows": [
                    {
                        "tableColumnName": "version",
                        "objectId": 1,
                        "objectType": "oecolumn",
                        "recommendedFunction": "SQL Values Contains",
                        "recommendedWorkflow": "custom_sql",
                        "recommendedFunctionCandidates": [
                            {
                                "functionName": "SQL Values Contains",
                                "score": 0.85,
                                "matchReason": "structured_sql_intent",
                            }
                        ],
                    }
                ],
            }
        )

        assert "Custom SQL" in text or "generate_query" in text
        assert "Do not use create_standard for an OEQUERY SQL function" in text
        assert "IN/NOT IN or allowed-value sets use SQL Values Contains" in text
        assert "Use dq_rule_manager step=create_standard with preferred_function_name" not in text
        assert "recommendedFunction" in text
