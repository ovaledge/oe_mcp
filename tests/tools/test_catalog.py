import json
from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_COLUMN_PROFILE,
    MCP_PATH_ENTITY_RELATIONSHIPS,
    MCP_PATH_LINEAGE,
    MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
    MCP_PATH_SEARCH_CATALOG,
    MCP_PATH_UPDATE_ASSET_DESCRIPTIONS,
    MCP_PATH_UPDATE_CDE_ASSOCIATIONS,
    MCP_SEARCH_CATEGORY_NAME_PARAM,
    MCP_SEARCH_CLASSIFICATIONS_PARAM,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_CUSTOM_FIELDS_PARAM,
    MCP_SEARCH_DATA_PRODUCTS_PARAM,
    MCP_SEARCH_DOMAIN_NAME_PARAM,
    MCP_SEARCH_GLOSSARY_TERMS_PARAM,
    MCP_SEARCH_SERVER_TYPE_PARAM,
    MCP_SEARCH_TAGS_PARAM,
    MCP_SEARCH_TERMS_PARAM,
)
from server.tools import catalog
from server.tools.catalog.helpers import _DESC_SEARCH
from tests.conftest import (
    MOCK_ASSET_DETAIL,
    MOCK_LINEAGE_RESPONSE,
    MOCK_SEARCH_RESPONSE,
    MOCK_UPDATE_CDE_RESPONSE,
)
from tests.helpers import get_tool_fn
from tests.tools.confirm_test_helpers import invoke_write_confirmed


class TestSearchCatalogAssets:
    async def test_enriches_absolute_nav_url_from_relative_nav_link(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "items": [
                {
                    "objectId": 2468,
                    "objectType": "glossary",
                    "objectName": "Sidheshwar",
                    "navLink": "#nav/glossary?browse=summary&id=2468",
                }
            ],
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(search_terms=["Sidheshwar"])
        hit = result["items"][0]
        assert hit["navLink"] == "#nav/glossary?browse=summary&id=2468"
        assert hit["redirectUrl"].startswith("https://mock.ovaledge.com/")
        assert hit["redirectUrl"].endswith("#nav/glossary?browse=summary&id=2468")
        assert "navUrl" not in hit

    def test_search_description_rejects_native_grant_fallback(self) -> None:
        assert "source_system_access" in _DESC_SEARCH

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

    async def test_lexical_arrays_tags_terms_custom_fields_data_products(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(
            tags=["Operations"],
            terms=["Revenue"],
            custom_fields=["Confidential"],
            data_products=["Customer 360"],
            classifications=["PII", "Financial"],
            context_query="Find assets with Operations tag and Revenue term",
        )
        params = mock_oe_client.get.call_args[1]["params"]
        assert json.loads(params[MCP_SEARCH_TAGS_PARAM]) == ["Operations"]
        assert json.loads(params[MCP_SEARCH_GLOSSARY_TERMS_PARAM]) == ["Revenue"]
        assert json.loads(params[MCP_SEARCH_CUSTOM_FIELDS_PARAM]) == ["Confidential"]
        assert json.loads(params[MCP_SEARCH_DATA_PRODUCTS_PARAM]) == ["Customer 360"]
        assert json.loads(params[MCP_SEARCH_CLASSIFICATIONS_PARAM]) == ["PII", "Financial"]
        assert params[MCP_SEARCH_CONTEXT_QUERY_PARAM].startswith("Find assets")
        assert MCP_SEARCH_TERMS_PARAM not in params

    async def test_omits_classifications_when_empty(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(classifications=[], limit=10)
        params = mock_oe_client.get.call_args[1]["params"]
        assert MCP_SEARCH_CLASSIFICATIONS_PARAM not in params

    async def test_filters_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(
            schema_name="sakila",
            connection_name="ovaledgedb",
            owner="admin",
            steward="steward@example.com",
            custodian="custodian@example.com",
        )
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["schemaName"] == "sakila"
        assert params["connectionName"] == "ovaledgedb"
        assert params["owner"] == "admin"
        assert params["steward"] == "steward@example.com"
        assert params["custodian"] == "custodian@example.com"

    async def test_server_type_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(
            context_query="Find all assets related to MySQL databases",
            server_type="mysql",
        )
        params = mock_oe_client.get.call_args[1]["params"]
        assert params[MCP_SEARCH_SERVER_TYPE_PARAM] == "mysql"
        assert params[MCP_SEARCH_CONTEXT_QUERY_PARAM].startswith("Find all assets")

    async def test_server_type_case_insensitive(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(server_type="MySQL")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params[MCP_SEARCH_SERVER_TYPE_PARAM] == "mysql"

    async def test_server_type_omitted_when_unset(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(search_terms=["customer"])
        params = mock_oe_client.get.call_args[1]["params"]
        assert MCP_SEARCH_SERVER_TYPE_PARAM not in params

    async def test_server_type_invalid_returns_400(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(server_type="not-a-real-connector")
        assert result["status_code"] == 400
        assert "server_type" in result["error"]
        mock_oe_client.get.assert_not_called()

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

    async def test_glossary_placement_filters_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        await tool_fn(
            object_type="glossary",
            domain_name="PrakashDOmain",
            category_name="test",
            subcategory_name="okok",
        )
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["objectType"] == "glossary"
        assert params[MCP_SEARCH_DOMAIN_NAME_PARAM] == "PrakashDOmain"
        assert params[MCP_SEARCH_CATEGORY_NAME_PARAM] == "test"
        assert params["subCategoryName"] == "okok"

    async def test_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(403, "Forbidden")

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "search_catalog_assets")
        result = await tool_fn(search_terms=["secret"])

        assert "error" in result
        assert result["status_code"] == 403


class TestCatalogAssetDetails:
    async def test_enriches_absolute_nav_url_from_relative_nav_link(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "objectId": 2468,
                "objectType": "glossary",
                "objectName": "Sidheshwar",
                "navLink": "#nav/glossary?browse=summary&id=2468",
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "catalog_asset_details")
        out = await tool_fn(object_id=2468, object_type="glossary")
        assert out["data"]["navLink"] == "#nav/glossary?browse=summary&id=2468"
        assert out["data"]["redirectUrl"].endswith("#nav/glossary?browse=summary&id=2468")
        assert "redirectUrl" not in out
        assert "navUrl" not in out

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

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(502, "Bad gateway")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "column_profile_statistics")
        out = await fn(object_id=7, object_type="oetable")
        assert out["status_code"] == 502


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

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(503, "Unavailable")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "table_entity_relationships")
        out = await fn(object_id=99)
        assert out["status_code"] == 503


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

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(504, "Gateway timeout")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1, object_type="oetable")
        assert out["status_code"] == 504


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
    async def test_confirm_preview_blocks_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(
            object_id=42,
            object_type="oetable",
            description_field="business_description",
            description_text="Updated business text",
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["doNotUpdate"] is True
        assert "confirmationToken" in out
        mock_oe_client.post.assert_not_called()

    async def test_post_body_and_formatted_response(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = dict(MOCK_UPDATE_DESCRIPTIONS_RESPONSE)
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await invoke_write_confirmed(

            fn,
            object_id=42,
            object_type="oetable",
            description_field="business_description",
            description_text="Updated business text",
            reason="MCP test"
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
            write_confirmed_by_user=False,
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
        out = await invoke_write_confirmed(

            fn,
            object_id=1,
            object_type="oetable",
            technical_description="A description from MCP tool via cursor.",
            prompt="Update the technical description of workflowtemplate table"
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
        await invoke_write_confirmed(

            fn,
            object_id=1,
            object_type="oetable",
            description_field="business_description",
            description_text="via generic pair"
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

    async def test_accepts_oeglobaldomain(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"status": "success"}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        await invoke_write_confirmed(

            fn,
            object_id=10,
            object_type="oeglobaldomain",
            domain_description="Domain text"
        )
        body = mock_oe_client.post.call_args[0][1]
        assert body["target"]["objectType"] == "oeglobaldomain"
        assert body["descriptions"]["domainDescription"] == "Domain text"

    async def test_oecode_alias_maps_to_code_api_type(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"status": "success"}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        await invoke_write_confirmed(

            fn,
            object_id=7,
            object_type="oecode",
            business_description="Code business",
            prompt="Update the business description"
        )
        body = mock_oe_client.post.call_args[0][1]
        assert body["target"]["objectType"] == "code"
        assert body["descriptions"]["businessDescription"] == "Code business"

    async def test_rejects_oestory(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await fn(
            object_id=1,
            object_type="oestory",
            description_field="business_description",
            description_text="x",
        )
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_asset_descriptions")
        out = await invoke_write_confirmed(

            fn,
            object_id=1,
            object_type="oetable",
            description_field="business_description",
            description_text="x"
        )
        assert out["status_code"] == 403
        assert "403" in out["error"]

class TestMetadataChangesBetweenCrawls:
    async def test_forwards_body(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"ok": True, "data": {"changeSummary": "x"}}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(
            question="What changed in CUSTOMER schema after the latest crawl?",
            connection_name="Snowflake PROD",
            schema_names=["CUSTOMER"],
            table_names=["CUSTOMER_PROFILE"],
            last_n_days=2,
            from_crawl_id=101,
            to_crawl_id=102,
        )
        assert out["ok"] is True
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
            body={
                "question": "What changed in CUSTOMER schema after the latest crawl?",
                "connectionName": "Snowflake PROD",
                "schemaNames": ["CUSTOMER"],
                "tableNames": ["CUSTOMER_PROFILE"],
                "lastNDays": 2,
                "fromCrawlId": 101,
                "toCrawlId": 102,
            },
        )

    async def test_rejects_days_and_weeks_together(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(last_n_days=1, last_n_weeks=1)
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_invalid_crawl_range(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(from_crawl_id=10, to_crawl_id=9)
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(500, "Internal error")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(question="Show drift")
        assert out["status_code"] == 500


class TestUpdateCdeAssociations:
    async def test_confirm_preview_blocks_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await fn(
            targets=[{"object_id": 3337, "object_type": "oeschema"}],
            action="Yes",
            cde_justification="Understanding CDE functionality",
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["doNotUpdate"] is True
        assert "confirmationToken" in out
        mock_oe_client.post.assert_not_called()

    async def test_post_body_matches_payload(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = dict(MOCK_UPDATE_CDE_RESPONSE)
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await invoke_write_confirmed(

            fn,
            targets=[{"object_id": 3337, "object_type": "oeschema"}],
            action="Yes",
            cde_justification="Understanding CDE functionality"
        )
        assert out["status"] == "success"
        assert "formattedResponse" in out
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_UPDATE_CDE_ASSOCIATIONS,
            {
                "targets": [{"objectId": 3337, "objectType": "oeschema"}],
                "action": "Yes",
                "cdeJustification": "Understanding CDE functionality",
            },
        )

    async def test_rejects_unsupported_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await fn(
            targets=[{"object_id": 1, "object_type": "glossary"}],
            action="Yes",
        )
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_dry_run_skips_confirm_and_posts(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {"ok": True, "data": {"status": "success"}}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        await fn(
            targets=[{"object_id": 10, "object_type": "oetable"}],
            action="None",
            dry_run=True,
        )
        body = mock_oe_client.post.call_args[0][1]
        assert body["options"] == {"dryRun": True}
        assert body["action"] == "None"

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await invoke_write_confirmed(

            fn,
            targets=[{"object_id": 1, "object_type": "oetable"}],
            action="Yes"
        )
        assert out["status_code"] == 403
