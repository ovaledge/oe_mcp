from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_OPERATION_CATALOG_ACCESS,
    MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
    MCP_PATH_ACCESS_EXPLORER,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_OBJECT_TYPE_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_SOURCE_ERROR,
    TOOL_ACCESS_EXPLORER,
)
from server.docs.loader import read_doc_markdown
from server.tools import access
from server.tools.access.helpers import _DESC_ACCESS_EXPLORER
from server.tools.rdam.helpers import (
    _has_table_level_grants,
    _schema_names_from_schema_grants,
    is_incomplete_table_object_path,
    normalize_string_list,
    reject_multiple_connection_id,
    reject_multiple_object_type,
    reject_multiple_source_system,
    shape_object_to_users_disambiguation,
    validate_and_normalize_object_type,
    validate_source_system_access_args,
)
from tests.helpers import get_tool_fn


def assert_rdam_api_called(mock_client: AsyncMock, params: dict[str, object]) -> None:
    expected = {"operation": MCP_OPERATION_SOURCE_SYSTEM_ACCESS, **params}
    mock_client.get.assert_any_call(MCP_PATH_ACCESS_EXPLORER, params=expected)


# Required on every source_system_access call (matches tool schema).
_REQ = {
    "username": "svc_analytics",
    "object_path": "prod_db.public.orders",
    "object_type": "table",
    "connection_id": 1000,
}


class TestGetSourceSystemAccess:
    def test_tool_description_documents_daa_scope(self) -> None:
        governance_doc = read_doc_markdown("governance")
        assert "Data Access Admin" in _DESC_ACCESS_EXPLORER
        assert "Instance Data Access Admin" in governance_doc
        assert "Connector Data Access Admin" in governance_doc

    def test_tool_description_documents_routing_essentials(self) -> None:
        rdam_doc = read_doc_markdown("rdam_source_access")
        assert "connectionName.dbName" in rdam_doc
        assert "dbName" in rdam_doc
        assert "snowflake.BUSINESS" in rdam_doc
        assert "SNOWFLAKE.ALERT" in rdam_doc
        assert "object_type=schema" in rdam_doc
        assert "rdam_tableprivilege" in rdam_doc
        assert "never fall back to `asset_explorer`" in _DESC_ACCESS_EXPLORER.lower()
        assert "Mandatory API fields" in rdam_doc
        assert "object_name" in _DESC_ACCESS_EXPLORER
        assert "object_type=all" in rdam_doc
        assert "svc_analytics" in rdam_doc
        assert "access_explorer" in _DESC_ACCESS_EXPLORER or "operation" in _DESC_ACCESS_EXPLORER
        assert "catalog_access" in _DESC_ACCESS_EXPLORER
        assert "Access grant models by source system" in rdam_doc
        assert "direct" in _DESC_ACCESS_EXPLORER
        assert "contributing_role" in _DESC_ACCESS_EXPLORER
        assert "user_to_objects" in _DESC_ACCESS_EXPLORER
        assert "descendants" in _DESC_ACCESS_EXPLORER
        assert "never call `object_to_users`" in rdam_doc.lower()
        assert "do not probe" in _DESC_ACCESS_EXPLORER.lower()
        assert "do not probe" in rdam_doc.lower()
        assert "omit `object_path`" in _DESC_ACCESS_EXPLORER.lower()
        assert "all tables on that connector" in rdam_doc.lower()
        assert "ask the user which schema" in rdam_doc.lower()
        assert "requiresSchemaSelection" in _DESC_ACCESS_EXPLORER
        assert "connection_id" in _DESC_ACCESS_EXPLORER
        assert "docs://ovaledge/rdam_source_access" in _DESC_ACCESS_EXPLORER
        assert "docs://ovaledge/mcp_workflows" in _DESC_ACCESS_EXPLORER
        assert "native_source_access" in _DESC_ACCESS_EXPLORER
        assert "disabled" in rdam_doc.lower()
        assert "what tables/schemas/columns can i see/view/access" in _DESC_ACCESS_EXPLORER.lower()
        assert "named principal" in _DESC_ACCESS_EXPLORER.lower()
        assert "not `access_explorer`" in _DESC_ACCESS_EXPLORER

        assert "filteredToObjectLevel" not in _DESC_ACCESS_EXPLORER

    def test_validate_only_source_system_and_query_direction_required(self) -> None:
        assert (
            validate_source_system_access_args(
                "redshift", "user_to_objects", None, None, None, None
            )
            is not None
        )
        assert (
            validate_source_system_access_args(
                "snowflake", "object_to_users", None, None, None, None
            )
            is not None
        )
        assert (
            validate_source_system_access_args(
                "snowflake",
                "object_to_users",
                None,
                "DB.SCHEMA",
                "schema",
                None,
            )
            is None
        )

        err = validate_source_system_access_args(
            "redshift", "user_to_objects", "", "prod_db.t", "table", 1000
        )
        assert err is not None

        err = validate_source_system_access_args(
            "redshift", "user_to_objects", "u", "", "schema", 1000
        )
        assert err is None

        err = validate_source_system_access_args(
            "redshift", "user_to_objects", "u", None, "table", 1000
        )
        assert err is None

        err = validate_source_system_access_args(
            "redshift", "user_to_objects", "u", "prod_db.t", None, None
        )
        assert err is not None

    def test_validate_rejects_invalid_direction_not_unknown_source_system(self) -> None:
        err = validate_source_system_access_args(
            "postgres", "user_to_objects", "u", "prod_db.t", "table", 1000
        )
        assert err is None

        err = validate_source_system_access_args(
            "redshift", "invalid", "u", "prod_db.t", "table", 1000
        )
        assert err is not None
        assert "query_direction" in err["error"]

    def test_validate_username_not_required_for_object_to_users(self) -> None:
        err = validate_source_system_access_args(
            "snowflake", "object_to_users", None, "BUSINESS.BANKING", "schema", 1360
        )
        assert err is None

    def test_object_to_users_object_id_requires_object_type(self) -> None:
        err = validate_source_system_access_args(
            "snowflake",
            "object_to_users",
            None,
            None,
            None,
            None,
            object_id=42,
        )
        assert err is not None
        assert "objectType" in err["error"]

        err = validate_source_system_access_args(
            "snowflake",
            "object_to_users",
            None,
            None,
            "table",
            None,
            object_id=42,
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

    def test_object_to_users_optional_fields_redshift(self) -> None:
        err = validate_source_system_access_args(
            "redshift", "object_to_users", None, "ovaledgedb.automation.customers", "table", 1000
        )
        assert err is None

        err = validate_source_system_access_args(
            "redshift", "object_to_users", None, "", "table", 1000
        )
        assert err is not None

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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="user_to_objects",
            **_REQ,
        )
        assert out["ok"] is True
        assert out["data"]["grants"] == []
        assert out["data"]["filteredToObjectLevel"] == "table"
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": _REQ["username"],
                "objectPath": _REQ["object_path"],
                "objectType": _REQ["object_type"],
                "connectionId": _REQ["connection_id"],
            })

    async def test_user_to_objects_connection_wide_tables_omits_object_path(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="user_to_objects",
            username="bhanuddm",
            object_path=None,
            object_type="table",
            connection_id=1000,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": "bhanuddm",
                "objectType": "table",
                "connectionId": 1000,
            })

    async def test_object_to_users_forwards_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path=_REQ["object_path"],
            object_type=_REQ["object_type"],
            connection_id=_REQ["connection_id"],
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "objectPath": _REQ["object_path"],
                "objectType": _REQ["object_type"],
                "connectionId": _REQ["connection_id"],
            })

    async def test_object_to_users_requires_access_intent(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            object_path=_REQ["object_path"],
            object_type=_REQ["object_type"],
            connection_id=_REQ["connection_id"],
        )
        assert out.get("error_code") == "ACCESS_INTENT_REQUIRED"
        mock_oe_client.get.assert_not_called()

    async def test_object_to_users_rejects_wrong_intent_catalog_acl(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="catalog_acl",
            object_path=_REQ["object_path"],
            object_type=_REQ["object_type"],
            connection_id=_REQ["connection_id"],
        )
        assert out.get("error_code") == "ACCESS_INTENT_REQUIRED"
        mock_oe_client.get.assert_not_called()

    async def test_user_to_objects_forwards_without_username(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="user_to_objects",
            username=None,
            object_path=_REQ["object_path"],
            object_type=_REQ["object_type"],
            connection_id=_REQ["connection_id"],
        )
        assert out["status_code"] == 400

    async def test_unsupported_source_system_continues_with_catalog_access(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.side_effect = [
            OvalEdgeError(
                400,
                "Connector type postgres is not supported for native DAM access. "
                "Supported connector types: redshift, snowflake, tableau. "
                "Continue with operation=catalog_access.",
            ),
            {"ok": True, "data": {"effectiveAccess": []}},
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="postgres",
            query_direction="user_to_objects",
            **_REQ,
        )
        assert out["ok"] is True
        assert "catalog_access" in (out.get("data") or {}).get("advisoryMessage", "")
        catalog_call = mock_oe_client.get.await_args_list[-1]
        assert catalog_call.args[0] == MCP_PATH_ACCESS_EXPLORER
        assert catalog_call.kwargs["params"]["operation"] == MCP_OPERATION_CATALOG_ACCESS
        assert catalog_call.kwargs["params"]["queryDirection"] == "user_to_object"

    async def test_forwards_without_object_type(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="snowflake",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path="SNOWFLAKE.ALERT",
            object_type="schema",
            connection_id=_REQ["connection_id"],
        )
        assert out["ok"] is True
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "snowflake",
                "queryDirection": "object_to_users",
                "objectPath": "SNOWFLAKE.ALERT",
                "objectType": "schema",
                "connectionId": _REQ["connection_id"],
            })

    async def test_forwards_minimal_user_to_objects(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="snowflake",
            query_direction="user_to_objects",
            username="RACHEL",
            connection_id=1002,
        )
        assert out["ok"] is True
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "snowflake",
                "queryDirection": "user_to_objects",
                "username": "RACHEL",
                "connectionId": 1002,
            })

    async def test_rejects_column_object_type_for_snowflake(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="snowflake",
            query_direction="object_to_users",
            access_intent_confirmed="native",
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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="snowflake",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            username=_REQ["username"],
            object_path="SNOWFLAKE.ALERT",
            object_type="oeschema",
            connection_id=1002,
            resolve_all_matches=True,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "snowflake",
                "queryDirection": "object_to_users",
                "username": _REQ["username"],
                "objectPath": "SNOWFLAKE.ALERT",
                "objectType": "schema",
                "connectionId": 1002,
                "resolveAllMatches": True,
            })

    async def test_oval_edge_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(
            404,
            "username not found in harvested metadata",
        )
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="objects_to_user",
            **_REQ,
        )
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_forwards_include_columns(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path="ovaledgedb.ovaledge.customer_vw",
            object_type="table",
            username=_REQ["username"],
            connection_id=42,
            include_columns=True,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "username": _REQ["username"],
                "objectPath": "ovaledgedb.ovaledge.customer_vw",
                "objectType": "table",
                "includeColumns": True,
                "connectionId": 42,
            })

    async def test_object_path_not_found_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(
            400,
            "object_path not found in harvested metadata: ovaledgedb.ovaledge.customer_vw",
        )
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="tableau",
            query_direction="object_to_users",
            access_intent_confirmed="native",
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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
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

    async def test_tableau_user_to_objects_direct_role(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {
                        "objectPath": "Finance/Headcount",
                        "objectLevel": "report",
                        "grantMechanism": "role",
                        "principalType": "user",
                        "principalName": "jane.doe",
                        "contributingRole": "Explorer",
                        "privileges": ["READ"],
                    },
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="tableau",
            query_direction="user_to_objects",
            username="jane.doe",
            object_path="Finance/Headcount",
            object_type="report",
            connection_id=2000,
        )
        assert out["ok"] is True
        role_grant = out["data"]["grants"][0]
        assert role_grant["grantMechanism"] == "role"
        assert role_grant["contributingRole"] == "Explorer"

    async def test_forwards_connection_prefixed_object_path(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="snowflake",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path="snowflake.BUSINESS",
            object_type="database",
            username=_REQ["username"],
            connection_id=1002,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "snowflake",
                "queryDirection": "object_to_users",
                "username": _REQ["username"],
                "objectPath": "snowflake.BUSINESS",
                "objectType": "database",
                "connectionId": 1002,
            })

    async def test_forwards_resolve_all_matches(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"grants": [], "ambiguousMatch": True},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path="accountbalance",
            object_type="table",
            username=_REQ["username"],
            connection_id=_REQ["connection_id"],
            resolve_all_matches=True,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "username": _REQ["username"],
                "objectPath": "accountbalance",
                "objectType": "table",
                "connectionId": _REQ["connection_id"],
                "resolveAllMatches": True,
            })

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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="user_to_objects",
            username="john_analyst",
            object_path="ovaledgedb",
            object_type="database",
            connection_id=1000,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": "john_analyst",
                "objectPath": "ovaledgedb",
                "objectType": "database",
                "connectionId": 1000,
            })
        assert len(out["data"]["grants"]) == 1
        assert out["data"]["grants"][0]["objectLevel"] == "database"
        assert out["data"]["filteredToObjectLevel"] == "database"
        assert "includedObjectLevels" not in out["data"]

    async def test_redshift_user_to_objects_table_type_exact_level_only(
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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="user_to_objects",
            username="john_analyst",
            object_path="ovaledgedb.automation.customers",
            object_type="table",
            connection_id=1000,
        )
        levels = {grant["objectLevel"] for grant in out["data"]["grants"]}
        assert levels == {"table"}
        assert out["data"]["filteredToObjectLevel"] == "table"

    async def test_redshift_object_to_users_passes_through_api_grants(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {"objectLevel": "database", "objectPath": "ovaledgedb"},
                    {"objectLevel": "schema", "objectPath": "ovaledgedb.automation"},
                    {"objectLevel": "table", "objectPath": "ovaledgedb.automation.customers"},
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path="ovaledgedb.automation.customers",
            object_type="table",
            connection_id=1000,
        )
        levels = {grant["objectLevel"] for grant in out["data"]["grants"]}
        assert levels == {"table"}
        assert out["data"].get("filteredToObjectLevel") == "table"

    async def test_redshift_multiple_usernames_forwards_params(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="user_to_objects",
            username=["john_analyst", "svc_analytics"],
            object_path="ovaledgedb",
            object_type="database",
            connection_id=1000,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": ["john_analyst", "svc_analytics"],
                "objectPath": "ovaledgedb",
                "objectType": "database",
                "connectionId": 1000,
            })

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
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path=[
                "ovaledgedb.automation.customers",
                "ovaledgedb.automation.orders",
            ],
            object_type="table",
            connection_id=1000,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "objectPath": [
                    "ovaledgedb.automation.customers",
                    "ovaledgedb.automation.orders",
                ],
                "objectType": "table",
                "connectionId": 1000,
            })

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


class TestShapeObjectToUsersDisambiguation:
    def test_incomplete_table_path_detection(self) -> None:
        assert is_incomplete_table_object_path("actor")
        assert is_incomplete_table_object_path("ovaledgedb.actor")
        assert not is_incomplete_table_object_path("ovaledgedb.sakila.actor")

    def test_backend_ambiguous_match_requires_schema_selection(self) -> None:
        shaped = shape_object_to_users_disambiguation(
            {
                "ok": True,
                "data": {
                    "ambiguousMatch": True,
                    "matchCandidates": [
                        {
                            "objectPath": "ovaledgedb.sakila.actor",
                            "objectLevel": "table",
                            "connectionId": 1000,
                        },
                        {
                            "objectPath": "ovaledgedb.automation.actor",
                            "objectLevel": "table",
                            "connectionId": 1000,
                        },
                    ],
                    "grants": [{"objectLevel": "schema"}],
                },
            },
            "actor",
            "table",
        )
        data = shaped["data"]
        assert data["requiresSchemaSelection"] is True
        assert data["grants"] == []
        assert "sakila" in data["advisoryMessage"]
        assert "automation" in data["advisoryMessage"]

    def test_multiple_table_grants_require_schema_selection(self) -> None:
        shaped = shape_object_to_users_disambiguation(
            {
                "ok": True,
                "data": {
                    "grants": [
                        {
                            "objectPath": "ovaledgedb.sakila.actor",
                            "objectLevel": "table",
                            "connectionId": 1000,
                        },
                        {
                            "objectPath": "ovaledgedb.public.actor",
                            "objectLevel": "table",
                            "connectionId": 1000,
                        },
                    ],
                },
            },
            "actor",
            "table",
        )
        data = shaped["data"]
        assert data["ambiguousMatch"] is True
        assert data["requiresSchemaSelection"] is True
        assert data["grants"] == []
        assert len(data["matchCandidates"]) == 2

    def test_single_resolved_table_grant_is_unchanged(self) -> None:
        result = {
            "ok": True,
            "data": {
                "grants": [
                    {
                        "objectPath": "ovaledgedb.automation.customers",
                        "objectLevel": "table",
                        "connectionId": 1000,
                    },
                ],
            },
        }
        shaped = shape_object_to_users_disambiguation(result, "customers", "table")
        assert shaped == result

    def test_parent_only_grants_prompt_schema_selection(self) -> None:
        shaped = shape_object_to_users_disambiguation(
            {
                "ok": True,
                "data": {
                    "grants": [
                        {
                            "objectPath": "sakila",
                            "objectLevel": "schema",
                            "connectionId": 1000,
                        },
                        {
                            "objectPath": "customerinfo",
                            "objectLevel": "schema",
                            "connectionId": 1000,
                        },
                    ],
                },
            },
            "actor",
            "table",
        )
        data = shaped["data"]
        assert data["requiresSchemaSelection"] is True
        assert data["grants"] == []
        assert data["schemaHints"] == ["sakila", "customerinfo"]
        assert "ask the user which schema" in data["advisoryMessage"].lower()

    def test_schema_names_from_schema_grants(self) -> None:
        grants = [
            {"objectPath": "salesinfo", "objectLevel": "schema"},
            {"objectPath": "customerinfo", "objectLevel": "schema"},
            {"objectPath": "salesinfo", "objectLevel": "schema"},
        ]
        assert _schema_names_from_schema_grants(grants) == ["salesinfo", "customerinfo"]

    def test_has_table_level_grants(self) -> None:
        assert _has_table_level_grants(
            {"ok": True, "data": {"grants": [{"objectLevel": "table"}]}}
        )
        assert not _has_table_level_grants(
            {"ok": True, "data": {"grants": [{"objectLevel": "schema"}]}}
        )

    async def test_object_to_users_applies_schema_disambiguation(
        self, mock_oe_client: AsyncMock
    ) -> None:
        async def _get(path: str, params: dict[str, object]) -> dict[str, object]:
            object_path = params.get("objectPath")
            if object_path == "actor":
                return {
                    "ok": True,
                    "data": {
                        "grants": [
                            {
                                "objectPath": "sakila",
                                "objectLevel": "schema",
                                "connectionId": 1000,
                            },
                            {
                                "objectPath": "salesinfo",
                                "objectLevel": "schema",
                                "connectionId": 1000,
                            },
                        ],
                    },
                }
            if object_path in {"sakila.actor", "salesinfo.actor"}:
                return {
                    "ok": True,
                    "data": {
                        "grants": [
                            {
                                "objectPath": object_path,
                                "objectLevel": "table",
                                "connectionId": 1000,
                            },
                        ],
                    },
                }
            return {"ok": True, "data": {"grants": []}}

        mock_oe_client.get.side_effect = _get
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path="actor",
            object_type="table",
            connection_id=1000,
        )
        data = out["data"]
        assert data["requiresSchemaSelection"] is True
        assert data["grants"] == []
        assert data["discoveredSchemaCandidates"] is True
        paths = {candidate["objectPath"] for candidate in data["matchCandidates"]}
        assert paths == {"sakila.actor", "salesinfo.actor"}
        assert "salesinfo" in data["advisoryMessage"]
        assert "customerinfo" not in data["advisoryMessage"]


class TestSourceSystemAccessHelpers:
    def test_compose_object_path_variants(self) -> None:
        from server.tools.rdam.helpers import compose_object_path

        assert compose_object_path("prod_db", "orders") == "prod_db.orders"
        assert compose_object_path("prod_db.public", "orders") == "prod_db.public.orders"
        assert compose_object_path(None, "transactions") == "transactions"
        assert (
            compose_object_path("prod_db.public.orders", "new_table")
            == "prod_db.public.new_table"
        )

    def test_object_type_all_normalizes(self) -> None:
        normalized, err = validate_and_normalize_object_type("snowflake", "all")
        assert err is None
        assert normalized == "all"

    def test_filter_grants_by_privileges(self) -> None:
        from server.tools.rdam.helpers import filter_grants_by_privileges

        result = {
            "ok": True,
            "data": {
                "grants": [
                    {"privileges": ["SELECT"], "objectLevel": "table"},
                    {"privileges": ["INSERT", "UPDATE"], "objectLevel": "table"},
                ],
            },
        }
        filtered = filter_grants_by_privileges(result, ["INSERT", "UPDATE"])
        grants = filtered["data"]["grants"]
        assert len(grants) == 1
        assert "INSERT" in grants[0]["privileges"]

    async def test_object_name_forwards_composed_path(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="object_to_users",
            access_intent_confirmed="native",
            object_path="prod_db",
            object_name="orders",
            object_type="table",
            connection_id=1000,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "redshift",
                "queryDirection": "object_to_users",
                "objectPath": "prod_db.orders",
                "objectType": "table",
                "connectionId": 1000,
            })

    async def test_object_type_all_omits_wire_object_type(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {"objectLevel": "database"},
                    {"objectLevel": "table"},
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="snowflake",
            query_direction="user_to_objects",
            username="john.doe",
            object_type="all",
            connection_id=1002,
        )
        assert_rdam_api_called(mock_oe_client, {
                "sourceSystem": "snowflake",
                "queryDirection": "user_to_objects",
                "username": "john.doe",
                "connectionId": 1002,
            })
        assert len(out["data"]["grants"]) == 2

    async def test_privileges_filter_on_user_to_objects(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {
                        "objectLevel": "table",
                        "objectPath": "prod.transactions",
                        "privileges": ["SELECT"],
                    },
                    {
                        "objectLevel": "table",
                        "objectPath": "prod.transactions",
                        "privileges": ["INSERT", "UPDATE"],
                    },
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="redshift",
            query_direction="user_to_objects",
            username="svc_etl",
            object_name="transactions",
            object_type="table",
            privileges=["INSERT", "UPDATE"],
            connection_id=1000,
        )
        grants = out["data"]["grants"]
        assert len(grants) == 1
        assert "INSERT" in grants[0]["privileges"]
        assert out["data"]["filteredToPrivileges"] == ["INSERT", "UPDATE"]

    async def test_multi_connection_advisory(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "grants": [
                    {"connectionId": 1001, "objectLevel": "table"},
                    {"connectionId": 1002, "objectLevel": "table"},
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation="source_system_access",
            source_system="snowflake",
            query_direction="user_to_objects",
            username="svc_analytics",
            object_type="table",
        )
        assert out["data"]["multipleConnections"] is True
        assert out["data"]["connectionIds"] == [1001, 1002]
        assert "connection_id" in out["data"]["advisoryMessage"]
