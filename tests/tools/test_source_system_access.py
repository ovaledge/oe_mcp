from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_OBJECT_PATH_FORMATS_DOC,
    MCP_PATH_SOURCE_SYSTEM_ACCESS,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_OBJECT_TYPE_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_SOURCE_ERROR,
)
from server.tools import rdam
from server.tools.rdam.helpers import (
    _DESC_SOURCE_SYSTEM_ACCESS,
    normalize_string_list,
    reject_multiple_connection_id,
    reject_multiple_object_type,
    reject_multiple_source_system,
    validate_and_normalize_object_type,
    validate_source_system_access_args,
)
from tests.helpers import get_tool_fn

# Required on every source_system_access call (matches tool schema).
_REQ = {
    "username": "svc_analytics",
    "object_path": "prod_db.public.orders",
    "object_type": "table",
    "connection_id": 1000,
}


class TestGetSourceSystemAccess:
    def test_tool_description_documents_daa_scope(self) -> None:
        assert "Instance Data Access Admin" in _DESC_SOURCE_SYSTEM_ACCESS
        assert "Connector Data Access Admin" in _DESC_SOURCE_SYSTEM_ACCESS

    def test_tool_description_documents_object_path_patterns(self) -> None:
        assert "connectionName.dbName" in MCP_OBJECT_PATH_FORMATS_DOC
        assert "dbName" in MCP_OBJECT_PATH_FORMATS_DOC
        assert "connectionName.dbName" in _DESC_SOURCE_SYSTEM_ACCESS
        assert "snowflake.BUSINESS" in MCP_OBJECT_PATH_FORMATS_DOC
        assert "SNOWFLAKE.ALERT" in _DESC_SOURCE_SYSTEM_ACCESS
        assert "object_type=schema" in _DESC_SOURCE_SYSTEM_ACCESS
        assert "rdam_tableprivilege" in _DESC_SOURCE_SYSTEM_ACCESS
        assert "never call `search_catalog_assets`" in _DESC_SOURCE_SYSTEM_ACCESS.lower()
        assert "Mandatory by direction" in _DESC_SOURCE_SYSTEM_ACCESS
        assert "connection_id" in _DESC_SOURCE_SYSTEM_ACCESS
        assert "filteredToObjectLevel" not in _DESC_SOURCE_SYSTEM_ACCESS

    def test_validate_rejects_missing_required_fields(self) -> None:
        err = validate_source_system_access_args(
            "redshift", "user_to_objects", "", "prod_db.t", "table", 1000
        )
        assert err is not None
        assert "mandatory" in err["error"]
        assert "username" in err["error"]

        err = validate_source_system_access_args(
            "redshift", "user_to_objects", "u", "", "table", 1000
        )
        assert err is not None
        assert "mandatory" in err["error"]
        assert "object_path" in err["error"]

        err = validate_source_system_access_args(
            "redshift", "user_to_objects", "u", "prod_db.t", None, None
        )
        assert err is not None
        assert "mandatory" in err["error"]
        assert "object_type" in err["error"]
        assert "connection_id" in err["error"]

    def test_validate_lists_all_missing_mandatory_fields(self) -> None:
        err = validate_source_system_access_args(
            "redshift", "user_to_objects", None, "", "", None
        )
        assert err is not None
        assert err["error"].startswith("The following parameters are mandatory:")
        for field in ("username", "object_path", "object_type", "connection_id"):
            assert field in err["error"]

    def test_validate_username_not_required_for_object_to_users(self) -> None:
        err = validate_source_system_access_args(
            "snowflake", "object_to_users", None, "BUSINESS.BANKING", "schema", 1360
        )
        assert err is None

    def test_reject_multiple_source_system_values(self) -> None:
        err = reject_multiple_source_system("redshift,snowflake")
        assert err is not None
        assert err["error"] == MCP_SOURCE_SYSTEM_ACCESS_MULTI_SOURCE_ERROR

        err = validate_source_system_access_args(
            "redshift,snowflake",
            "user_to_objects",
            "john_analyst",
            "ovaledgedb",
            "database",
            1000,
        )
        assert err is not None
        assert "source_system" in err["error"]
        assert "not supported" in err["error"]

    def test_object_to_users_mandatory_fields_redshift(self) -> None:
        err = validate_source_system_access_args(
            "redshift", "object_to_users", None, "ovaledgedb.automation.customers", "table", 1000
        )
        assert err is None

        err = validate_source_system_access_args(
            "redshift", "object_to_users", None, "", "table", 1000
        )
        assert err is not None
        assert "object_path" in err["error"]

    def test_reject_multiple_connection_id_values(self) -> None:
        err = reject_multiple_connection_id([1000, 1002])
        assert err is not None
        assert err["error"] == MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_ERROR

        err = validate_source_system_access_args(
            "redshift",
            "user_to_objects",
            "john_analyst",
            "ovaledgedb",
            "database",
            [1000, 1002],
        )
        assert err is not None
        assert "connection_id" in err["error"]
        assert "not supported" in err["error"]

    async def test_user_to_objects_forwards_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="user_to_objects",
            **_REQ,
        )
        assert out["ok"] is True
        assert out["data"]["grants"] == []
        assert out["data"]["filteredToObjectLevel"] == "table"
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": _REQ["username"],
                "objectPath": _REQ["object_path"],
                "objectType": _REQ["object_type"],
                "connectionId": _REQ["connection_id"],
            },
        )

    async def test_object_to_users_forwards_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path=_REQ["object_path"],
            object_type=_REQ["object_type"],
            connection_id=_REQ["connection_id"],
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "objectPath": _REQ["object_path"],
                "objectType": _REQ["object_type"],
                "connectionId": _REQ["connection_id"],
            },
        )

    async def test_user_to_objects_rejects_missing_username(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="user_to_objects",
            username=None,
            object_path=_REQ["object_path"],
            object_type=_REQ["object_type"],
            connection_id=_REQ["connection_id"],
        )
        assert out["status_code"] == 400
        assert "mandatory" in out["error"]
        assert "username" in out["error"]
        mock_oe_client.get.assert_not_called()

    async def test_rejects_invalid_source_system(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="postgres",
            query_direction="user_to_objects",
            **_REQ,
        )
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_missing_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            username=_REQ["username"],
            object_path="SNOWFLAKE.ALERT",
            object_type="",
            connection_id=_REQ["connection_id"],
        )
        assert out["status_code"] == 400
        assert "mandatory" in out["error"]
        assert "object_type" in out["error"]
        mock_oe_client.get.assert_not_called()

    async def test_rejects_column_object_type_for_snowflake(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            username=_REQ["username"],
            object_path="BUSINESS.BANKING.ACCOUNTSCHEDULE",
            object_type="column",
            connection_id=_REQ["connection_id"],
        )
        assert out["status_code"] == 400
        assert "redshift" in out["error"].lower()
        mock_oe_client.get.assert_not_called()

    async def test_normalizes_oeschema_alias(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            username=_REQ["username"],
            object_path="SNOWFLAKE.ALERT",
            object_type="oeschema",
            connection_id=1002,
            resolve_all_matches=True,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "snowflake",
                "queryDirection": "object_to_users",
                "username": _REQ["username"],
                "objectPath": "SNOWFLAKE.ALERT",
                "objectType": "schema",
                "connectionId": 1002,
                "resolveAllMatches": True,
            },
        )

    async def test_oval_edge_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(
            404,
            "username not found in harvested metadata",
        )
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="snowflake",
            query_direction="user_to_objects",
            username="missing.user",
            object_path="BUSINESS",
            object_type="database",
            connection_id=1002,
        )
        assert out["status_code"] == 404

    async def test_rejects_invalid_query_direction(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="objects_to_user",
            **_REQ,
        )
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_forwards_include_columns(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="ovaledgedb.ovaledge.customer_vw",
            object_type="table",
            username=_REQ["username"],
            connection_id=42,
            include_columns=True,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "username": _REQ["username"],
                "objectPath": "ovaledgedb.ovaledge.customer_vw",
                "objectType": "table",
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
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="ovaledgedb.ovaledge.customer_vw",
            object_type="table",
            username=_REQ["username"],
            connection_id=_REQ["connection_id"],
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
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="ovaledgedb.automation.customers",
            object_type="table",
            username=_REQ["username"],
            connection_id=_REQ["connection_id"],
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
                    },
                    {
                        "objectPath": "Executive/Revenue Dashboard",
                        "objectLevel": "report",
                        "grantMechanism": "group",
                        "principalType": "user",
                        "principalName": "jane.doe",
                        "contributingGroup": "Analysts",
                        "privileges": ["READ"],
                    },
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="tableau",
            query_direction="object_to_users",
            object_path="Executive/Revenue Dashboard",
            object_type="report",
            username="svc_bi",
            connection_id=2000,
        )
        assert out["ok"] is True
        direct = out["data"]["grants"][0]
        group = out["data"]["grants"][1]
        assert direct["grantMechanism"] == "direct"
        assert group["grantMechanism"] == "group"

    async def test_tableau_user_to_objects_group_expansion(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {
                        "objectPath": "Finance",
                        "objectLevel": "project",
                        "grantMechanism": "direct",
                        "principalType": "user",
                        "principalName": "jane.doe",
                        "privileges": ["READ"],
                    },
                    {
                        "objectPath": "Finance/Headcount",
                        "objectLevel": "report",
                        "grantMechanism": "group",
                        "principalType": "user",
                        "principalName": "jane.doe",
                        "contributingGroup": "Analysts",
                        "privileges": ["READ"],
                    },
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="tableau",
            query_direction="user_to_objects",
            username="jane.doe",
            object_path="Finance/Headcount",
            object_type="report",
            connection_id=2000,
        )
        assert out["ok"] is True
        group_grant = out["data"]["grants"][0]
        assert group_grant["grantMechanism"] == "group"
        assert group_grant["contributingGroup"] == "Analysts"

    async def test_forwards_connection_prefixed_object_path(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            object_path="snowflake.BUSINESS",
            object_type="database",
            username=_REQ["username"],
            connection_id=1002,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "snowflake",
                "queryDirection": "object_to_users",
                "username": _REQ["username"],
                "objectPath": "snowflake.BUSINESS",
                "objectType": "database",
                "connectionId": 1002,
            },
        )

    async def test_forwards_resolve_all_matches(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"grants": [], "ambiguousMatch": True},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path="accountbalance",
            object_type="table",
            username=_REQ["username"],
            connection_id=_REQ["connection_id"],
            resolve_all_matches=True,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "username": _REQ["username"],
                "objectPath": "accountbalance",
                "objectType": "table",
                "connectionId": _REQ["connection_id"],
                "resolveAllMatches": True,
            },
        )

    async def test_user_to_objects_filters_by_object_type_level(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {
                        "objectPath": "ovaledgedb",
                        "objectLevel": "database",
                        "privileges": ["CREATE"],
                        "grantMechanism": "direct",
                    },
                    {
                        "objectPath": "ovaledgedb.automation",
                        "objectLevel": "schema",
                        "privileges": ["USAGE"],
                        "grantMechanism": "direct",
                    },
                    {
                        "objectPath": "ovaledgedb.automation.customers",
                        "objectLevel": "table",
                        "privileges": ["SELECT"],
                        "grantMechanism": "direct",
                    },
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        out = await fn(
            source_system="redshift",
            query_direction="user_to_objects",
            username="john_analyst",
            object_path="ovaledgedb",
            object_type="database",
            connection_id=1000,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": "john_analyst",
                "objectPath": "ovaledgedb",
                "objectType": "database",
                "connectionId": 1000,
            },
        )
        assert len(out["data"]["grants"]) == 1
        assert out["data"]["grants"][0]["objectLevel"] == "database"
        assert out["data"]["filteredToObjectLevel"] == "database"

    async def test_redshift_multiple_usernames_forwards_params(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        await fn(
            source_system="redshift",
            query_direction="user_to_objects",
            username=["john_analyst", "svc_analytics"],
            object_path="ovaledgedb",
            object_type="database",
            connection_id=1000,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": ["john_analyst", "svc_analytics"],
                "objectPath": "ovaledgedb",
                "objectType": "database",
                "connectionId": 1000,
            },
        )

    def test_reject_multiple_object_type_values(self) -> None:
        err = reject_multiple_object_type(["database", "schema"])
        assert err is not None
        assert err["error"] == MCP_SOURCE_SYSTEM_ACCESS_MULTI_OBJECT_TYPE_ERROR

        err = validate_source_system_access_args(
            "redshift",
            "user_to_objects",
            "john_analyst",
            "ovaledgedb",
            "database,schema",
            1000,
        )
        assert err is not None
        assert "object_type" in err["error"]
        assert "not supported" in err["error"]

    async def test_redshift_multiple_object_paths_forwards_params(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, "source_system_access")
        await fn(
            source_system="redshift",
            query_direction="object_to_users",
            object_path=[
                "ovaledgedb.automation.customers",
                "ovaledgedb.automation.orders",
            ],
            object_type="table",
            connection_id=1000,
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SOURCE_SYSTEM_ACCESS,
            params={
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "objectPath": [
                    "ovaledgedb.automation.customers",
                    "ovaledgedb.automation.orders",
                ],
                "objectType": "table",
                "connectionId": 1000,
            },
        )

    def test_normalize_string_list_splits_commas(self) -> None:
        assert normalize_string_list("john_analyst, svc_analytics") == [
            "john_analyst",
            "svc_analytics",
        ]

    def test_validate_and_normalize_object_type(self) -> None:
        normalized, err = validate_and_normalize_object_type("snowflake", "oeschema")
        assert err is None
        assert normalized == "schema"

        _, err = validate_and_normalize_object_type("snowflake", "column")
        assert err is not None
        assert err["status_code"] == 400

        normalized, err = validate_and_normalize_object_type("redshift", "database")
        assert err is None
        assert normalized == "database"
