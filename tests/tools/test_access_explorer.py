"""Unified access_explorer: catalog permissions + native RDAM via operation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastmcp import FastMCP

from server.constants import (
    MCP_OPERATION_CATALOG_ACCESS,
    MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
    MCP_PATH_ACCESS_EXPLORER,
    TOOL_ACCESS_EXPLORER,
)
from server.tools import access
from server.tools.access.helpers import (
    _DESC_ACCESS_EXPLORER,
    validate_get_user_object_access_args,
)
from server.tools.rdam.helpers import validate_source_system_access_args
from tests.helpers import get_tool_fn, get_tool_object


class TestAccessExplorerRegistration:
    async def test_tool_registered_as_access_explorer(self) -> None:
        mcp = FastMCP("test")
        access.register(mcp)
        tool = await get_tool_object(mcp, TOOL_ACCESS_EXPLORER)
        assert tool.name == TOOL_ACCESS_EXPLORER

    async def test_query_direction_schema_is_enum(self) -> None:
        mcp = FastMCP("test")
        access.register(mcp)
        tool = await get_tool_object(mcp, TOOL_ACCESS_EXPLORER)
        props = (tool.parameters or {}).get("properties", {})
        qd = props["query_direction"]
        enum_values: set[str] = set()
        if "enum" in qd:
            enum_values.update(v for v in qd["enum"] if v is not None)
        for variant in qd.get("anyOf", []) + qd.get("oneOf", []):
            enum_values.update(v for v in variant.get("enum", []) if v is not None)
        assert enum_values == {
            "user_to_object",
            "object_to_principals",
            "user_to_objects",
            "object_to_users",
            "browse",
        }

    def test_description_covers_both_operations(self) -> None:
        assert "catalog permissions" in _DESC_ACCESS_EXPLORER
        assert "catalog_access" in _DESC_ACCESS_EXPLORER
        assert "not ACL" in _DESC_ACCESS_EXPLORER or "catalog permissions" in _DESC_ACCESS_EXPLORER
        assert MCP_OPERATION_CATALOG_ACCESS in _DESC_ACCESS_EXPLORER
        assert MCP_OPERATION_SOURCE_SYSTEM_ACCESS in _DESC_ACCESS_EXPLORER
        assert "docs://ovaledge/mcp_workflows" in _DESC_ACCESS_EXPLORER
        assert "catalog_object_access" in _DESC_ACCESS_EXPLORER
        assert "native_source_access" in _DESC_ACCESS_EXPLORER
        assert "What tables/schemas/columns can I see/view/access" in _DESC_ACCESS_EXPLORER


class TestAccessExplorerValidation:
    def test_catalog_validate_requires_direction(self) -> None:
        err = validate_get_user_object_access_args(None, "user1", 1, "oetable", None, None)
        assert err is not None
        assert err["status_code"] == 400

    def test_catalog_validate_user_to_object_requires_username(self) -> None:
        err = validate_get_user_object_access_args(
            "user_to_object", None, 1, "oetable", None, None
        )
        assert err is not None
        assert "username" in err["error"]

    def test_catalog_validate_object_resolution_exclusive(self) -> None:
        err = validate_get_user_object_access_args(
            "object_to_principals",
            None,
            1,
            "oetable",
            "conn.schema.table",
            None,
        )
        assert err is not None
        assert "one object resolution" in err["error"]

    def test_rdam_validate_rejects_invalid_source(self) -> None:
        err = validate_source_system_access_args(
            "postgres", "user_to_objects", "u", "prod_db.t", "table", 1000
        )
        assert err is not None
        assert "source_system" in err["error"]

    async def test_unknown_operation_rejected_without_http(self) -> None:
        from server.tools.access.invocations import _invoke_access_explorer

        out = await _invoke_access_explorer(
            operation="not_a_real_op",
            query_direction="user_to_object",
            username="john.doe",
            object_id=42,
            object_type="oetable",
            fully_qualified_name=None,
            object_name=None,
            resolve_all_matches=False,
            source_system=None,
            object_path=None,
            connection_id=None,
            privileges=None,
            include_columns=False,
            scope_mode="exact",
            access_intent_confirmed=None,
        )
        assert out["status_code"] == 400
        assert "operation" in out["error"].lower()

    async def test_source_system_access_requires_source_system(self) -> None:
        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation=MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
            query_direction="user_to_objects",
            username="svc_analytics",
            object_path="prod_db.public.orders",
            object_type="table",
            connection_id=1000,
        )
        assert out["status_code"] == 400
        assert "source_system" in out["error"]

    async def test_catalog_missing_query_direction(self) -> None:
        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation=MCP_OPERATION_CATALOG_ACCESS,
            username="john.doe",
            object_id=42,
            object_type="oetable",
        )
        assert out["status_code"] == 400
        assert "query_direction" in out["error"]


class TestAccessExplorerCatalogPath:
    @patch("server.tools.access.invocations.ovaledge_client")
    async def test_catalog_access_maps_params_with_operation(
        self, mock_client_factory: AsyncMock
    ) -> None:
        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "ok": True,
            "data": {
                "queryDirection": "user_to_object",
                "objectId": 42,
                "objectType": "oetable",
                "redirectUrl": "#nav/table?id=42",
            },
        }
        mock_client_factory.return_value.__aenter__.return_value = mock_client

        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        result = await fn(
            operation=MCP_OPERATION_CATALOG_ACCESS,
            query_direction="user_to_object",
            username="john.doe",
            object_id=42,
            object_type="oetable",
        )
        assert result["ok"] is True
        mock_client.get.assert_awaited_once()
        assert mock_client.get.await_args.args[0] == MCP_PATH_ACCESS_EXPLORER
        params = mock_client.get.await_args.kwargs["params"]
        assert params["operation"] == MCP_OPERATION_CATALOG_ACCESS
        assert params["queryDirection"] == "user_to_object"
        assert params["username"] == "john.doe"
        assert params["objectId"] == 42

    @patch("server.tools.access.invocations.ovaledge_client")
    async def test_object_to_principals_requires_access_intent(
        self, mock_client_factory: AsyncMock
    ) -> None:
        mock_client = AsyncMock()
        mock_client_factory.return_value.__aenter__.return_value = mock_client

        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation=MCP_OPERATION_CATALOG_ACCESS,
            query_direction="object_to_principals",
            object_id=42,
            object_type="oetable",
        )
        assert out.get("error_code") == "ACCESS_INTENT_REQUIRED"
        mock_client.get.assert_not_awaited()

    @patch("server.tools.access.invocations.ovaledge_client")
    async def test_catalog_connector_by_name(self, mock_client_factory: AsyncMock) -> None:
        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "ok": True,
            "data": {
                "queryDirection": "object_to_principals",
                "objectId": 1002,
                "objectType": "connection",
                "objectName": "looker",
            },
        }
        mock_client_factory.return_value.__aenter__.return_value = mock_client

        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        result = await fn(
            operation=MCP_OPERATION_CATALOG_ACCESS,
            query_direction="object_to_principals",
            object_name="looker connector",
            object_type="connection",
            access_intent_confirmed="catalog_acl",
        )
        assert result["ok"] is True
        params = mock_client.get.await_args.kwargs["params"]
        assert params["operation"] == MCP_OPERATION_CATALOG_ACCESS
        assert params["objectName"] == "looker connector"
        assert params["objectType"] == "connection"

    @patch("server.tools.access.invocations.ovaledge_client")
    async def test_catalog_fqn_happy_path(self, mock_client_factory: AsyncMock) -> None:
        mock_client = AsyncMock()
        mock_client.get.return_value = {
            "ok": True,
            "data": {
                "queryDirection": "user_to_object",
                "fullyQualifiedName": "db.schema.table",
            },
        }
        mock_client_factory.return_value.__aenter__.return_value = mock_client

        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        result = await fn(
            operation=MCP_OPERATION_CATALOG_ACCESS,
            query_direction="user_to_object",
            username="john.doe",
            fully_qualified_name="db.schema.table",
        )
        assert result["ok"] is True
        params = mock_client.get.await_args.kwargs["params"]
        assert params["fullyQualifiedName"] == "db.schema.table"
        assert params["operation"] == MCP_OPERATION_CATALOG_ACCESS


class TestAccessExplorerSourceSystemPath:
    async def test_source_system_access_forwards_operation(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation=MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
            source_system="redshift",
            query_direction="user_to_objects",
            username="svc_analytics",
            object_path="prod_db.public.orders",
            object_type="table",
            connection_id=1000,
        )
        assert out["ok"] is True
        mock_oe_client.get.assert_any_call(
            MCP_PATH_ACCESS_EXPLORER,
            params={
                "operation": MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
                "sourceSystem": "redshift",
                "queryDirection": "user_to_objects",
                "username": "svc_analytics",
                "objectPath": "prod_db.public.orders",
                "objectType": "table",
                "connectionId": 1000,
            },
        )

    async def test_object_to_users_requires_native_intent(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        out = await fn(
            operation=MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
            source_system="snowflake",
            query_direction="object_to_users",
            object_path="prod_db.public.orders",
            object_type="table",
            connection_id=1000,
        )
        assert out.get("error_code") == "ACCESS_INTENT_REQUIRED"
        mock_oe_client.get.assert_not_awaited()

    async def test_browse_forwards_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"objects": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_ACCESS_EXPLORER)
        await fn(
            operation=MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
            source_system="redshift",
            query_direction="browse",
            connection_id=1000,
            object_type="database",
        )
        mock_oe_client.get.assert_any_call(
            MCP_PATH_ACCESS_EXPLORER,
            params={
                "operation": MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
                "sourceSystem": "redshift",
                "queryDirection": "browse",
                "objectType": "database",
                "connectionId": 1000,
            },
        )
