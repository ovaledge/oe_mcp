import json
from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_ASSET_DETAILS,
    MCP_PATH_ASSET_EXPLORER,
    MCP_PATH_ASSET_LINEAGE,
    MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
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
from server.tools.catalog.helpers import _DESC_ASSET_EXPLORER
from tests.conftest import (
    MOCK_ASSET_DETAIL,
    MOCK_LINEAGE_RESPONSE,
    MOCK_SEARCH_RESPONSE,
    MOCK_UPDATE_CDE_RESPONSE,
)
from tests.helpers import get_tool_fn
from tests.tools.confirm_test_helpers import invoke_write_confirmed


class TestAssetExplorer:
    async def test_enriches_absolute_nav_url_from_relative_nav_link(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "items": [
                    {
                        "objectId": 2468,
                        "objectType": "glossary",
                        "objectName": "Sidheshwar",
                        "navLink": "#nav/glossary?browse=summary&id=2468",
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        result = await tool_fn(search_terms=["Sidheshwar"])
        hit = result["data"]["items"][0]
        assert hit["navLink"] == "#nav/glossary?browse=summary&id=2468"
        assert hit["redirectUrl"].startswith("https://mock.ovaledge.com/")
        assert hit["redirectUrl"].endswith("#nav/glossary?browse=summary&id=2468")
        assert "navUrl" not in hit

    def test_explorer_description_rejects_native_grant_fallback(self) -> None:
        assert "source_system_access" in _DESC_ASSET_EXPLORER

    def test_explorer_description_defaults_to_open_catalog_search(self) -> None:
        assert "omit object_type" in _DESC_ASSET_EXPLORER.lower()
        assert "do not default to tables-only" in _DESC_ASSET_EXPLORER.lower()
        assert "asset_details" in _DESC_ASSET_EXPLORER.lower()
        assert "shortlist" in _DESC_ASSET_EXPLORER.lower()
        assert "exact governance names" in _DESC_ASSET_EXPLORER.lower()
        assert "find data assets" in _DESC_ASSET_EXPLORER.lower()
        assert "blanket" not in _DESC_ASSET_EXPLORER.lower()

    async def test_search_get_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        result = await tool_fn(search_terms=["customer", "transactions"], object_type="oetable")

        assert result == MOCK_SEARCH_RESPONSE
        mock_oe_client.get.assert_called_once()
        args, kwargs = mock_oe_client.get.call_args
        assert args[0] == MCP_PATH_ASSET_EXPLORER
        params = kwargs["params"]
        assert json.loads(params[MCP_SEARCH_TERMS_PARAM]) == ["customer", "transactions"]
        assert params["objectType"] == "oetable"
        assert params["page"] == 1
        assert "connectionName" not in params

    async def test_context_query_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        full_q = "Where do we store employee payroll dimensions?"
        await tool_fn(search_terms=["employee"], context_query=full_q)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params[MCP_SEARCH_CONTEXT_QUERY_PARAM] == full_q
        assert json.loads(params[MCP_SEARCH_TERMS_PARAM]) == ["employee"]

    async def test_omits_search_terms_when_empty(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        await tool_fn(search_terms=[], limit=10)
        params = mock_oe_client.get.call_args[1]["params"]
        assert MCP_SEARCH_TERMS_PARAM not in params

    async def test_lexical_arrays_tags_terms_custom_fields_data_products(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
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
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        await tool_fn(classifications=[], limit=10)
        params = mock_oe_client.get.call_args[1]["params"]
        assert MCP_SEARCH_CLASSIFICATIONS_PARAM not in params

    async def test_filters_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
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
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
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
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        await tool_fn(server_type="MySQL")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params[MCP_SEARCH_SERVER_TYPE_PARAM] == "mysql"

    async def test_server_type_omitted_when_unset(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        await tool_fn(search_terms=["customer"])
        params = mock_oe_client.get.call_args[1]["params"]
        assert MCP_SEARCH_SERVER_TYPE_PARAM not in params

    async def test_server_type_invalid_returns_400(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        result = await tool_fn(server_type="not-a-real-connector")
        assert result["status_code"] == 400
        assert "server_type" in result["error"]
        mock_oe_client.get.assert_not_called()

    async def test_limit_capped(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        await tool_fn(search_terms=["x"], limit=500)

        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 50

    async def test_search_accepts_extended_object_type(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        await tool_fn(search_terms=["q"], object_type="oequery")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["objectType"] == "oequery"

    async def test_glossary_placement_filters_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        await tool_fn(
            object_type="glossary",
            domain_name="PrakashDOmain",
            category_name="test",
            subcategory_id=42,
        )
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["objectType"] == "glossary"
        assert params[MCP_SEARCH_DOMAIN_NAME_PARAM] == "PrakashDOmain"
        assert params[MCP_SEARCH_CATEGORY_NAME_PARAM] == "test"
        assert params["subcategoryId"] == 42

    async def test_glossary_name_mode_forwards_standardized_params(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"glossaryTerms": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_explorer")
        await fn(object_type="glossary", name="Revenue")
        assert mock_oe_client.get.call_args[1]["params"]["objectType"] == "glossary"
        assert mock_oe_client.get.call_args[1]["params"]["name"] == "Revenue"

    async def test_tag_name_mode_forwards_hierarchy_flags(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"tags": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_explorer")
        await fn(object_type="oetag", name="PII", include_children=True)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["objectType"] == "oetag"
        assert params["name"] == "PII"
        assert params["includeChildren"] is True

    async def test_page_and_limit_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_explorer")
        await fn(search_terms=["customer"], page=3, limit=25)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["page"] == 3
        assert params["limit"] == 25

    async def test_object_type_omitted_when_unset(self, mock_oe_client: AsyncMock) -> None:
        """Open catalog search is the default — no implicit tables-only filter."""
        mock_oe_client.get.return_value = MOCK_SEARCH_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_explorer")
        await fn(search_terms=["payment"], context_query="Anything about payments")
        assert "objectType" not in mock_oe_client.get.call_args[1]["params"]

    async def test_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(403, "Forbidden")

        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)

        tool_fn = await get_tool_fn(mcp, "asset_explorer")
        result = await tool_fn(search_terms=["secret"])

        assert "error" in result
        assert result["status_code"] == 403

    async def test_rejects_invalid_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_explorer")
        out = await fn(search_terms=["x"], object_type="not_a_real_type")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()


class TestAssetExplorerSectionEnrichment:
    """Glossary and tag sections of an explorer payload get governance formatting."""

    GLOSSARY_SECTION = {
        "objectId": 1275,
        "objectType": "glossary",
        "objectName": "Revenue",
        "navLink": "#nav/glossary?browse=summary&id=1275",
    }
    TAG_SECTION = {
        "objectId": 1085,
        "objectType": "oetag",
        "objectName": "Finance & Economics",
        "navLink": "#nav/tag?id=1085&objectType=oetag",
        "childTags": [
            {
                "objectId": 1086,
                "objectName": "Macroeconomic Indicators",
                "navLink": "#nav/tag?id=1086&objectType=oetag",
            }
        ],
    }

    async def _explore(self, mock_oe_client: AsyncMock, body: dict, **kwargs: object) -> dict:
        mock_oe_client.get.return_value = body
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_explorer")
        return await fn(**kwargs)

    async def test_glossary_section_nav_links_enriched(
        self, mock_oe_client: AsyncMock
    ) -> None:
        out = await self._explore(
            mock_oe_client,
            {"ok": True, "data": {"glossaryTerms": self.GLOSSARY_SECTION}},
            object_type="glossary",
            name="Revenue",
        )
        term = out["data"]["glossaryTerms"]
        assert term["redirectUrl"].startswith("https://mock.ovaledge.com/")
        assert term["redirectUrl"].endswith("#nav/glossary?browse=summary&id=1275")

    async def test_tag_section_hierarchy_produces_formatted_response(
        self, mock_oe_client: AsyncMock
    ) -> None:
        out = await self._explore(
            mock_oe_client,
            {"ok": True, "data": {"tags": self.TAG_SECTION}},
            object_type="oetag",
            name="Finance & Economics",
            include_children=True,
        )
        formatted = out["formattedResponse"]
        assert "Finance & Economics" in formatted
        assert "Macroeconomic Indicators" in formatted
        child = out["data"]["tags"]["childTags"][0]
        assert child["redirectUrl"].endswith("#nav/tag?id=1086&objectType=oetag")

    async def test_catalog_items_and_glossary_section_enriched_together(
        self, mock_oe_client: AsyncMock
    ) -> None:
        out = await self._explore(
            mock_oe_client,
            {
                "ok": True,
                "data": {
                    "items": [
                        {
                            "objectId": 100600,
                            "objectType": "oetable",
                            "objectName": "Customers",
                            "navLink": "#nav/table?id=100600",
                        }
                    ],
                    "glossaryTerms": self.GLOSSARY_SECTION,
                },
            },
            search_terms=["customer"],
        )
        assert out["data"]["items"][0]["redirectUrl"].endswith("#nav/table?id=100600")
        assert out["data"]["glossaryTerms"]["redirectUrl"]

    async def test_error_payload_is_not_enriched(self, mock_oe_client: AsyncMock) -> None:
        body = {"error": "boom", "status_code": 500}
        out = await self._explore(mock_oe_client, body, search_terms=["x"])
        assert out == body

    async def test_ok_false_payload_is_not_enriched(
        self, mock_oe_client: AsyncMock
    ) -> None:
        body = {"ok": False, "data": {"glossaryTerms": self.GLOSSARY_SECTION}}
        out = await self._explore(mock_oe_client, body, object_type="glossary", name="Revenue")
        assert out == body
        assert "redirectUrl" not in out["data"]["glossaryTerms"]

    async def test_hits_without_nav_link_are_left_alone(
        self, mock_oe_client: AsyncMock
    ) -> None:
        out = await self._explore(
            mock_oe_client,
            {"ok": True, "data": {"items": [{"objectId": 7, "objectType": "oetable"}]}},
            search_terms=["x"],
        )
        assert "redirectUrl" not in out["data"]["items"][0]


class TestAssetDetails:
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
        tool_fn = await get_tool_fn(mcp, "asset_details")
        out = await tool_fn(object_id=2468, object_type="glossary")
        assert out["data"]["navLink"] == "#nav/glossary?browse=summary&id=2468"
        assert out["data"]["redirectUrl"].endswith("#nav/glossary?browse=summary&id=2468")
        assert "redirectUrl" not in out
        assert "navUrl" not in out

    async def test_object_id_and_type(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_ASSET_DETAIL
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_details")
        await tool_fn(object_id=42, object_type="oetable")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"objectId": 42, "objectType": "oetable"}
        assert mock_oe_client.get.call_args[0][0] == MCP_PATH_ASSET_DETAILS

    async def test_details_block_nav_link_is_enriched(
        self, mock_oe_client: AsyncMock
    ) -> None:
        """Composite payloads carry the asset under `details` — enrich that, not the wrapper."""
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "details": {
                    "objectId": 1038,
                    "objectType": "oetable",
                    "objectName": "INPATIENTDISCHARGEDETIALS",
                    "navLink": "#nav/table?id=1038",
                },
                "profile": {"columns": []},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_details")
        out = await fn(object_id=1038, object_type="oetable")
        assert out["data"]["details"]["redirectUrl"].endswith("#nav/table?id=1038")
        assert "redirectUrl" not in out["data"]

    async def test_error_payload_is_not_enriched(self, mock_oe_client: AsyncMock) -> None:
        body = {"error": "not found", "status_code": 404}
        mock_oe_client.get.return_value = body
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_details")
        assert await fn(object_id=1, object_type="oetable") == body

    async def test_ok_false_payload_is_not_enriched(
        self, mock_oe_client: AsyncMock
    ) -> None:
        body = {"ok": False, "data": {"objectId": 1, "navLink": "#nav/table?id=1"}}
        mock_oe_client.get.return_value = body
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_details")
        out = await fn(object_id=1, object_type="oetable")
        assert "redirectUrl" not in out["data"]

    async def test_rejects_invalid_object_type_with_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_details")
        result = await tool_fn(object_id=1, object_type="invalid_type")
        assert result["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(502, "Bad gateway")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        tool_fn = await get_tool_fn(mcp, "asset_details")
        result = await tool_fn(object_id=1, object_type="oetable")
        assert result["status_code"] == 502
        assert "502" in result["error"]

    async def test_happy_path_returns_enriched_detail(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "objectId": 1019,
                "objectType": "oetable",
                "objectName": "film",
                "navLink": "#nav/table?browse=summary&id=1019",
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_details")
        out = await fn(object_id=1019, object_type="oetable")
        assert out["data"]["objectName"] == "film"
        assert out["data"]["redirectUrl"].endswith("#nav/table?browse=summary&id=1019")
        mock_oe_client.get.assert_called_once()

    async def test_composite_response_includes_profile_and_relationships(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "details": {"objectId": 7, "objectType": "oetable"},
                "profile": {"columns": [{"name": "id", "nulls": 0}]},
                "relationships": [{"from": "a", "to": "b", "type": "FK"}],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_details")
        out = await fn(object_id=7, object_type="oetable")
        assert out["data"]["profile"]["columns"][0]["name"] == "id"
        assert out["data"]["relationships"][0]["type"] == "FK"


class TestAssetLineage:
    async def test_forwards_params(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_LINEAGE_RESPONSE
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1, object_type="oefile", depth=4)
        assert out == MOCK_LINEAGE_RESPONSE
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_ASSET_LINEAGE,
            params={"objectId": 1, "objectType": "oefile", "depth": 4},
        )

    async def test_oetable_default_depth_happy_path(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"nodes": [{"id": 1}], "edges": []}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1019, object_type="oetable")
        assert out["nodes"][0]["id"] == 1
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_ASSET_LINEAGE,
            params={"objectId": 1019, "objectType": "oetable", "depth": 2},
        )

    async def test_rejects_non_table_file_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1, object_type="glossary")
        assert out["status_code"] == 400
        assert "oetable or oefile" in out["error"]
        mock_oe_client.get.assert_not_called()

    async def test_rejects_oeschema(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1004, object_type="oeschema")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(504, "Gateway timeout")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1, object_type="oetable")
        assert out["status_code"] == 504

    async def test_forbidden_returns_structured_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "asset_lineage")
        out = await fn(object_id=1, object_type="oetable")
        assert out["status_code"] == 403
        assert "403" in out["error"]




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

    async def test_enhances_response_and_replaces_backend_formatted_response(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "formattedResponse": "Backend narrative that must not win.\n"
                + ("- col.x [modified]\n" * 50),
                "contextHeader": {
                    "catalogSchema": "CUSTOMER",
                    "schemaId": 10,
                    "connection": "Snowflake PROD",
                },
                "rollup": {
                    "totalChanges": 3,
                    "tablesModified": 1,
                    "columnsModified": 2,
                    "rowCountChanges": 1,
                },
                "notableDeltas": [
                    {"tableName": "orders", "rowCountDelta": 1200},
                ],
                "compareSchemaUrl": (
                    "https://example.com#nav/comparedb?srchtab=history&id=5"
                ),
                "fallback": {"show": False},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(
            question="What changed in CUSTOMER schema after the latest crawl?"
        )
        fr = out["formattedResponse"]
        assert "Backend narrative that must not win." not in fr
        assert "**Top row-count adds**" in fr
        assert "`orders` (+1,200)" in fr
        assert out["data"]["formattedResponse"] == fr
        assert "requiredInfo" in out
        assert out["data"]["usefulLinks"]["compareSchemaUrl"].endswith("id=5")

    async def test_table_scoped_question_uses_object_redirect_links_only(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "sakila", "schemaId": 1004},
                "redirectUrl": "https://example.com#nav/table?id=1019",
                "compareSchemaUrl": "https://example.com#nav/comparedb?id=5",
                "rollup": {"totalChanges": 1, "tablesModified": 1},
                "fallback": {"show": False},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(
            question="What changed in table film?",
            table_names=["film"],
        )
        links_section = out["formattedResponse"].split("**Useful links**", 1)[1]
        assert "OvalEdge object redirect URL" in links_section
        assert "CompareSchema" not in links_section

    async def test_forwards_last_n_weeks(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "contextHeader": {},
                "rollup": {"totalChanges": 0},
                "fallback": {"show": False},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        await fn(last_n_weeks=3, connection_name="PROD")
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
            body={"connectionName": "PROD", "lastNWeeks": 3},
        )

    async def test_happy_path_timestamp_window_and_schema_filter(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "contextHeader": {
                    "catalogSchema": "sakila",
                    "schemaId": 1004,
                    "connection": "MySQL",
                },
                "rollup": {
                    "totalChanges": 2,
                    "tablesAdded": 1,
                    "columnsAdded": 5,
                },
                "columnChanges": [
                    {
                        "tableName": "film",
                        "columnName": "rating_code",
                        "changeType": "added",
                    }
                ],
                "analyzedFromTimestamp": "2026-07-01T00:00:00Z",
                "analyzedToTimestamp": "2026-07-08T00:00:00Z",
                "fallback": {"show": False},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(
            question="What columns were added recently?",
            connection_name="MySQL",
            schema_names=["sakila", "  ", "northwind"],
            from_timestamp="2026-07-01T00:00:00Z",
            to_timestamp="2026-07-08T00:00:00Z",
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
            body={
                "question": "What columns were added recently?",
                "connectionName": "MySQL",
                "schemaNames": ["sakila", "northwind"],
                "fromTimestamp": "2026-07-01T00:00:00Z",
                "toTimestamp": "2026-07-08T00:00:00Z",
            },
        )
        fr = out["formattedResponse"]
        assert "**Example columns added**" in fr
        assert "`film.rating_code`" in fr
        assert "period 2026-07-01T00:00:00Z → 2026-07-08T00:00:00Z" in fr
        assert out["requiredInfo"]["timestampOfAnalyzedCrawls"].startswith("2026-07-01")

    async def test_happy_path_equal_crawl_ids_allowed(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {"totalChanges": 0},
                "fallback": {"show": False},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(from_crawl_id=50, to_crawl_id=50)
        assert out["ok"] is True
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
            body={"fromCrawlId": 50, "toCrawlId": 50},
        )

    async def test_happy_path_fallback_when_deep_analysis_missing(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "CUSTOMER"},
                "rollup": {"totalChanges": 0},
                "fallback": {
                    "show": True,
                    "message": "Run Deep Analysis under Advance Tools, then ask again.",
                },
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(question="Show drift for CUSTOMER")
        assert "Run Deep Analysis" in out["formattedResponse"]
        assert out["data"]["fallback"]["show"] is True

    async def test_omits_blank_schema_and_table_filters(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "contextHeader": {},
                "rollup": {"totalChanges": 0},
                "fallback": {"show": False},
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        await fn(schema_names=["", "  "], table_names=None, last_n_days=1)
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
            body={"lastNDays": 1},
        )

    async def test_rejects_days_and_weeks_error_message(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(last_n_days=2, last_n_weeks=1, question="drift?")
        assert out["status_code"] == 400
        assert "last_n_days or last_n_weeks" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_rejects_inverted_crawl_range_error_message(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(from_crawl_id=20, to_crawl_id=10)
        assert out["status_code"] == 400
        assert "from_crawl_id must be <= to_crawl_id" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_unauthorized_returns_structured_dict(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(401, "Unauthorized")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(question="Show drift")
        assert out["status_code"] == 401
        assert "401" in out["error"]

    async def test_forbidden_returns_structured_dict(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(connection_name="PROD")
        assert out["status_code"] == 403
        assert "403" in out["error"]

    async def test_not_found_returns_structured_dict(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(404, "Schema not found")
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(schema_names=["missing_schema"])
        assert out["status_code"] == 404
        assert "404" in out["error"]

    async def test_non_dict_backend_payload_passes_through(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {"ok": True, "data": "not-a-dict"}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "metadata_changes_between_crawls")
        out = await fn(question="Show drift")
        assert out == {"ok": True, "data": "not-a-dict"}
        assert "formattedResponse" not in out


class TestMetadataChangesFormatter:
    def test_builds_compact_response_with_top_row_count_adds(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                # Bloated backend narrative must not replace the compact MCP format.
                "formattedResponse": (
                    "## Metadata changes — CUSTOMER\n\nBackend summary.\n"
                    + ("- col.x [modified]: detail\n" * 200)
                ),
                "contextHeader": {
                    "catalogSchema": "CUSTOMER",
                    "schemaId": 10,
                    "connection": "Snowflake PROD",
                },
                "rollup": {
                    "totalChanges": 369,
                    "tablesAdded": 33,
                    "tablesDeleted": 0,
                    "tablesModified": 26,
                    "columnsAdded": 0,
                    "columnsDeleted": 0,
                    "columnsModified": 310,
                    "schemasAdded": 0,
                    "schemasModified": 0,
                    "schemasRemoved": 0,
                    "rowCountChanges": 6,
                },
                "notableDeltas": [
                    {
                        "tableName": "oe_internal_diagnostics_delete_query",
                        "rowCountDelta": 81708,
                    },
                    {"tableName": "a_dqi_score", "rowCountDelta": 60616},
                    {"tableName": "oe_async_call_stats", "rowCountDelta": 36488},
                ],
                "compareSchemaUrl": (
                    "https://example.com#nav/comparedb?srchtab=history&id=5"
                ),
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(
            raw,
            include_links=True,
            header_title="What changed in CUSTOMER schema after the latest crawl?",
        )
        fr = out["data"]["formattedResponse"]
        assert "Backend summary." not in fr
        assert "**Top row-count adds**" in fr
        assert "`oe_internal_diagnostics_delete_query` (+81,708)" in fr
        assert "`a_dqi_score` (+60,616)" in fr
        assert "**Summary**" in fr
        assert "| Metric | Value |" in fr
        assert "**Useful links**" in fr
        assert out["formattedResponse"] == fr
        assert out["data"]["usefulLinks"]["compareSchemaUrl"].endswith("id=5")

    def test_caps_large_change_lists(self) -> None:
        from server.tools.catalog.formatters import (
            _MCP_COLUMN_CHANGE_LIST_CAP,
            _enhance_metadata_changes_response,
        )

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {"totalChanges": 100, "columnsModified": 100},
                "columnChanges": [
                    {"tableName": "t", "columnName": f"c{i}", "changeType": "modified"}
                    for i in range(_MCP_COLUMN_CHANGE_LIST_CAP + 25)
                ],
                "notableDeltas": [
                    {"tableName": "big", "rowCountDelta": 1000},
                ],
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(raw, include_links=False)
        assert len(out["data"]["columnChanges"]) == _MCP_COLUMN_CHANGE_LIST_CAP
        assert out["data"]["_columnChangesTruncated"] is True
        assert "**Top row-count adds**" in out["data"]["formattedResponse"]
        assert "`big` (+1,000)" in out["data"]["formattedResponse"]

    def test_shows_fallback_message_when_no_data(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {},
                "rollup": {"totalChanges": 0},
                "fallback": {
                    "show": True,
                    "message": "Run Deep Analysis under Advance Tools, then ask again.",
                },
            },
        }
        out = _enhance_metadata_changes_response(raw)
        assert "Run Deep Analysis" in out["data"]["formattedResponse"]

    def test_renders_property_previous_current_for_modified_columns(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "CUSTOMER"},
                "rollup": {
                    "totalChanges": 1,
                    "tablesAdded": 0,
                    "tablesDeleted": 0,
                    "tablesModified": 0,
                    "columnsAdded": 0,
                    "columnsDeleted": 0,
                    "columnsModified": 1,
                    "dataTypeChanges": 1,
                    "lengthChanges": 1,
                },
                "columnChanges": [
                    {
                        "tableName": "CUSTOMER_PROFILE",
                        "columnName": "status_code",
                        "changeType": "modified",
                        "previousDataType": "CHAR",
                        "currentDataType": "VARCHAR",
                        "previousLength": "20",
                        "currentLength": "30",
                    }
                ],
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(raw)
        fr = out["data"]["formattedResponse"]
        assert "**Datatype / length changes (modified columns)**" in fr
        assert "`CUSTOMER_PROFILE.status_code`" in fr
        assert "| Property | Previous | Current |" in fr
        assert "| Data Type | CHAR | VARCHAR |" in fr
        assert "| Length | 20 | 30 |" in fr

    def test_shows_named_column_examples_for_added_modified_deleted(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "CUSTOMER"},
                "rollup": {
                    "totalChanges": 3,
                    "columnsAdded": 2,
                    "columnsDeleted": 1,
                    "columnsModified": 1,
                },
                "columnChanges": [
                    {
                        "tableName": "ORDERS",
                        "columnName": "region_code",
                        "changeType": "added",
                    },
                    {
                        "tableName": "ORDERS",
                        "columnName": "legacy_flag",
                        "changeType": "deleted",
                    },
                    {
                        "tableName": "CUSTOMER_PROFILE",
                        "columnName": "status_code",
                        "changeType": "modified",
                        "previousDataType": "CHAR",
                        "currentDataType": "VARCHAR",
                    },
                    {
                        "tableName": "AUDIT",
                        "columnName": "id",
                        "changeType": "modified",
                        "detail": "Data Modified for the transaction",
                    },
                ],
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(
            raw, header_title="What columns were added, modified, or deleted?"
        )
        fr = out["data"]["formattedResponse"]
        assert "**Example columns added**" in fr
        assert "`ORDERS.region_code`" in fr
        assert "**Example columns deleted**" in fr
        assert "`ORDERS.legacy_flag`" in fr
        assert "**Example columns modified**" in fr
        assert "`CUSTOMER_PROFILE.status_code`" in fr
        # Prefer structural modifies over data-modified rows in the example list.
        assert "AUDIT.id" not in fr.split("**Example columns modified**", 1)[1].split(
            "**Useful links**", 1
        )[0]

    def test_added_question_falls_back_to_new_table_column_counts(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "ovaledgedb"},
                "rollup": {
                    "totalChanges": 10,
                    "tablesAdded": 2,
                    "columnsAdded": 95,
                    "columnsDeleted": 0,
                    "columnsModified": 0,
                },
                "columnChanges": [
                    {
                        "tableName": "audit_user_signin",
                        "columnName": "id",
                        "changeType": "modified",
                        "detail": "Data Modified for the transaction",
                    }
                ],
                "tableSummaries": [
                    {
                        "tableName": "a_filecolumn",
                        "changeType": "added",
                        "columnsAdded": 52,
                    },
                    {
                        "tableName": "tickettemplate",
                        "changeType": "added",
                        "columnsAdded": 43,
                    },
                ],
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(
            raw, header_title="What columns were added recently?"
        )
        fr = out["data"]["formattedResponse"]
        assert "**Example columns added**" in fr
        assert "`a_filecolumn` (+52 columns)" in fr
        assert "`tickettemplate` (+43 columns)" in fr
        # Added-focused question should not dump data-modified column noise.
        assert "Example columns with recent data changes" not in fr

    def test_prioritizes_added_columns_before_list_cap(self) -> None:
        from server.tools.catalog.formatters import (
            _MCP_COLUMN_CHANGE_LIST_CAP,
            _enhance_metadata_changes_response,
        )

        noisy = [
            {
                "tableName": "AUDIT",
                "columnName": f"c{i}",
                "changeType": "modified",
                "detail": "Data Modified for the transaction",
            }
            for i in range(_MCP_COLUMN_CHANGE_LIST_CAP + 5)
        ]
        noisy.append(
            {
                "tableName": "ORDERS",
                "columnName": "new_col",
                "changeType": "added",
            }
        )
        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {
                    "totalChanges": len(noisy),
                    "columnsAdded": 1,
                    "columnsModified": len(noisy) - 1,
                },
                "columnChanges": noisy,
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(
            raw, header_title="What columns were added?"
        )
        capped = out["data"]["columnChanges"]
        assert len(capped) == _MCP_COLUMN_CHANGE_LIST_CAP
        assert any(
            c.get("columnName") == "new_col" and c.get("changeType") == "added"
            for c in capped
        )
        assert "`ORDERS.new_col`" in out["data"]["formattedResponse"]

    def test_builds_nav_links_from_schema_id_when_backend_urls_absent(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {
                    "catalogSchema": "CUSTOMER",
                    "schemaId": 42,
                    "compareSchemaId": 7,
                },
                "redirectUrl": "https://oe.example/#nav/schema?id=42",
                "rollup": {"totalChanges": 1, "tablesModified": 1},
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(raw, include_links=True)
        links = out["data"]["usefulLinks"]
        assert links["compareSchemaUrl"].endswith(
            "#nav/comparedb?srchtab=history&id=7"
        )
        assert links["objectSchemaUrl"].endswith("#nav/schema?browse=summary&id=42")
        assert "dataandmetachanges?searchTab=datachanges" in links["dataChangeUrl"]
        assert (
            "dataandmetachanges?searchTab=metadatachanges/table"
            in links["metadataChangeUrl"]
        )
        assert "schemaname=42" in links["dataChangeUrl"]
        fr = out["data"]["formattedResponse"]
        assert "**Useful links**" in fr
        assert "CompareSchema" in fr

    def test_prefers_backend_urls_over_constructed_nav_links(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {
                    "catalogSchema": "CUSTOMER",
                    "schemaId": 42,
                    "compareSchemaId": 7,
                },
                "redirectUrl": "https://oe.example/#nav/schema?id=42",
                "compareSchemaUrl": "https://oe.example/#nav/comparedb?srchtab=history&id=99",
                "objectSchemaUrl": "https://oe.example/#nav/schema?browse=summary&id=88",
                "dataChangeUrl": "https://oe.example/#nav/dataandmetachanges?searchTab=datachanges",
                "metadataChangeUrl": (
                    "https://oe.example/#nav/dataandmetachanges"
                    "?searchTab=metadatachanges/table"
                ),
                "rollup": {"totalChanges": 1},
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(raw, include_links=True)
        links = out["data"]["usefulLinks"]
        assert links["compareSchemaUrl"].endswith("id=99")
        assert links["objectSchemaUrl"].endswith("id=88")
        assert links["dataChangeUrl"].endswith("searchTab=datachanges")
        assert links["metadataChangeUrl"].endswith("searchTab=metadatachanges/table")

    def test_deleted_question_falls_back_to_table_column_counts(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {
                    "totalChanges": 5,
                    "columnsDeleted": 12,
                    "columnsAdded": 0,
                    "columnsModified": 0,
                },
                "columnChanges": [],
                "tableSummaries": [
                    {
                        "tableName": "legacy_orders",
                        "changeType": "deleted",
                        "columnsDeleted": 8,
                    },
                    {
                        "tableName": "old_audit",
                        "changeType": "modified",
                        "columnsDeleted": 4,
                    },
                ],
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(
            raw, header_title="Which columns were deleted?"
        )
        fr = out["data"]["formattedResponse"]
        assert "**Example columns deleted**" in fr
        assert "`legacy_orders` (-8 columns)" in fr
        assert "`old_audit` (-4 columns)" in fr
        assert "Example columns added" not in fr

    def test_data_modified_only_uses_recent_data_changes_examples(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {
                    "totalChanges": 2,
                    "columnsModified": 2,
                    "columnsAdded": 0,
                    "columnsDeleted": 0,
                },
                "columnChanges": [
                    {
                        "tableName": "ORDERS",
                        "columnName": "amount",
                        "changeType": "modified",
                        "detail": "Data Modified for the transaction",
                    },
                    {
                        "tableName": "ORDERS",
                        "columnName": "status",
                        "changeType": "modified",
                        "detail": "Data Modified for the transaction",
                    },
                ],
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(
            raw, header_title="What columns were modified?"
        )
        fr = out["data"]["formattedResponse"]
        assert "**Example columns with recent data changes**" in fr
        assert "`ORDERS.amount`" in fr
        assert "`ORDERS.status`" in fr
        assert "**Example columns modified**" not in fr

    def test_question_intent_filters_example_buckets(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {
                    "totalChanges": 3,
                    "columnsAdded": 1,
                    "columnsDeleted": 1,
                    "columnsModified": 1,
                },
                "columnChanges": [
                    {
                        "tableName": "T",
                        "columnName": "a",
                        "changeType": "added",
                    },
                    {
                        "tableName": "T",
                        "columnName": "d",
                        "changeType": "deleted",
                    },
                    {
                        "tableName": "T",
                        "columnName": "m",
                        "changeType": "modified",
                        "previousDataType": "INT",
                        "currentDataType": "BIGINT",
                    },
                ],
                "fallback": {"show": False},
            },
        }
        deleted_only = _enhance_metadata_changes_response(
            raw, header_title="Which columns were deleted or dropped?"
        )["data"]["formattedResponse"]
        assert "**Example columns deleted**" in deleted_only
        assert "`T.d`" in deleted_only
        assert "Example columns added" not in deleted_only
        assert "Example columns modified" not in deleted_only

        modified_only = _enhance_metadata_changes_response(
            raw, header_title="Show datatype or length changes"
        )["data"]["formattedResponse"]
        assert "**Example columns modified**" in modified_only
        assert "`T.m`" in modified_only
        assert "Example columns added" not in modified_only
        assert "Example columns deleted" not in modified_only

    def test_caps_datatype_length_property_tables_with_remaining_note(self) -> None:
        from server.tools.catalog.formatters import (
            _MCP_PROPERTY_CHANGE_TABLE_CAP,
            _enhance_metadata_changes_response,
        )

        column_changes = [
            {
                "tableName": "T",
                "columnName": f"c{i}",
                "changeType": "modified",
                "previousDataType": "INT",
                "currentDataType": "BIGINT",
            }
            for i in range(_MCP_PROPERTY_CHANGE_TABLE_CAP + 3)
        ]
        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {
                    "totalChanges": len(column_changes),
                    "columnsModified": len(column_changes),
                    "dataTypeChanges": len(column_changes),
                },
                "columnChanges": column_changes,
                "fallback": {"show": False},
            },
        }
        fr = _enhance_metadata_changes_response(raw)["data"]["formattedResponse"]
        assert "**Datatype / length changes (modified columns)**" in fr
        assert "`T.c0`" in fr
        assert f"`T.c{_MCP_PROPERTY_CHANGE_TABLE_CAP - 1}`" in fr
        assert f"`T.c{_MCP_PROPERTY_CHANGE_TABLE_CAP}`" not in fr
        assert "_…and 3 more modified column(s) with type/length changes_" in fr

    def test_shows_no_changes_message_when_rollup_empty(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "EMPTY", "connection": "PROD"},
                "rollup": {"totalChanges": 0},
                "fallback": {"show": False},
            },
        }
        fr = _enhance_metadata_changes_response(raw)["data"]["formattedResponse"]
        assert "No structural or row-count changes were found for this scope." in fr
        assert "**Summary**" not in fr
        assert "connection PROD" in fr
        assert "schema EMPTY" in fr

    def test_top_row_count_adds_from_row_count_changes_ignores_negatives(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {"totalChanges": 2, "rowCountChanges": 2},
                "rowCountChanges": [
                    {"tableName": "grew", "rowCountDelta": 500},
                    {"tableName": "shrank", "rowCountDelta": -200},
                    {"tableName": "grew_more", "rowCountDelta": 900},
                ],
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(raw)
        fr = out["data"]["formattedResponse"]
        assert "**Top row-count adds**" in fr
        assert "`grew_more` (+900)" in fr
        assert "`grew` (+500)" in fr
        assert "shrank" not in fr
        top = out["data"]["topLargeRowCountAdds"]
        assert [d["tableName"] for d in top] == ["grew_more", "grew"]

    def test_caps_table_and_notable_delta_lists(self) -> None:
        from server.tools.catalog.formatters import (
            _MCP_NOTABLE_DELTA_LIST_CAP,
            _MCP_TABLE_CHANGE_LIST_CAP,
            _enhance_metadata_changes_response,
        )

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "rollup": {"totalChanges": 200, "tablesModified": 200},
                "tableChanges": [
                    {"tableName": f"t{i}", "changeType": "modified"}
                    for i in range(_MCP_TABLE_CHANGE_LIST_CAP + 10)
                ],
                "tableSummaries": [
                    {"tableName": f"s{i}", "changeType": "modified"}
                    for i in range(_MCP_TABLE_CHANGE_LIST_CAP + 5)
                ],
                "notableDeltas": [
                    {"tableName": f"d{i}", "rowCountDelta": i + 1}
                    for i in range(_MCP_NOTABLE_DELTA_LIST_CAP + 8)
                ],
                "fallback": {"show": False},
            },
        }
        data = _enhance_metadata_changes_response(raw)["data"]
        assert len(data["tableChanges"]) == _MCP_TABLE_CHANGE_LIST_CAP
        assert data["_tableChangesTruncated"] is True
        assert len(data["tableSummaries"]) == _MCP_TABLE_CHANGE_LIST_CAP
        assert data["_tableSummariesTruncated"] is True
        assert len(data["notableDeltas"]) == _MCP_NOTABLE_DELTA_LIST_CAP
        assert data["_notableDeltasTruncated"] is True

    def test_populates_required_info_and_mirrors_top_level_fields(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S"},
                "redirectUrl": "https://oe.example/#nav/schema?id=1",
                "crawlComparisonReference": "crawl-101-vs-102",
                "changeSummary": "Tables and columns drifted",
                "analyzedFromTimestamp": "2026-07-01T00:00:00Z",
                "analyzedToTimestamp": "2026-07-08T00:00:00Z",
                "rollup": {"totalChanges": 1, "tablesModified": 1},
                "fallback": {"show": False},
            },
        }
        out = _enhance_metadata_changes_response(raw)
        required = out["requiredInfo"]
        assert (
            required["ovaledgeObjectRedirectUrl"]
            == "https://oe.example/#nav/schema?id=1"
        )
        assert required["crawlComparisonReference"] == "crawl-101-vs-102"
        assert required["changeSummary"] == "Tables and columns drifted"
        assert (
            required["timestampOfAnalyzedCrawls"]
            == "2026-07-01T00:00:00Z -> 2026-07-08T00:00:00Z"
        )
        assert "Required info" in required["requiredInfoMarkdown"]
        assert out["data"]["requiredInfo"] == required
        assert out["summaryTableMarkdown"] == out["data"]["summaryTableMarkdown"]
        assert "period 2026-07-01T00:00:00Z → 2026-07-08T00:00:00Z" in out[
            "formattedResponse"
        ]

    def test_show_object_redirect_limits_useful_links_table(self) -> None:
        from server.tools.catalog.formatters import _enhance_metadata_changes_response

        raw = {
            "ok": True,
            "data": {
                "contextHeader": {"catalogSchema": "S", "schemaId": 10},
                "redirectUrl": "https://oe.example/#nav/table?id=55",
                "compareSchemaUrl": "https://oe.example/#nav/comparedb?id=5",
                "rollup": {"totalChanges": 1},
                "fallback": {"show": False},
            },
        }
        fr = _enhance_metadata_changes_response(
            raw, include_links=True, show_object_redirect=True
        )["data"]["formattedResponse"]
        assert "OvalEdge object redirect URL" in fr
        assert "Open object" in fr
        assert "CompareSchema" not in fr.split("**Useful links**", 1)[1]


class TestIsSpecificTableCompare:
    def test_true_when_table_names_provided(self) -> None:
        from server.tools.catalog.helpers import _is_specific_table_compare

        assert _is_specific_table_compare(None, ["CUSTOMER_PROFILE"]) is True

    def test_true_for_table_phrasing_in_question(self) -> None:
        from server.tools.catalog.helpers import _is_specific_table_compare

        assert _is_specific_table_compare("changes in table film", None) is True
        assert _is_specific_table_compare("what changed at actor", None) is True
        assert _is_specific_table_compare("deltas from rental table", None) is True

    def test_false_for_schema_level_question(self) -> None:
        from server.tools.catalog.helpers import _is_specific_table_compare

        assert (
            _is_specific_table_compare(
                "What changed in CUSTOMER schema after the latest crawl?",
                None,
            )
            is False
        )


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

    async def test_happy_path_alias_object_type_and_category(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {"status": "success", "updated": 1}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await invoke_write_confirmed(
            fn,
            targets=[{"object_id": 88, "object_type": "filecolumn"}],
            action="Yes",
            cde_category="PII",
            cde_justification="Contains customer email",
        )
        assert out["status"] == "success"
        body = mock_oe_client.post.call_args[0][1]
        assert body["targets"] == [{"objectId": 88, "objectType": "oefilecolumn"}]
        assert body["cdeCategory"] == "PII"
        assert body["cdeJustification"] == "Contains customer email"

    async def test_happy_path_action_none_clears_cde(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {"status": "success"}
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await invoke_write_confirmed(
            fn,
            targets=[{"object_id": 10, "object_type": "oetable"}],
            action="None",
        )
        assert out["status"] == "success"
        body = mock_oe_client.post.call_args[0][1]
        assert body["action"] == "None"
        assert "cdeCategory" not in body
        assert "cdeJustification" not in body

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

    async def test_rejects_empty_targets(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await fn(targets=[], action="Yes")
        assert out["status_code"] == 400
        assert "at least one" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_rejects_invalid_action(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await fn(
            targets=[{"object_id": 1, "object_type": "oetable"}],
            action="Maybe",
        )
        assert out["status_code"] == 400
        assert "action must be one of" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_rejects_missing_object_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await fn(
            targets=[{"object_type": "oetable"}],
            action="Yes",
        )
        assert out["status_code"] == 400
        assert "object_id and object_type" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_rejects_non_positive_object_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await fn(
            targets=[{"object_id": 0, "object_type": "oetable"}],
            action="Yes",
        )
        assert out["status_code"] == 400
        assert "positive integer" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_rejects_non_integer_object_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        out = await fn(
            targets=[{"object_id": "abc", "object_type": "oetable"}],
            action="Yes",
        )
        assert out["status_code"] == 400
        assert "integer" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_rejects_confirmation_token_mismatch(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        catalog.register(mcp)
        fn = await get_tool_fn(mcp, "update_cde_associations")
        preview = await fn(
            targets=[{"object_id": 10, "object_type": "oetable"}],
            action="Yes",
        )
        assert preview["workflowPhase"] == "confirm_update"
        out = await fn(
            targets=[{"object_id": 10, "object_type": "oetable"}],
            action="Yes",
            write_confirmed_by_user=True,
            confirmation_token="not-the-real-token",
        )
        assert out.get("error_code") == "confirmation_token_mismatch"
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
