from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.constants import (
    MCP_PATH_CREATE_SQL_DQ_RULE,
    MCP_PATH_GENERATE_DQ_QUERIES,
    MCP_PATH_VALIDATE_DQ_QUERIES,
    TOOL_DQ_RULE_ADVISOR,
    TOOL_DQ_RULE_MANAGER,
)
from server.tools import dataquality
from tests.helpers import get_tool_fn
from tests.tools.confirm_test_helpers import invoke_write_confirmed


class TestGenerateDqQueries:
    async def test_generate_queries_posts(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "status": "generated",
                "ruleQuery": "SELECT 1",
                "context": {"connectionId": 1, "schemaId": 2},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert out["workflowPhase"] == "generate_queries"
        assert out["connectionId"] == 1
        assert out["schemaId"] == 2
        assert "**connection_id:** 1" in out["formattedResponse"]
        assert "validate_query" in out["agentInstruction"]
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_GENERATE_DQ_QUERIES,
            {
                "objectId": 101,
                "objectType": "oecolumn",
            },
        )

    async def test_generate_queries_function_based_routes_to_create_rules(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "status": "function_based",
                "recommendedFunction": "Non-Null Validation",
                "recommendedWorkflow": "function_based",
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert out["workflowPhase"] == "generate_queries"
        assert "create_standard" in out.get("agentInstruction", "")

    async def test_generate_queries_code_found_routes_to_associate(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "status": "code_found",
                "recommendedCodeObjectId": 555,
                "recommendedReuseAction": "associate_existing_dqr",
                "context": {"connectionId": 3, "schemaId": 4},
                "matchingCodeObjects": [{"codeObjectId": 555, "dqruleId": 77}],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert TOOL_DQ_RULE_MANAGER in out["agentInstruction"]
        assert "dqrule_id=77" in out["agentInstruction"]
        assert "Do not call" in out["agentInstruction"]

    async def test_generate_queries_code_found_routes_to_create_from_code(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "status": "code_found",
                "recommendedCodeObjectId": 555,
                "recommendedReuseAction": "create_from_code",
                "context": {"connectionId": 3, "schemaId": 4},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert "create_custom_sql" in out["agentInstruction"]
        assert "code_object_id=555" in out["agentInstruction"]
        assert "connection_id=3" in out["agentInstruction"]

    async def test_generate_queries_code_found_already_associated(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "status": "code_found",
                "recommendedReuseAction": "already_associated",
                "recommendedCodeObjectId": 555,
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert "already associated" in out["agentInstruction"].lower()
        assert "validate_query" in out["agentInstruction"]

    async def test_generate_queries_requires_objects(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_generate_rejects_invalid_object_type(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 1, "objectType": "dqrule"}])
        assert out["status_code"] == 400
        assert "objectType" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_generate_rejects_missing_object_id(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectType": "oecolumn"}])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_generate_forwards_business_rule_and_description(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"status": "generated", "ruleQuery": "SELECT 1"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        await fn(step="generate_query", 
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            business_rule="  values must be non-null  ",
            business_description="  email column  ",
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_GENERATE_DQ_QUERIES,
            {
                "objectId": 101,
                "objectType": "oecolumn",
                "businessRule": "values must be non-null",
                "businessDescription": "email column",
            },
        )

    async def test_generate_cross_schema_blocked_instruction(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "status": "cross_schema_blocked",
                "message": "Cross-schema dependent rules cannot be created.",
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert "Do not call" in out["agentInstruction"]
        assert "validate_query" in out["agentInstruction"]
        assert "create_custom_sql" in out["agentInstruction"]

    async def test_generate_function_not_identified_instruction(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"status": "function_not_identified"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert "generate_query" in out["agentInstruction"]
        assert "invent" in out["agentInstruction"].lower()

    async def test_generate_oval_edge_error_returns_structured_dict(
        self, mock_oe_client: AsyncMock
    ) -> None:
        from server.client import OvalEdgeError

        mock_oe_client.post.side_effect = OvalEdgeError(500, "Internal error")
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="generate_query", objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert out["status_code"] == 500
        assert "500" in out["error"]


class TestValidateDqQueries:
    async def test_validate_preview_before_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        preview = await fn(step="validate_query", 
            connection_id=1,
            schema_id=2,
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        assert preview["workflowPhase"] == "confirm_create"
        assert preview.get("confirmationToken")
        mock_oe_client.post.assert_not_called()

    async def test_validate_posts_when_confirmed(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"canCreateRule": True, "ruleQueryValid": True, "results": []},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await invoke_write_confirmed(
            fn,
            step="validate_query",
            connection_id=1,
            schema_id=2,
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        assert out["workflowPhase"] == "validate_queries"
        assert out["canCreateRule"] is True
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_VALIDATE_DQ_QUERIES,
            {
                "connectionId": 1,
                "schemaId": 2,
                "ruleQuery": "SELECT 1",
                "statsQuery": "SELECT 2",
                "failedValuesQuery": "SELECT 3",
            },
        )

    async def test_validate_rejects_tampered_token(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        preview = await fn(step="validate_query", 
            connection_id=1,
            schema_id=2,
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        out = await fn(step="validate_query", 
            connection_id=1,
            schema_id=2,
            rule_query="SELECT 9",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            write_confirmed_by_user=True,
            confirmation_token=preview["confirmationToken"],
        )
        assert out["status_code"] == 400
        assert out.get("error_code") == "confirmation_token_mismatch"
        mock_oe_client.post.assert_not_called()

    async def test_validate_rejects_missing_connection_or_schema(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="validate_query", 
            connection_id=0,
            schema_id=2,
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        assert out["status_code"] == 400
        assert "connection_id" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_validate_rejects_blank_queries(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="validate_query", 
            connection_id=1,
            schema_id=2,
            rule_query="   ",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        assert out["status_code"] == 400
        assert "rule_query" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_validate_rejects_missing_stats_query(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await fn(step="validate_query", 
            connection_id=1,
            schema_id=2,
            rule_query="SELECT 1",
            stats_query=None,
            failed_values_query="SELECT 3",
        )
        assert out["status_code"] == 400
        assert "stats_query" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_validate_oval_edge_error_returns_structured_dict(
        self, mock_oe_client: AsyncMock
    ) -> None:
        from server.client import OvalEdgeError

        mock_oe_client.post.side_effect = OvalEdgeError(502, "Bad gateway")
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_ADVISOR)
        out = await invoke_write_confirmed(
            fn,
            step="validate_query",
            connection_id=1,
            schema_id=2,
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        assert out["status_code"] == 502
        assert "502" in out["error"]


class TestCreateSqlDqRule:
    async def test_create_sql_rule_confirm_preview(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(step="create_custom_sql", 
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            recommended_function="SQL Exact Value",
        )
        assert out["workflowPhase"] == "confirm_create"
        assert out.get("confirmationToken")
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_rule_posts_when_confirmed(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"status": "created", "dqruleId": 88, "ruleName": "mcp_rule"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_custom_sql",
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            connection_id=5,
            schema_id=6,
            recommended_function="SQL Exact Value",
        )
        assert out["workflowPhase"] == "create_sql_rule"
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_CREATE_SQL_DQ_RULE,
            {
                "objectId": 101,
                "objectType": "oecolumn",
                "ruleName": "mcp_rule",
                "ruleQuery": "SELECT 1",
                "statsQuery": "SELECT 2",
                "failedValuesQuery": "SELECT 3",
                "connectionId": 5,
                "schemaId": 6,
                "recommendedFunction": "SQL Exact Value",
            },
        )

    async def test_create_sql_rule_from_code_object_id(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"status": "created", "dqruleId": 90, "ruleName": "mcp_reuse"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_custom_sql",
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_reuse",
            code_object_id=555,
            connection_id=5,
            schema_id=6,
            recommended_function="SQL Exact Value",
        )
        assert out["workflowPhase"] == "create_sql_rule"
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_CREATE_SQL_DQ_RULE,
            {
                "objectId": 101,
                "objectType": "oecolumn",
                "ruleName": "mcp_reuse",
                "connectionId": 5,
                "schemaId": 6,
                "codeObjectId": 555,
                "recommendedFunction": "SQL Exact Value",
            },
        )

    async def test_create_sql_rule_rejects_tampered_token(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        preview = await fn(step="create_custom_sql", 
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            recommended_function="SQL Exact Value",
        )
        out = await fn(step="create_custom_sql", 
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="tampered_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            write_confirmed_by_user=True,
            confirmation_token=preview["confirmationToken"],
            recommended_function="SQL Exact Value",
        )
        assert out["status_code"] == 400
        assert out.get("error_code") == "confirmation_token_mismatch"
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_rejects_empty_objects(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(step="create_custom_sql", 
            objects=[],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            recommended_function="SQL Exact Value",
        )
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_rejects_blank_rule_name(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(step="create_custom_sql", 
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="  ",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            recommended_function="SQL Exact Value",
        )
        assert out["status_code"] == 400
        assert "rule_name" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_rejects_neither_query_nor_code(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(step="create_custom_sql", 
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            recommended_function="SQL Exact Value",
        )
        assert out["status_code"] == 400
        assert "rule_query or code_object_id" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_rejects_rule_query_without_stats(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(step="create_custom_sql", 
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            failed_values_query="SELECT 3",
            recommended_function="SQL Exact Value",
        )
        assert out["status_code"] == 400
        assert "stats_query" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_rejects_invalid_object_type(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(step="create_custom_sql", 
            objects=[{"objectId": 101, "objectType": "glossary"}],
            rule_name="mcp_rule",
            code_object_id=555,
            recommended_function="SQL Exact Value",
        )
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_additional_objects_and_purpose_forwarded(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"status": "created", "dqruleId": 91, "ruleName": "mcp_multi"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_custom_sql",
            objects=[
                {"objectId": 101, "objectType": "oecolumn"},
                {"objectId": 202, "objectType": "oecolumn"},
            ],
            rule_name="mcp_multi",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            purpose="  detect nulls  ",
            recommended_function=" Non-Null Validation ",
            connection_id=5,
            schema_id=6,
        )
        assert out["workflowPhase"] == "create_sql_rule"
        body = mock_oe_client.post.call_args[0][1]
        assert body["additionalObjects"] == [
            {"objectId": 202, "objectType": "oecolumn"}
        ]
        assert body["purpose"] == "detect nulls"
        assert body["recommendedFunction"] == "Non-Null Validation"

    async def test_create_sql_rejects_missing_recommended_function(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(
            step="create_custom_sql",
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        assert out["status_code"] == 400
        assert "recommended_function" in out["error"]
        assert "generate_query" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_rejects_placeholder_recommended_function(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await fn(
            step="create_custom_sql",
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            recommended_function="CUSTOM_SQL",
        )
        assert out["status_code"] == 400
        assert out.get("error_code") == "validation_invalid"
        mock_oe_client.post.assert_not_called()

    async def test_create_sql_oval_edge_error_returns_structured_dict(
        self, mock_oe_client: AsyncMock
    ) -> None:
        from server.client import OvalEdgeError

        mock_oe_client.post.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_DQ_RULE_MANAGER)
        out = await invoke_write_confirmed(
            fn,
            step="create_custom_sql",
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            code_object_id=555,
            connection_id=5,
            schema_id=6,
            recommended_function="SQL Exact Value",
        )
        assert out["status_code"] == 403
        assert "403" in out["error"]
