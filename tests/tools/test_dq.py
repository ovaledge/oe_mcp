from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.constants import (
    MCP_PATH_CREATE_SQL_DQ_RULE,
    MCP_PATH_GENERATE_DQ_QUERIES,
    MCP_PATH_VALIDATE_DQ_QUERIES,
    TOOL_ASSOCIATE_DQ_RULE_OBJECTS,
    TOOL_CREATE_SQL_DQ_RULE,
    TOOL_GENERATE_DQ_QUERIES,
    TOOL_VALIDATE_DQ_QUERIES,
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
        fn = await get_tool_fn(mcp, TOOL_GENERATE_DQ_QUERIES)
        out = await fn(objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert out["workflowPhase"] == "generate_queries"
        assert out["connectionId"] == 1
        assert out["schemaId"] == 2
        assert "**connection_id:** 1" in out["formattedResponse"]
        assert "validate_dq_queries" in out["agentInstruction"]
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
        fn = await get_tool_fn(mcp, TOOL_GENERATE_DQ_QUERIES)
        out = await fn(objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert out["workflowPhase"] == "generate_queries"
        assert "create_dq_rules" in out.get("agentInstruction", "")

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
        fn = await get_tool_fn(mcp, TOOL_GENERATE_DQ_QUERIES)
        out = await fn(objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert TOOL_ASSOCIATE_DQ_RULE_OBJECTS in out["agentInstruction"]
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
        fn = await get_tool_fn(mcp, TOOL_GENERATE_DQ_QUERIES)
        out = await fn(objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert TOOL_CREATE_SQL_DQ_RULE in out["agentInstruction"]
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
        fn = await get_tool_fn(mcp, TOOL_GENERATE_DQ_QUERIES)
        out = await fn(objects=[{"objectId": 101, "objectType": "oecolumn"}])
        assert "already associated" in out["agentInstruction"].lower()
        assert f"Do not call {TOOL_VALIDATE_DQ_QUERIES}" in out["agentInstruction"]

    async def test_generate_queries_requires_objects(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_GENERATE_DQ_QUERIES)
        out = await fn(objects=[])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()


class TestValidateDqQueries:
    async def test_validate_preview_before_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_VALIDATE_DQ_QUERIES)
        preview = await fn(
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
        fn = await get_tool_fn(mcp, TOOL_VALIDATE_DQ_QUERIES)
        out = await invoke_write_confirmed(
            fn,
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
        fn = await get_tool_fn(mcp, TOOL_VALIDATE_DQ_QUERIES)
        preview = await fn(
            connection_id=1,
            schema_id=2,
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        out = await fn(
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


class TestCreateSqlDqRule:
    async def test_create_sql_rule_confirm_preview(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SQL_DQ_RULE)
        out = await fn(
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
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
        fn = await get_tool_fn(mcp, TOOL_CREATE_SQL_DQ_RULE)
        out = await invoke_write_confirmed(
            fn,
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            connection_id=5,
            schema_id=6,
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
            },
        )

    async def test_create_sql_rule_from_code_object_id(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"status": "created", "dqruleId": 90, "ruleName": "mcp_reuse"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SQL_DQ_RULE)
        out = await invoke_write_confirmed(
            fn,
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_reuse",
            code_object_id=555,
            connection_id=5,
            schema_id=6,
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
            },
        )

    async def test_create_sql_rule_rejects_tampered_token(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SQL_DQ_RULE)
        preview = await fn(
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="mcp_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
        )
        out = await fn(
            objects=[{"objectId": 101, "objectType": "oecolumn"}],
            rule_name="tampered_rule",
            rule_query="SELECT 1",
            stats_query="SELECT 2",
            failed_values_query="SELECT 3",
            write_confirmed_by_user=True,
            confirmation_token=preview["confirmationToken"],
        )
        assert out["status_code"] == 400
        assert out.get("error_code") == "confirmation_token_mismatch"
        mock_oe_client.post.assert_not_called()
