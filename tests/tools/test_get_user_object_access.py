from unittest.mock import AsyncMock, patch

from fastmcp import FastMCP

from server.constants import MCP_PATH_GET_USER_OBJECT_ACCESS, TOOL_GET_USER_OBJECT_ACCESS
from server.tools import access
from server.tools.access.helpers import (
    _DESC_GET_USER_OBJECT_ACCESS,
    validate_get_user_object_access_args,
)
from tests.helpers import get_tool_fn, get_tool_object


class TestGetUserObjectAccess:
    async def test_tool_registered(self) -> None:
        mcp = FastMCP("test")
        access.register(mcp)
        tool = await get_tool_object(mcp, TOOL_GET_USER_OBJECT_ACCESS)
        assert tool.name == TOOL_GET_USER_OBJECT_ACCESS

    def test_tool_description_mentions_catalog_acl(self) -> None:
        assert "catalog ACL" in _DESC_GET_USER_OBJECT_ACCESS
        assert "source_system_access" in _DESC_GET_USER_OBJECT_ACCESS
        assert "user_to_object" in _DESC_GET_USER_OBJECT_ACCESS
        assert "connection" in _DESC_GET_USER_OBJECT_ACCESS
        assert "docs://ovaledge/mcp_workflows" in _DESC_GET_USER_OBJECT_ACCESS
        assert "catalog_object_access" in _DESC_GET_USER_OBJECT_ACCESS

    def test_validate_requires_direction(self) -> None:
        err = validate_get_user_object_access_args(None, "user1", 1, "oetable", None, None)
        assert err is not None
        assert err["status_code"] == 400

    def test_validate_user_to_object_requires_username(self) -> None:
        err = validate_get_user_object_access_args(
            "user_to_object", None, 1, "oetable", None, None
        )
        assert err is not None
        assert "username" in err["error"]

    def test_validate_object_resolution_exclusive(self) -> None:
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

    @patch("server.tools.access.register.ovaledge_client")
    async def test_invoke_maps_params(self, mock_client_factory) -> None:
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
        fn = await get_tool_fn(mcp, TOOL_GET_USER_OBJECT_ACCESS)
        result = await fn(
            query_direction="user_to_object",
            username="john.doe",
            object_id=42,
            object_type="oetable",
        )
        assert result["ok"] is True
        mock_client.get.assert_awaited_once()
        call_kwargs = mock_client.get.await_args.kwargs
        assert call_kwargs["params"]["queryDirection"] == "user_to_object"
        assert call_kwargs["params"]["username"] == "john.doe"
        assert call_kwargs["params"]["objectId"] == 42
        assert MCP_PATH_GET_USER_OBJECT_ACCESS in mock_client.get.await_args.args[0]

    @patch("server.tools.access.register.ovaledge_client")
    async def test_invoke_connector_by_name(self, mock_client_factory) -> None:
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
        fn = await get_tool_fn(mcp, TOOL_GET_USER_OBJECT_ACCESS)
        result = await fn(
            query_direction="object_to_principals",
            object_name="looker connector",
            object_type="connection",
            access_intent_confirmed="catalog_acl",
        )
        assert result["ok"] is True
        call_kwargs = mock_client.get.await_args.kwargs
        assert call_kwargs["params"]["objectName"] == "looker connector"
        assert call_kwargs["params"]["objectType"] == "connection"
