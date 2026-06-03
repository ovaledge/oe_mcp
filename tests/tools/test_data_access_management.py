from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import MCP_OBJECT_PATH_FORMATS_DOC, MCP_PATH_SOURCE_SYSTEM_ACCESS
from server.tools import rdam
from server.tools.rdam.helpers import _DESC_GET_SOURCE_SYSTEM_ACCESS
from tests.helpers import get_tool_fn


class TestGetSourceSystemAccess:
    def test_tool_description_documents_daa_scope(self) -> None:
        assert "Instance Data Access Admin" in _DESC_GET_SOURCE_SYSTEM_ACCESS
        assert "Connector Data Access Admin" in _DESC_GET_SOURCE_SYSTEM_ACCESS

    def test_tool_description_documents_object_path_patterns(self) -> None:
        assert "connectionName.dbName" in MCP_OBJECT_PATH_FORMATS_DOC
        assert "dbName" in MCP_OBJECT_PATH_FORMATS_DOC
        assert "connectionName.dbName" in _DESC_GET_SOURCE_SYSTEM_ACCESS
        assert "snowflake.BUSINESS" in MCP_OBJECT_PATH_FORMATS_DOC

    async def test_user_to_objects_forwards_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="user_to_objects",
            username="svc_analytics",
        )
        assert out == {"ok": True, "data": {"grants": []}}
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": "svc_analytics",
            },
        )

    async def test_object_to_users_forwards_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="prod_db.public.orders",
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "objectPath": "prod_db.public.orders",
            },
        )

    async def test_rejects_invalid_source_system(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="postgres",
            query_direction="user_to_objects",
            username="u",
        )
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_missing_username(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(source_system="snowflake", query_direction="user_to_objects")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_missing_object_path(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(source_system="tableau", query_direction="object_to_users")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(
            404,
            "username not found in harvested metadata",
        )
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="snowflake",
            query_direction="user_to_objects",
            username="missing.user",
        )
        assert out["status_code"] == 404

    async def test_rejects_invalid_query_direction(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="objects_to_user",
            username="svc_analytics",
        )
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_username_on_object_to_users(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="prod_db.public.orders",
            username="svc_analytics",
        )
        assert out["status_code"] == 400
        assert "username" in out["error"].lower()
        mock_oe_client.get.assert_not_called()

    async def test_forwards_optional_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="ovaledgedb.ovaledge.customer_vw",
            include_columns=True,
            connection_id=42,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "objectPath": "ovaledgedb.ovaledge.customer_vw",
                "includeColumns": True,
                "connectionId": 42,
            },
        )

    async def test_object_path_not_found_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(
            400,
            "object_path not found in harvested metadata: ovaledgedb.ovaledge.customer_vw",
        )
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="ovaledgedb.ovaledge.customer_vw",
        )
        assert out["status_code"] == 400
        assert "object_path" in out["error"]

    async def test_role_without_members_includes_principal_note(
        self, mock_oe_client: AsyncMock
    ) -> None:
        note = (
            "No users are assigned to this role in harvested RDAM metadata; "
            "the role is shown as principal."
        )
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {
                        "objectPath": "ovaledgedb.automation.customers",
                        "objectLevel": "table",
                        "privileges": ["INSERT"],
                        "grantMechanism": "role",
                        "principalType": "role",
                        "principalName": "oe_mrdw",
                        "contributingRole": "oe_mrdw",
                        "principalNote": note,
                    },
                    {
                        "objectPath": "ovaledgedb.automation.customers",
                        "objectLevel": "table",
                        "privileges": ["INSERT", "SELECT"],
                        "grantMechanism": "role",
                        "principalType": "user",
                        "principalName": "kabilan",
                        "contributingRole": "twitchdemo",
                    },
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="ovaledgedb.automation.customers",
        )
        role_grant = out["data"]["grants"][0]
        user_grant = out["data"]["grants"][1]
        assert role_grant["principalNote"] == note
        assert user_grant.get("principalNote") is None
        assert user_grant["contributingRole"] == "twitchdemo"

    async def test_tableau_object_to_users(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {
                        "objectPath": "Executive/Revenue Dashboard",
                        "objectLevel": "report",
                        "grantMechanism": "direct",
                        "principalType": "user",
                        "principalName": "svc_bi",
                        "privileges": ["READ"],
                    }
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="tableau",
            query_direction="object_to_users",
            object_path="Executive/Revenue Dashboard",
        )
        assert out["ok"] is True
        grant = out["data"]["grants"][0]
        assert grant["grantMechanism"] == "direct"
        assert grant["principalType"] == "user"
        assert grant["objectLevel"] == "report"

    async def test_forwards_connection_prefixed_object_path(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            object_path="snowflake.BUSINESS",
            connection_id=1002,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "snowflake",
                "queryDirection": "object_to_users",
                "objectPath": "snowflake.BUSINESS",
                "connectionId": 1002,
            },
        )

    async def test_forwards_database_only_object_path(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            object_path="BUSINESS",
            connection_id=1002,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "snowflake",
                "queryDirection": "object_to_users",
                "objectPath": "BUSINESS",
                "connectionId": 1002,
            },
        )

    async def test_forwards_resolve_all_matches(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [],
                "ambiguousMatch": True,
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="accountbalance",
            resolve_all_matches=True,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "objectPath": "accountbalance",
                "resolveAllMatches": True,
            },
        )

    async def test_passes_through_summary_from_api(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [],
                "summary": {
                    "totalGrants": 16,
                    "byObjectLevel": {
                        "database": 0,
                        "schema": 2,
                        "table": 14,
                        "column": 0,
                    },
                    "byGrantMechanism": {
                        "direct": 15,
                        "group": 1,
                        "role": 0,
                    },
                },
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="user_to_objects",
            username="sithik",
        )
        assert out["data"]["summary"]["totalGrants"] == 16
        assert out["data"]["summary"]["byObjectLevel"]["table"] == 14

    async def test_snowflake_user_to_objects(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {
                        "objectPath": "BUSINESS",
                        "objectLevel": "database",
                        "grantMechanism": "role",
                        "principalName": "john.doe",
                        "contributingRole": "ROLE_BANK_ACCOUNTS",
                        "privileges": ["USAGE"],
                    },
                    {
                        "objectPath": "WH.FINANCE.ORDERS",
                        "grantMechanism": "role",
                        "principalName": "john.doe",
                        "contributingRole": "data_analyst",
                        "privileges": ["SELECT"],
                    }
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="snowflake",
            query_direction="user_to_objects",
            username="john.doe",
        )
        assert out["data"]["grants"][0]["objectLevel"] == "database"
        assert out["data"]["grants"][0]["privileges"] == ["USAGE"]
        assert out["data"]["grants"][1]["grantMechanism"] == "role"
        assert out["data"]["grants"][1]["contributingRole"] == "data_analyst"
