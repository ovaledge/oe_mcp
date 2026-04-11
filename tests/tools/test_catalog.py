from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_COLUMN_PROFILE,
    MCP_PATH_ENTITY_RELATIONSHIPS,
    MCP_PATH_LINEAGE,
    MCP_PATH_SEARCH_CATALOG,
)
from server.tools import catalog
from tests.conftest import MOCK_ASSET_DETAIL, MOCK_LINEAGE_RESPONSE, MOCK_SEARCH_RESPONSE
from tests.helpers import get_tool_fn


class TestSearchCatalogAssets:
    async def test_search_get_params(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(search_term="customer transactions", object_type="oetable")

        assert result == MOCK_SEARCH_RESPONSE
        mock_oe_client.get.assert_called_once()
        args, kwargs = mock_oe_client.get.call_args
        assert args[0] == MCP_PATH_SEARCH_CATALOG
        params = kwargs["params"]
        assert params["searchTerm"] == "customer transactions"
        assert params["objectType"] == "oetable"
        assert params["page"] == 1
        assert "connectionName" not in params

    async def test_limit_capped(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(search_term="x", limit=500)

        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 100

    async def test_invalid_object_type_returns_400(self, mock_oe_client: object) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(search_term="x", object_type="TABLE")
        assert result["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_error_returns_structured_dict(self, mock_oe_client: object) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(403, "Forbidden")

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(search_term="secret")

        assert "error" in result
        assert result["status_code"] == 403


class TestCatalogAssetDetails:
    async def test_fqn_only(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        out = await tool_fn(fully_qualified_name="db.schema.table")
        assert out == MOCK_ASSET_DETAIL
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"fullyQualifiedName": "db.schema.table"}

    async def test_object_id_and_type(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        await tool_fn(object_id=42, object_type="oetable")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"objectId": 42, "objectType": "oetable"}

    async def test_rejects_mixing_fqn_and_id(self, mock_oe_client: object) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        result = await tool_fn(fully_qualified_name="a.b.c", object_id=1)
        assert result["status_code"] == 400
        mock_oe_client.get.assert_not_called()


class TestColumnProfileStatistics:
    async def test_oetable(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = {"columns": []}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "column_profile_statistics")
        await fn(object_id=7, object_type="oetable")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_COLUMN_PROFILE,
            params={"objectId": 7, "objectType": "oetable"},
        )

    async def test_rejects_glossary(self, mock_oe_client: object) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "column_profile_statistics")
        out = await fn(object_id=1, object_type="glossary")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()


class TestTableEntityRelationships:
    async def test_forwards_object_id(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = {"relationships": []}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "table_entity_relationships")
        await fn(object_id=99)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_ENTITY_RELATIONSHIPS,
            params={"objectId": 99},
        )


class TestAssetLineage:
    async def test_forwards_params(self, mock_oe_client: object) -> None:
        mock_oe_client.get.return_value = MOCK_LINEAGE_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1, object_type="oefile", depth=4)
        assert out == MOCK_LINEAGE_RESPONSE
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LINEAGE,
            params={"objectId": 1, "objectType": "oefile", "depth": 4},
        )
