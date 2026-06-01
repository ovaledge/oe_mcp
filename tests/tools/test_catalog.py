import json
from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_COLUMN_PROFILE,
    MCP_PATH_ENTITY_RELATIONSHIPS,
    MCP_PATH_LINEAGE,
    MCP_PATH_SEARCH_CATALOG,
    MCP_PATH_UPDATE_ASSET_DESCRIPTIONS,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_TERMS_PARAM,
)
from server.tools import catalog
from tests.conftest import MOCK_ASSET_DETAIL, MOCK_LINEAGE_RESPONSE, MOCK_SEARCH_RESPONSE
from tests.helpers import get_tool_fn


class TestSearchCatalogAssets:
    async def test_search_get_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(search_terms=["customer", "transactions"], object_type="oetable")

        assert result == MOCK_SEARCH_RESPONSE
        mock_oe_client.get.assert_called_once()
        args, kwargs = mock_oe_client.get.call_args
        assert args[0] == MCP_PATH_SEARCH_CATALOG
        params = kwargs["params"]
        assert json.loads(params[MCP_SEARCH_TERMS_PARAM]) == ["customer", "transactions"]
        assert params["objectType"] == "oetable"
        assert params["page"] == 1
        assert "connectionName" not in params

    async def test_context_query_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        full_q = "Where do we store employee payroll dimensions?"
        await tool_fn(search_terms=["employee"], context_query=full_q)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params[MCP_SEARCH_CONTEXT_QUERY_PARAM] == full_q
        assert json.loads(params[MCP_SEARCH_TERMS_PARAM]) == ["employee"]

    async def test_omits_search_terms_when_empty(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(search_terms=[], limit=10)
        params = mock_oe_client.get.call_args[1]["params"]
        assert MCP_SEARCH_TERMS_PARAM not in params

    async def test_limit_capped(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(search_terms=["x"], limit=500)

        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 100

    async def test_search_accepts_extended_object_type(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(search_terms=["q"], object_type="oequery")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["objectType"] == "oequery"

    async def test_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(403, "Forbidden")

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(search_terms=["secret"])

        assert "error" in result
        assert result["status_code"] == 403


class TestCatalogAssetDetails:
    async def test_fqn_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        out = await tool_fn(fully_qualified_name="db.schema.table")
        assert out == MOCK_ASSET_DETAIL
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"fullyQualifiedName": "db.schema.table"}

    async def test_object_id_and_type(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        await tool_fn(object_id=42, object_type="oetable")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"objectId": 42, "objectType": "oetable"}

    async def test_rejects_mixing_fqn_and_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        result = await tool_fn(fully_qualified_name="a.b.c", object_id=1)
        assert result["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_missing_lookup_mode(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        result = await tool_fn()
        assert result["status_code"] == 400
        assert "fully_qualified_name" in result["error"]
        mock_oe_client.get.assert_not_called()

    async def test_rejects_invalid_object_type_with_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        result = await tool_fn(object_id=1, object_type="invalid_type")
        assert result["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(502, "Bad gateway")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        result = await tool_fn(object_id=1, object_type="oetable")
        assert result["status_code"] == 502
        assert "502" in result["error"]


class TestColumnProfileStatistics:
    async def test_oetable(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"columns": []}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "column_profile_statistics")
        await fn(object_id=7, object_type="oetable")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_COLUMN_PROFILE,
            params={"objectId": 7, "objectType": "oetable"},
        )

    async def test_rejects_glossary(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "column_profile_statistics")
        out = await fn(object_id=1, object_type="glossary")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()


class TestTableEntityRelationships:
    async def test_forwards_object_id(self, mock_oe_client: AsyncMock) -> None:
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
    async def test_forwards_params(self, mock_oe_client: AsyncMock) -> None:
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

    async def test_rejects_non_table_file_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1, object_type="glossary")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()


class TestTableEntityRelationshipsErrors:
    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(503, "Unavailable")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "table_entity_relationships")
        out = await fn(object_id=5)
        assert out["status_code"] == 503
        assert "503" in out["error"]


MOCK_UPDATE_DESCRIPTIONS_RESPONSE = {
    "status": "success",
    "target": {
        "objectId": 42,
        "objectType": "oetable",
        "redirectUrl": "https://host/#nav/table?id=42",
    },
    "requestedFields": ["businessDescription"],
    "updatedFields": ["businessDescription"],
    "blockedFields": [],
    "blockedReasons": [],
    "audit": {"source": "OE-MCP"},
}


class TestUpdateAssetDescriptions:
    async def test_post_body_and_formatted_response(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = dict(MOCK_UPDATE_DESCRIPTIONS_RESPONSE)
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(
            object_id=42,
            object_type="oetable",
            description_field="business_description",
            description_text="Updated business text",
            reason="MCP test",
        )
        assert out["status"] == "success"
        assert "formattedResponse" in out
        assert "42" in out["formattedResponse"]
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_UPDATE_ASSET_DESCRIPTIONS,
            {
                "target": {"objectId": 42, "objectType": "oetable"},
                "descriptions": {
                    "description": "Updated business text",
                    "descriptionField": "businessDescription",
                },
                "clientContext": {"reason": "MCP test"},
            },
        )

    async def test_multiple_description_fields(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"status": "success"}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        await fn(
            object_id=1,
            object_type="oecolumn",
            business_description="biz",
            technical_description="tech",
            dry_run=True,
        )
        body = mock_oe_client.post.call_args[0][1]
        assert body["descriptions"] == {
            "businessDescription": "biz",
            "technicalDescription": "tech",
        }
        assert body["options"] == {"dryRun": True}

    async def test_rejects_no_description_fields(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(object_id=1, object_type="oetable")
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_description_text_requires_description_field(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(
            object_id=1,
            object_type="oetable",
            description_text="ambiguous description only",
        )
        assert out["status_code"] == 400
        assert "description_field" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_rejects_ambiguous_column_description_without_slot_in_prompt(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(
            object_id=1,
            object_type="oecolumn",
            business_description="guessed business",
            prompt="Update the description on a column called fieldname",
        )
        assert out["status_code"] == 400
        assert "multiple description slots" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_allows_technical_when_prompt_names_technical(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {"status": "success"}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(
            object_id=1,
            object_type="oetable",
            technical_description="A description from MCP tool via cursor.",
            prompt="Update the technical description of workflowtemplate table",
        )
        assert out.get("status_code") != 400
        mock_oe_client.post.assert_called_once()
        body = mock_oe_client.post.call_args[0][1]
        assert body["descriptions"]["technicalDescription"] == (
            "A description from MCP tool via cursor."
        )
        assert "technical description" in body["clientContext"]["prompt"].lower()

    async def test_description_field_and_text_maps_to_api(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {"status": "success"}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        await fn(
            object_id=1,
            object_type="oetable",
            description_field="business_description",
            description_text="via generic pair",
        )
        body = mock_oe_client.post.call_args[0][1]
        assert body["descriptions"] == {
            "description": "via generic pair",
            "descriptionField": "businessDescription",
        }

    async def test_rejects_invalid_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(
            object_id=1,
            object_type="not_a_type",
            business_description="x",
        )
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(
            object_id=1,
            object_type="oetable",
            description_field="business_description",
            description_text="x",
        )
        assert out["status_code"] == 403
        assert "403" in out["error"]
