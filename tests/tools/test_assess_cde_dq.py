from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import MCP_DQ_ASSESS_LIMIT_DEFAULT, MCP_PATH_ASSESS_CDE_DQ, TOOL_ASSESS_CDE_DQ
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

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(500, "Internal error")
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        out = await fn(discover_cde_columns=True)
        assert out["status_code"] == 500

    def test_description_routing_phrases(self) -> None:
        desc = dataquality_helpers._DESC_ASSESS_CDE_DQ
        assert "lookup_dq_rule" in desc
        assert "search_catalog_assets" in desc
        assert "associate_dq_rule_objects" in desc
        assert "description_custom_field_name" in desc
        assert "description_term_name" in desc
        assert "descriptionSource" in desc
        assert "never used as automatic fallbacks" in desc or "no automatic glossary" in desc
        assert "Read-only" in desc
        assert MCP_PATH_ASSESS_CDE_DQ in desc
        assert "pass only the assets in scope" in desc

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
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        await fn(discover_cde_columns=True, description_term_name=" Net Revenue ")
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
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        await fn(discover_cde_columns=True, limit=999)
        body = mock_oe_client.post.call_args[0][1]
        assert body["limit"] == MCP_DQ_ASSESS_LIMIT_MAX

    async def test_rejects_missing_object_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        out = await fn(objects=[{"objectType": "oecolumn"}])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_non_positive_object_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        out = await fn(objects=[{"objectId": 0, "objectType": "oecolumn"}])
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
        fn = await get_tool_fn(mcp, TOOL_ASSESS_CDE_DQ)
        out = await fn(objects=[{"objectId": 11, "objectType": "oecolumn"}])
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
        assert "Function candidates" in text
        assert "Non-Empty and Non-Null Validation" in text
        assert "excluded_function_names" in text
        assert "Existing rules using this function" in text
        assert "DESCRIPTION_datalengthrange" in text
        assert "ID 1618" in text

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

        assert "Custom SQL path" in text
        assert "Do not call create_dq_rules for an OEQUERY SQL function" in text
        assert "IN/NOT IN or allowed-value sets use SQL Values Contains" in text
        assert "Use create_dq_rules with preferred_function_name" not in text
