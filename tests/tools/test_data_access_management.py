from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import MCP_PATH_SOURCE_SYSTEM_ACCESS
from server.tools import data_access_management
from tests.helpers import get_tool_fn


class TestGetSourceSystemAccess:
    async def test_user_to_objects_forwards_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        data_access_management.register(mcp)
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
        data_access_management.register(mcp)
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
        data_access_management.register(mcp)
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
        data_access_management.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(source_system="snowflake", query_direction="user_to_objects")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_missing_object_path(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        data_access_management.register(mcp)
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
        data_access_management.register(mcp)
        fn = await get_tool_fn(mcp, "get_source_system_access")
        out = await fn(
            source_system="snowflake",
            query_direction="user_to_objects",
            username="missing.user",
        )
        assert out["status_code"] == 404
