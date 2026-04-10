from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.tools import catalog
from tests.conftest import MOCK_ASSET_DETAIL, MOCK_COUNT_RESPONSE, MOCK_SEARCH_RESPONSE
from tests.helpers import get_tool_fn


class TestSearchCatalogAssets:
    async def test_basic_keyword_search(self, mock_oe_client: object) -> None:
        mock_oe_client.post.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(keywords=["customer", "transactions"])

        assert result == MOCK_SEARCH_RESPONSE
        mock_oe_client.post.assert_called_once()
        ca = mock_oe_client.post.call_args
        if ca.kwargs:
            call_body = ca.kwargs.get("body")
        else:
            call_body = ca.args[1] if len(ca.args) > 1 else None
        assert call_body is not None
        assert call_body["keywords"] == ["customer", "transactions"]

    async def test_limit_capped_at_50(self, mock_oe_client: object) -> None:
        mock_oe_client.post.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(keywords=["test"], limit=100)

        ca = mock_oe_client.post.call_args
        call_body = ca.kwargs.get("body") if ca.kwargs else ca.args[1]
        assert call_body["limit"] == 50

    async def test_offset_defaults_to_zero(self, mock_oe_client: object) -> None:
        mock_oe_client.post.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(keywords=["test"])

        ca = mock_oe_client.post.call_args
        call_body = ca.kwargs.get("body") if ca.kwargs else ca.args[1]
        assert call_body["offset"] == 0

    async def test_error_returns_structured_dict(self, mock_oe_client: object) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(403, "Forbidden")

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(keywords=["secret"])

        assert "error" in result
        assert result["status_code"] == 403


class TestGetAssetDetails:
    async def test_forwards_params(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "get_asset_details")
        out = await tool_fn("obj-1", "TABLE", include_columns=True)
        assert out == MOCK_ASSET_DETAIL
        mock_oe_client.get.assert_called_once()
        args, kwargs = mock_oe_client.get.call_args
        assert "/api/mcp/assets/obj-1/composite" in args[0]
        assert kwargs.get("params", {})["objectType"] == "TABLE"


class TestCountCatalog:
    async def test_post_body(self, mock_oe_client: object) -> None:
        mock_oe_client.post.return_value = MOCK_COUNT_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "count_catalog_assets")
        await tool_fn(keywords=["a"], object_types=["TABLE"])
        ca = mock_oe_client.post.call_args
        body = ca.kwargs.get("body") if ca.kwargs else ca.args[1]
        assert body["keywords"] == ["a"]
        assert body["objectTypes"] == ["TABLE"]
