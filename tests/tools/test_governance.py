from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_DOMAIN_METADATA_SIZE_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_PATH_CUSTOM_FIELDS,
    MCP_PATH_DOMAIN_METADATA,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_LOOKUP_DQ_RULES,
    MCP_PATH_TAGS,
    MCP_PATH_TAGS_CREATE_OPTIONS,
    MCP_PATH_TAGS_PARENT_OPTIONS,
    MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES,
    MCP_PATH_UPDATE_GOVERNANCE_ROLES,
)
from server.tools import dataquality, governance
from server.tools.governance import helpers as governance_helpers
from tests.conftest import MOCK_GLOSSARY_RESULT
from tests.helpers import get_tool_fn


class TestLookupGlossaryTerm:
    async def test_term_name_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_GLOSSARY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(term_name="churn")
        assert out == MOCK_GLOSSARY_RESULT
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_GLOSSARY_TERMS,
            params={"termName": "churn", "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT},
        )

    async def test_rejects_both_id_and_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(object_id=1, term_name="x")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_object_id_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_GLOSSARY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(object_id=99)
        assert out == MOCK_GLOSSARY_RESULT
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_GLOSSARY_TERMS,
            params={"objectId": 99, "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT},
        )

    async def test_custom_limit_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_GLOSSARY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        await fn(term_name="x", limit=5)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_GLOSSARY_TERMS,
            params={"termName": "x", "limit": 5},
        )

    async def test_limit_capped_at_max(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_GLOSSARY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        await fn(term_name="x", limit=999)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_GLOSSARY_TERMS,
            params={"termName": "x", "limit": MCP_GLOSSARY_TAGS_LIMIT_MAX},
        )

    async def test_rejects_neither_id_nor_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn()
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_placement_by_domain_name(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_GLOSSARY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(domain_name="PrakashDOmain", category_name="test")
        assert out == MOCK_GLOSSARY_RESULT
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_GLOSSARY_TERMS,
            params={
                "domainName": "PrakashDOmain",
                "categoryName": "test",
                "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
            },
        )

    async def test_rejects_mixed_name_and_placement(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(term_name="x", domain_name="Finance")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_whitespace_term_name_treated_as_missing(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(term_name="   ")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(term_name="revenue")
        assert out["status_code"] == 403

    async def test_enriches_absolute_nav_url_from_relative_nav_link(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": [
                {
                    "objectId": 2468,
                    "objectName": "Sidheshwar",
                    "navLink": "#nav/glossary?browse=summary&id=2468",
                }
            ],
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(term_name="Sidheshwar")
        hit = out["data"][0]
        assert hit["navLink"] == "#nav/glossary?browse=summary&id=2468"
        assert hit["redirectUrl"].startswith("https://mock.ovaledge.com/")
        assert hit["redirectUrl"].endswith("#nav/glossary?browse=summary&id=2468")
        assert "navUrl" not in hit

    async def test_object_id_lookup_enriches_nav_in_data(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "objectId": 99,
                "objectName": "Revenue",
                "navLink": "#nav/glossary?browse=summary&id=99",
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_glossary_term")
        out = await fn(object_id=99)
        assert out["data"]["redirectUrl"].endswith("#nav/glossary?browse=summary&id=99")
        assert "redirectUrl" not in out
        assert "navUrl" not in out["data"]


_MOCK_DOMAIN_PICKER = {
    "ok": True,
    "data": {
        "domains": [
            {
                "globaldomainid": 12,
                "domain": "Finance",
                "isCategory": True,
                "isSubCategory": False,
                "isTerm": False,
            }
        ]
    },
}


class TestCreateGlossaryTerm:
    async def test_picker_domains(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = _MOCK_DOMAIN_PICKER
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(search_on="oeglobaldomain")
        assert "formattedPlacementOptions" in out
        assert "formattedResponse" in out
        assert out["awaitingUserSelection"] is True
        assert out["workflowPhase"] == "select_domain"
        assert "Finance" in out["formattedResponse"]
        assert out.get("nextStep")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "oeglobaldomain",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 0,
                "categoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_term_name_without_domain_shows_domain_picker(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _MOCK_DOMAIN_PICKER
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="TeamTest")
        assert out["workflowPhase"] == "select_domain"
        assert out["pendingTermName"] == "TeamTest"
        assert "TeamTest" in out["formattedResponse"]
        assert "domain" in out["formattedResponse"].lower()
        mock_oe_client.get.assert_called_once()
        mock_oe_client.post.assert_not_called()

    async def test_term_name_with_domain_name_resolves_and_skips_domain_picker(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.side_effect = [
            {
                "ok": True,
                "data": {
                    "domains": [
                        {"globaldomainid": 12, "domain": "prakashDomain"},
                        {"globaldomainid": 13, "domain": "otherDomain"},
                    ]
                },
            },
            {
                "ok": True,
                "data": {"Category": [{"categoryId": 55, "categoryName": "cost"}]},
            },
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="Mahabharata", domain_name="prakashDomain")
        assert out["workflowPhase"] == "select_category"
        assert out["pendingDomainId"] == 12
        assert out["pendingDomainName"] == "prakashDomain"
        assert out["selectionField"] == "category_id"
        assert mock_oe_client.get.call_count == 2
        first_call = mock_oe_client.get.call_args_list[0]
        assert first_call.args[0] == MCP_PATH_DOMAIN_METADATA
        assert first_call.kwargs["params"]["searchOn"] == "oeglobaldomain"
        second_call = mock_oe_client.get.call_args_list[1]
        assert second_call.args[0] == MCP_PATH_DOMAIN_METADATA
        assert second_call.kwargs["params"]["searchOn"] == "category"
        assert second_call.kwargs["params"]["domainId"] == 12
        mock_oe_client.post.assert_not_called()

    async def test_term_name_with_domain_name_normalized_match(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.side_effect = [
            {
                "ok": True,
                "data": {
                    "domains": [
                        {"globaldomainid": 12, "domain": "Prakash Domain"},
                        {"globaldomainid": 13, "domain": "otherDomain"},
                    ]
                },
            },
            {
                "ok": True,
                "data": {"Category": [{"categoryId": 55, "categoryName": "cost"}]},
            },
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="Mahabharata", domain_name="prakashDomain")
        assert out["workflowPhase"] == "select_category"
        assert out["pendingDomainId"] == 12
        assert out["pendingDomainName"] == "Prakash Domain"
        assert mock_oe_client.get.call_count == 2
        mock_oe_client.post.assert_not_called()

    async def test_term_name_with_unknown_domain_name_returns_domain_picker(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"domains": [{"globaldomainid": 12, "domain": "Finance"}]},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="Mahabharata", domain_name="prakashDomain")
        assert out["workflowPhase"] == "select_domain"
        assert out["domainNameMatch"] == "not_found"
        assert out["requestedDomainName"] == "prakashDomain"
        mock_oe_client.get.assert_called_once()
        mock_oe_client.post.assert_not_called()

    async def test_picker_category_without_domain_id(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(search_on="category")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_picker_subcategory(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"SubCategory": [{"subCategoryId": 88, "subCategoryName": "money"}]},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        await fn(search_on="subcategory", category_id=55)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "subcategory",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 0,
                "categoryId": 55,
                "subCategoryId": 0,
            },
        )

    async def test_confirm_preview_blocks_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="TermX",
            domain_id=12,
            description="Business definition from the user.",
            skip_category=True,
            category_skip_confirmed=True,
        )
        assert out["workflowPhase"] == "confirm_create"
        assert out.get("doNotCreate") is True
        assert out.get("createConfirmedByUser") is False
        mock_oe_client.post.assert_not_called()

    async def test_create_happy_path(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "businessGlossaryId": 1001,
                "termName": "Revenue Recognition",
                "status": "DRAFT",
                "domainId": 12,
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        preview = await fn(
            term_name="Revenue Recognition",
            domain_id=12,
            description="ASC 606 revenue recognition policy.",
            category_id=55,
            subcategory_id=88,
            domain_name="Finance",
            category_name="cost",
            subcategory_name="money",
        )
        assert preview["workflowPhase"] == "confirm_create"
        assert preview.get("doNotCreate") is True
        mock_oe_client.post.assert_not_called()
        out = await fn(
            term_name="Revenue Recognition",
            domain_id=12,
            description="ASC 606 revenue recognition policy.",
            category_id=55,
            subcategory_id=88,
            domain_name="Finance",
            category_name="cost",
            subcategory_name="money",
            create_confirmed_by_user=True,
        )
        assert out["placementPath"] == "Finance > cost > money > Revenue Recognition"
        assert "navUrl" in out
        assert "redirectUrl" in out
        assert out["redirectUrl"] == out["navUrl"]
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_GLOSSARY_TERMS,
            body={
                "termName": "Revenue Recognition",
                "domainId": 12,
                "description": "ASC 606 revenue recognition policy.",
                "category1Id": 55,
                "category2Id": 88,
                "publish": False,
            },
        )
        mock_oe_client.get.assert_not_called()

    async def test_create_uses_nav_link_as_redirect(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "businessGlossaryId": 2463,
                "termName": "joyful",
                "status": "DRAFT",
                "domainId": 1066,
                "navLink": "#nav/glossary?browse=summary&id=2463",
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="joyful",
            domain_id=1066,
            description="joyful description",
            skip_category=True,
            category_skip_confirmed=True,
            create_confirmed_by_user=True,
        )
        assert out["navLink"] == "#nav/glossary?browse=summary&id=2463"
        assert out["redirectUrl"].endswith("#nav/glossary?browse=summary&id=2463")
        assert out["data"]["navLink"] == "#nav/glossary?browse=summary&id=2463"
        assert out["data"]["redirectUrl"].endswith("#nav/glossary?browse=summary&id=2463")
        assert "Redirect" in out["formattedResponse"]

    async def test_domain_id_without_description_shows_category_picker(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "Category": [
                    {"categoryId": 55, "categoryName": "cost"},
                    {"categoryId": 56, "categoryName": "finance"},
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="X", domain_id=12, domain_name="Finance")
        assert out["workflowPhase"] == "select_category"
        assert out["awaitingUserSelection"] is True
        assert "skip" in out["formattedResponse"].lower()
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "category",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 12,
                "categoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_single_category_still_shows_category_picker_until_user_confirms(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"Category": [{"categoryId": 55, "categoryName": "test"}]},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="X", domain_id=12, domain_name="Finance")
        assert out["workflowPhase"] == "select_category"
        assert out["selectionField"] == "category_id"
        assert "test" in out["formattedResponse"]
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "category",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 12,
                "categoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_domain_without_categories_shows_explicit_no_category_message(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"Category": []},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="X", domain_id=12, domain_name="Finance")
        assert out["workflowPhase"] == "collect_description"
        assert "No categories are available under the selected domain" in out["formattedResponse"]
        assert out["hasCategoriesInDomain"] is False
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "category",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 12,
                "categoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_skip_category_without_confirmed_shows_category_picker(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"Category": [{"categoryId": 55, "categoryName": "cost"}]},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="X", domain_id=12, skip_category=True)
        assert out["workflowPhase"] == "select_category"
        assert out["awaitingUserSelection"] is True
        mock_oe_client.get.assert_called_once()
        mock_oe_client.post.assert_not_called()

    async def test_skip_category_confirmed_missing_description_collects_description(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"Category": [{"categoryId": 55, "categoryName": "cost"}]},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="X",
            domain_id=12,
            skip_category=True,
            category_skip_confirmed=True,
        )
        assert out["status_code"] == 400
        assert out["workflowPhase"] == "collect_description"
        assert "description" in out["formattedResponse"].lower()
        assert out["hasCategoriesInDomain"] is True
        assert out["categoryAvailabilityMessage"] == (
            "Categories are available under the selected domain."
        )
        assert "cost" in out["formattedResponse"]
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "category",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 12,
                "categoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_skip_category_confirmed_with_no_categories_shows_no_category_message(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"Category": []},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="X",
            domain_id=12,
            skip_category=True,
            category_skip_confirmed=True,
        )
        assert out["workflowPhase"] == "collect_description"
        assert "No categories are available under the selected domain" in out["formattedResponse"]
        assert out["hasCategoriesInDomain"] is False
        assert out["categoryAvailabilityMessage"] == (
            "No categories are available under the selected domain."
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "category",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 12,
                "categoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_category_with_subcategories_shows_subcategory_picker(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {"SubCategory": [{"subCategoryId": 88, "subCategoryName": "money"}]},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="X",
            domain_id=12,
            category_id=55,
            category_name="cost",
        )
        assert out["workflowPhase"] == "select_subcategory"
        assert "money" in out["formattedResponse"]
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "subcategory",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 12,
                "categoryId": 55,
                "subCategoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_domain_and_category_name_skip_category_picker_and_show_subcategory(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.side_effect = [
            {
                "ok": True,
                "data": {"Category": [{"categoryId": 1068, "categoryName": "test"}]},
            },
            {
                "ok": True,
                "data": {"SubCategory": [{"subCategoryId": 88, "subCategoryName": "money"}]},
            },
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="Java", domain_id=1066, category_name="test")
        assert out["workflowPhase"] == "select_subcategory"
        assert out["pendingCategoryId"] == 1068
        assert "money" in out["formattedResponse"]
        assert mock_oe_client.get.call_count == 2
        first_call = mock_oe_client.get.call_args_list[0]
        assert first_call.args[0] == MCP_PATH_DOMAIN_METADATA
        assert first_call.kwargs["params"]["searchOn"] == "category"
        assert first_call.kwargs["params"]["domainId"] == 1066
        second_call = mock_oe_client.get.call_args_list[1]
        assert second_call.args[0] == MCP_PATH_DOMAIN_METADATA
        assert second_call.kwargs["params"]["searchOn"] == "subcategory"
        assert second_call.kwargs["params"]["categoryId"] == 1068
        mock_oe_client.post.assert_not_called()

    async def test_domain_category_path_in_domain_name_skips_category_picker(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.side_effect = [
            {
                "ok": True,
                "data": {"domains": [{"globaldomainid": 1066, "domain": "PrakashDomain"}]},
            },
            {
                "ok": True,
                "data": {"Category": [{"categoryId": 1068, "categoryName": "test"}]},
            },
            {
                "ok": True,
                "data": {"SubCategory": [{"subCategoryId": 88, "subCategoryName": "money"}]},
            },
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="Java", domain_name="PrakashDomain>test")
        assert out["workflowPhase"] == "select_subcategory"
        assert out["pendingDomainId"] == 1066
        assert out["pendingCategoryId"] == 1068
        assert out["pendingDomainName"] == "PrakashDomain"
        assert mock_oe_client.get.call_count == 3
        first_call = mock_oe_client.get.call_args_list[0]
        assert first_call.kwargs["params"]["searchOn"] == "oeglobaldomain"
        second_call = mock_oe_client.get.call_args_list[1]
        assert second_call.kwargs["params"]["searchOn"] == "category"
        assert second_call.kwargs["params"]["domainId"] == 1066
        third_call = mock_oe_client.get.call_args_list[2]
        assert third_call.kwargs["params"]["searchOn"] == "subcategory"
        assert third_call.kwargs["params"]["categoryId"] == 1068
        mock_oe_client.post.assert_not_called()

    async def test_domain_category_subcategory_path_resolves_all_and_collects_description(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.side_effect = [
            {
                "ok": True,
                "data": {"domains": [{"globaldomainid": 1066, "domain": "PrakashDomain"}]},
            },
            {
                "ok": True,
                "data": {"Category": [{"categoryId": 1068, "categoryName": "test"}]},
            },
            {
                "ok": True,
                "data": {
                    "SubCategory": [
                        {"subCategoryId": 777, "subCategoryName": "payments"}
                    ]
                },
            },
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(term_name="Java", domain_name="PrakashDomain>test>payments")
        assert out["workflowPhase"] == "collect_description"
        assert out["pendingDomainId"] == 1066
        assert out["pendingCategoryId"] == 1068
        assert out["pendingSubcategoryId"] == 777
        assert "Placement **PrakashDomain > test > payments** is set." in out["formattedResponse"]
        assert mock_oe_client.get.call_count == 3
        mock_oe_client.post.assert_not_called()

    async def test_skip_subcategory_missing_description_collects_description(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "SubCategory": [
                    {"subCategoryId": 88, "subCategoryName": "money"}
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="X",
            domain_id=12,
            category_id=55,
            skip_subcategory=True,
        )
        assert out["workflowPhase"] == "select_subcategory"
        assert "money" in out["formattedResponse"]
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "subcategory",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 12,
                "categoryId": 55,
                "subCategoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_skip_subcategory_confirmed_missing_description_collects_description(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "SubCategory": [
                    {"subCategoryId": 88, "subCategoryName": "money"}
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="X",
            domain_id=12,
            category_id=55,
            skip_subcategory=True,
            subcategory_skip_confirmed=True,
        )
        assert out["workflowPhase"] == "collect_description"
        assert "money" in out["formattedResponse"]
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_DOMAIN_METADATA,
            params={
                "searchOn": "subcategory",
                "page": 0,
                "size": MCP_DOMAIN_METADATA_SIZE_DEFAULT,
                "domainId": 12,
                "categoryId": 55,
                "subCategoryId": 0,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_create_with_search_on_and_term_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(search_on="oeglobaldomain", term_name="X")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()
        mock_oe_client.post.assert_not_called()

    async def test_create_subcategory_without_category(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="X",
            domain_id=12,
            description="desc",
            subcategory_id=88,
        )
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(409, "Duplicate term")
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_glossary_term")
        out = await fn(
            term_name="X",
            domain_id=12,
            description="desc",
            skip_category=True,
            category_skip_confirmed=True,
            create_confirmed_by_user=True,
        )
        assert out["status_code"] == 409


class TestLookupTags:
    async def test_object_id_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"tag": "t"}
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        await fn(object_id=3)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_TAGS,
            params={"objectId": 3, "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT},
        )

    async def test_custom_limit_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"tag": "t"}
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        await fn(tag_name="PII", limit=7)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_TAGS,
            params={"tagName": "PII", "limit": 7},
        )

    async def test_rejects_both_id_and_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn(object_id=1, tag_name="PII")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_neither_id_nor_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn()
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(404, "Not found")
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn(tag_name="missing")
        assert out["status_code"] == 404

    async def test_enriches_absolute_nav_url_from_relative_nav_link(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": [
                {
                    "objectId": 1519,
                    "objectName": "deepList",
                    "navLink": "#nav/tag?id=1519&objectType=oetag&masterTagId=1036",
                    "parentObjectId": 1036,
                }
            ],
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn(tag_name="deepList")
        hit = out["data"][0]
        assert hit["navLink"] == "#nav/tag?id=1519&objectType=oetag&masterTagId=1036"
        assert hit["redirectUrl"].startswith("https://mock.ovaledge.com/")
        assert hit["redirectUrl"].endswith(
            "#nav/tag?id=1519&objectType=oetag&masterTagId=1036"
        )
        assert "redirectUrl" not in out

    async def test_object_id_lookup_enriches_nav_in_data(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "objectId": 99,
                "objectName": "Confidential",
                "navLink": "#nav/tag?id=99&objectType=oetag&masterTagId=10",
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn(object_id=99)
        assert out["data"]["redirectUrl"].endswith(
            "#nav/tag?id=99&objectType=oetag&masterTagId=10"
        )
        assert "redirectUrl" not in out

    async def test_include_children_forwards_param(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"objectId": 1}}
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        await fn(tag_name="Parent", include_children=True)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_TAGS,
            params={
                "tagName": "Parent",
                "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
                "includeChildren": True,
            },
        )

    async def test_include_parent_forwards_param(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"objectId": 2}}
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        await fn(object_id=2, include_parent=True)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_TAGS,
            params={"objectId": 2, "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT, "includeParent": True},
        )

    async def test_hierarchy_enriches_formatted_response(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "objectId": 100,
                "objectName": "ParentTag",
                "navLink": "#nav/tag?id=100&objectType=oetag&masterTagId=1",
                "childTags": [
                    {
                        "objectId": 101,
                        "objectName": "ChildA",
                        "navLink": "#nav/tag?id=101&objectType=oetag&masterTagId=1",
                        "hasChildren": False,
                    }
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn(tag_name="ParentTag", include_children=True)
        assert "formattedResponse" in out
        assert "Child tags (1)" in out["formattedResponse"]
        assert "ChildA" in out["formattedResponse"]
        child = out["data"]["childTags"][0]
        assert child["redirectUrl"].startswith("https://mock.ovaledge.com/")

    async def test_parent_tag_enriched_in_response(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "objectId": 201,
                "objectName": "ChildTag",
                "navLink": "#nav/tag?id=201&objectType=oetag&masterTagId=1",
                "parentTag": {
                    "objectId": 100,
                    "objectName": "ParentTag",
                    "navLink": "#nav/tag?id=100&objectType=oetag&masterTagId=1",
                },
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_tags")
        out = await fn(object_id=201, include_parent=True)
        assert "Parent tag:" in out["formattedResponse"]
        assert out["data"]["parentTag"]["redirectUrl"].startswith("https://mock.ovaledge.com/")


class TestBuildUserSelectableMasters:
    def test_lists_all_masters_without_parent_truncation(self) -> None:
        choices = [
            {"masterTagId": 3, "tagName": "Zebra"},
            {"masterTagId": 1, "tagName": "Alpha"},
            {
                "masterTagId": 2,
                "tagName": "Beta",
                "parentTagChoices": [{"parentTagId": 99, "tagName": "child"}],
            },
        ]
        masters = governance_helpers._build_user_selectable_masters(choices)
        assert len(masters) == 3
        assert [m["masterTagId"] for m in masters] == [1, 2, 3]
        text = governance_helpers._format_master_list_for_user(masters)
        assert "3 accessible" in text
        assert "parentTagId=99" not in text


@pytest.fixture(autouse=True)
def _clear_parent_picker_pending() -> None:
    governance_helpers._pending_parent_picker_expiry.clear()
    yield
    governance_helpers._pending_parent_picker_expiry.clear()


class TestCreateTag:
    async def test_forwards_create_body(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"tagId": 99, "tagName": "Confidential"},
        }
        secure_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "masterTagChoices": [{"masterTagId": 10, "tagName": "Governance"}],
            },
        }
        parent_opts = {
            "ok": True,
            "data": {
                "masterTagId": 10,
                "parentTagChoices": [{"parentTagId": 20, "tagName": "Child"}],
            },
        }
        tag_lookup = {
            "ok": True,
            "data": {
                "objectId": 99,
                "objectName": "Confidential",
                "navLink": "#nav/tag?id=99&objectType=oetag&masterTagId=10",
                "fullQualifiedName": "Governance > Confidential",
            },
        }
        secure_gets = [
            secure_opts,
            secure_opts,
            parent_opts,
            secure_opts,
            secure_opts,
            parent_opts,
            parent_opts,
        ]
        mock_oe_client.get.side_effect = [
            *secure_gets,
            *secure_gets,
            tag_lookup,
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        parent_step = await fn(
            tag_name="Confidential",
            description="<p>secret</p>",
            master_tag_id=10,
            master_tag_id_confirmed_by_user=True,
        )
        assert parent_step.get("selectionPhase") == "PARENT_OPTIONAL"
        confirm = await fn(
            tag_name="Confidential",
            description="<p>secret</p>",
            master_tag_id=10,
            master_tag_id_confirmed_by_user=True,
            parent_tag_id=20,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
        )
        assert confirm["workflowPhase"] == "confirm_create"
        mock_oe_client.post.assert_not_called()
        out = await fn(
            tag_name="Confidential",
            description="<p>secret</p>",
            master_tag_id=10,
            master_tag_id_confirmed_by_user=True,
            parent_tag_id=20,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
            create_confirmed_by_user=True,
        )
        assert out["ok"] is True
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_TAGS,
            body={
                "tagName": "Confidential",
                "description": "<p>secret</p>",
                "masterTagId": 10,
                "parentTagId": 20,
            },
        )
        assert mock_oe_client.get.call_args_list[0].args == (MCP_PATH_TAGS_CREATE_OPTIONS,)
        mock_oe_client.get.assert_any_call(
            MCP_PATH_TAGS,
            params={"objectId": 99, "limit": 1},
        )
        assert out["data"]["redirectUrl"].endswith("#nav/tag?id=99")
        assert out["data"]["navLink"].endswith(
            "#nav/tag?id=99&objectType=oetag&masterTagId=10"
        )
        assert out["data"]["summaryPageUrl"].endswith(
            "#nav/tag?id=99&objectType=oetag&masterTagId=10"
        )
        assert out["data"]["tagSummary"]["tagId"] == 99
        assert out["auditReference"]["store"] == "a_tag"
        assert out["auditReference"]["action"] == "ADD"
        assert out["auditReference"]["redirectUrl"].endswith(
            "#nav/audittrail?activeTab=audittagtermdomain/audittag"
        )
        assert out["backendCreatePayload"]["tagId"] == 99
        assert out["backend"]["create"]["data"]["tagId"] == 99
        assert "[Tag summary]" in out["formattedResponse"]
        assert "[Redirect URL]" in out["formattedResponse"]
        assert "[Audit reference]" in out["formattedResponse"]
        assert "Confidential" in out["formattedResponse"]
        assert out["links"]["redirect"]["label"] == "Redirect URL"

    async def test_open_root_uses_mastertag_summary_url(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"tagId": 77, "tagName": "Ranchi", "tagSecurityMode": "open"},
        }
        open_create_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "open",
                "parentTagChoices": [{"parentTagId": 1, "tagName": "Root"}],
            },
        }
        ranchi_gets = [
            {"ok": True, "data": {"tagSecurityMode": "open"}},
            open_create_opts,
            {"ok": True, "data": {"tagSecurityMode": "open"}},
        ]
        mock_oe_client.get.side_effect = [
            *ranchi_gets,
            *ranchi_gets,
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.0")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        step1 = await fn(tag_name="Ranchi")
        assert step1.get("selectionPhase") == "PARENT_OPTIONAL"
        await fn(
            tag_name="Ranchi",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        out = await fn(
            tag_name="Ranchi",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
            create_confirmed_by_user=True,
        )
        assert out["ok"] is True
        assert out["navLink"].endswith(
            "#nav/tag?id=77&objectType=mastertag&masterTagId=77"
        )
        assert out["redirectUrl"].endswith("#nav/tag?id=77")
        assert "[Tag summary]" in out["formattedResponse"]

    async def test_fallback_nav_when_lookup_missing(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"tagId": 5, "tagName": "PII"},
        }
        open_opts = {"ok": True, "data": {"tagSecurityMode": "open", "parentTagChoices": []}}

        async def open_get(path: str, **kwargs: object) -> dict[str, object]:
            if path == MCP_PATH_TAGS:
                raise OvalEdgeError(404, "Not found")
            return open_opts

        mock_oe_client.get.side_effect = open_get
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="PII")
        await fn(
            tag_name="PII",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        out = await fn(
            tag_name="PII",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
            create_confirmed_by_user=True,
        )
        assert out["ok"] is True
        assert "#nav/tag?id=5" in out["data"]["navLink"]
        assert out.get("catalogLookupNote")

    async def test_rejects_empty_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(tag_name="   ")
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_create_api_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(400, "Cannot add")
        open_opts = {"ok": True, "data": {"tagSecurityMode": "open", "parentTagChoices": []}}
        mock_oe_client.get.side_effect = [
            open_opts,
            open_opts,
            open_opts,
            open_opts,
            open_opts,
            open_opts,
            open_opts,
            open_opts,
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="x")
        await fn(
            tag_name="x",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        out = await fn(
            tag_name="x",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
            create_confirmed_by_user=True,
        )
        assert out["status_code"] == 400

    async def test_secure_mode_returns_choices_without_post(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "status": "INPUT_REQUIRED",
                "requiredFields": ["masterTagId"],
                "masterTagChoices": [
                    {
                        "masterTagId": 12,
                        "tagName": "Finance",
                        "parentTagChoices": [
                            {"parentTagId": 101, "tagName": "Cost Center"},
                        ],
                    },
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(tag_name="NewTag")
        assert out["ok"] is False
        assert out["status_code"] == 422
        assert out.get("awaitingUserSelection") is True
        assert out.get("doNotCreateTag") is True
        assert out["masterTagChoiceCount"] == 1
        assert len(out["userSelectableMasters"]) == 1
        assert out["userSelectableMasters"][0]["masterTagId"] == 12
        assert out["masterTagChoices"][0]["masterTagId"] == 12
        assert "masterTagId=12" in out["formattedResponse"]
        assert out.get("selectionPhase") == "MASTER_REQUIRED"
        assert "userSelectableParents" not in out
        assert "list is complete" in out["formattedResponse"]
        mock_oe_client.post.assert_not_called()

    async def test_secure_mode_rejects_parent_not_under_master(
        self, mock_oe_client: AsyncMock
    ) -> None:
        """Parent allow-list comes from parent-options, not empty nested masterTagChoices."""
        secure_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "masterTagChoices": [
                    {
                        "masterTagId": 1013,
                        "tagName": "Personal Finance",
                        "parentTagChoices": [],
                    },
                ],
            },
        }
        parent_opts = {
            "ok": True,
            "data": {
                "masterTagId": 1013,
                "parentTagChoices": [
                    {"parentTagId": 1019, "tagName": "Tax Planning"},
                ],
            },
        }
        mock_oe_client.get.side_effect = [
            secure_opts,
            secure_opts,
            parent_opts,
            secure_opts,
            secure_opts,
            parent_opts,
            parent_opts,
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(
            tag_name="BadChild",
            master_tag_id=1013,
            master_tag_id_confirmed_by_user=True,
        )
        out = await fn(
            tag_name="BadChild",
            master_tag_id=1013,
            master_tag_id_confirmed_by_user=True,
            parent_tag_id=1033,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
        )
        assert out["ok"] is False
        assert "1033" in out.get("message", "")
        assert "1013" in out.get("message", "")
        assert "browse_parent_tag_id" in out.get("formattedResponse", "")
        mock_oe_client.post.assert_not_called()

    async def test_secure_mode_nested_parent_via_browse(self, mock_oe_client: AsyncMock) -> None:
        """Grandchild parent (e.g. MCPNEWcreated) is allowed after BFS parent-options browse."""
        secure_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "masterTagChoices": [
                    {"masterTagId": 1036, "tagName": "Deposit Accounts"},
                ],
            },
        }
        top_parent_opts = {
            "ok": True,
            "data": {
                "masterTagId": 1036,
                "masterTagName": "Deposit Accounts",
                "parentTagChoices": [
                    {
                        "parentTagId": 1774,
                        "tagName": "MCPCreated",
                        "hasChildren": True,
                    },
                ],
            },
        }
        nested_parent_opts = {
            "ok": True,
            "data": {
                "masterTagId": 1036,
                "browseParentTagId": 1774,
                "browseParentTagName": "MCPCreated",
                "parentTagChoices": [
                    {"parentTagId": 1776, "tagName": "MCPNEWcreated"},
                ],
            },
        }
        async def _parent_options_router(*_args: object, **kwargs: object) -> dict[str, object]:
            params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
            if params.get("browseParentTagId"):
                return nested_parent_opts
            if params.get("masterTagId"):
                return top_parent_opts
            return secure_opts

        mock_oe_client.get.side_effect = _parent_options_router
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(
            tag_name="deep tag created",
            master_tag_id=1036,
            master_tag_id_confirmed_by_user=True,
        )
        out = await fn(
            tag_name="deep tag created",
            master_tag_id=1036,
            master_tag_id_confirmed_by_user=True,
            parent_tag_id=1776,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
        )
        assert out.get("doNotCreateTag") is True
        assert out.get("workflowPhase") == "confirm_create"
        mock_oe_client.post.assert_not_called()
        mock_oe_client.get.assert_any_call(
            MCP_PATH_TAGS_PARENT_OPTIONS,
            params={"masterTagId": 1036, "browseParentTagId": 1774},
        )

    async def test_secure_mode_browse_parent_shows_children(
        self, mock_oe_client: AsyncMock
    ) -> None:
        secure_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "masterTagChoices": [
                    {"masterTagId": 1036, "tagName": "Deposit Accounts"},
                ],
            },
        }
        nested_parent_opts = {
            "ok": True,
            "data": {
                "masterTagId": 1036,
                "browseParentTagId": 1774,
                "browseParentTagName": "MCPCreated",
                "parentTagChoices": [
                    {"parentTagId": 1776, "tagName": "MCPNEWcreated"},
                ],
            },
        }
        mock_oe_client.get.side_effect = [
            secure_opts,
            secure_opts,
            nested_parent_opts,
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(
            tag_name="deep tag created",
            master_tag_id=1036,
            master_tag_id_confirmed_by_user=True,
            browse_parent_tag_id=1774,
        )
        assert out.get("doNotCreateTag") is True
        assert out.get("browseParentTagId") == 1774
        assert out["parentTagChoiceCount"] == 1
        assert "MCPNEWcreated" in str(out.get("userSelectableParents"))
        mock_oe_client.get.assert_any_call(
            MCP_PATH_TAGS_PARENT_OPTIONS,
            params={"masterTagId": 1036, "browseParentTagId": 1774},
        )

    async def test_secure_mode_parent_step_after_master(self, mock_oe_client: AsyncMock) -> None:
        secure_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "masterTagChoices": [{"masterTagId": 12, "tagName": "Finance"}],
            },
        }
        parent_opts = {
            "ok": True,
            "data": {
                "masterTagId": 12,
                "masterTagName": "Finance",
                "parentTagChoices": [
                    {"parentTagId": 101, "tagName": "Cost Center"},
                ],
            },
        }
        mock_oe_client.get.side_effect = [secure_opts, secure_opts, parent_opts]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(
            tag_name="ChildTag",
            master_tag_id=12,
            master_tag_id_confirmed_by_user=True,
        )
        assert out["ok"] is True
        assert out.get("doNotCreateTag") is True
        assert out.get("selectionPhase") == "PARENT_OPTIONAL"
        assert out.get("userMustSelectParentOrSkip") is True
        assert out["parentTagChoiceCount"] == 1
        assert "SECURE mode" in out["formattedResponse"]
        assert "Under master only" in out["formattedResponse"]
        assert out.get("createUnderMasterOnlyOption", {}).get("masterTagId") == 12
        mock_oe_client.post.assert_not_called()
        mock_oe_client.get.assert_any_call(
            MCP_PATH_TAGS_PARENT_OPTIONS,
            params={"masterTagId": 12},
        )

    async def test_rejects_invented_master_tag_id(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "masterTagChoices": [{"masterTagId": 12, "tagName": "Finance"}],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(
            tag_name="GDPR Classification",
            master_tag_id=1062,
            master_tag_id_confirmed_by_user=True,
        )
        assert out["ok"] is False
        assert out.get("userMustSelectMasterTag") is True
        mock_oe_client.post.assert_not_called()

    async def test_open_mode_tag_name_only_shows_parents_then_create(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"tagId": 50, "tagName": "SkipTest", "tagSecurityMode": "open"},
        }
        open_create_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "open",
                "parentTagChoices": [{"parentTagId": 1, "tagName": "Root"}],
            },
        }
        open_step_gets = [
            {"ok": True, "data": {"tagSecurityMode": "open"}},
            open_create_opts,
            {"ok": True, "data": {"tagSecurityMode": "open"}},
        ]
        mock_oe_client.get.side_effect = [
            *open_step_gets,
            *open_step_gets,
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        step1 = await fn(tag_name="SkipTest")
        assert step1.get("selectionPhase") == "PARENT_OPTIONAL"
        assert step1.get("userSelectableParents")
        mock_oe_client.post.assert_not_called()
        await fn(
            tag_name="SkipTest",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        out = await fn(
            tag_name="SkipTest",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
            create_confirmed_by_user=True,
        )
        assert out["ok"] is True
        mock_oe_client.post.assert_called_once()

    async def test_open_mode_parent_tag_id_post_matches_ui(
        self, mock_oe_client: AsyncMock
    ) -> None:
        """Open mode under a parent → POST parentTagId only (same as tag/addNewTag UI)."""
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "tagId": 200,
                "tagName": "Child",
                "parentTagId": 1055,
                "tagSecurityMode": "open",
            },
        }
        open_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "open",
                "parentTagChoices": [{"parentTagId": 1055, "tagName": "AssociateTag"}],
            },
        }
        open_parent_gets = [open_opts, open_opts, open_opts, open_opts, open_opts]
        mock_oe_client.get.side_effect = [
            *open_parent_gets,
            *open_parent_gets,
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="Child")
        await fn(
            tag_name="Child",
            parent_tag_id=1055,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
        )
        out = await fn(
            tag_name="Child",
            parent_tag_id=1055,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
            create_confirmed_by_user=True,
        )
        assert out["ok"] is True
        body = mock_oe_client.post.call_args.kwargs.get("body") or {}
        assert body.get("parentTagId") == 1055
        assert body.get("masterTagId") is None

    async def test_open_mode_blocks_create_until_parent_list_shown(
        self, mock_oe_client: AsyncMock
    ) -> None:
        open_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "open",
                "parentTagChoices": [{"parentTagId": 1, "tagName": "Root"}],
            },
        }
        mock_oe_client.get.side_effect = [open_opts, open_opts]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(
            tag_name="pencil",
            create_directly_under_master=True,
        )
        assert out.get("selectionPhase") == "PARENT_OPTIONAL"
        assert out.get("doNotCreateTag") is True
        assert out.get("userSelectableParents")
        mock_oe_client.post.assert_not_called()

    async def test_open_mode_suggests_parent_before_create(
        self, mock_oe_client: AsyncMock
    ) -> None:
        open_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "open",
                "parentTagChoices": [
                    {"parentTagId": 1013, "tagName": "Personal Finance"},
                    {"parentTagId": 1033, "tagName": "Risk Management"},
                ],
            },
        }
        mock_oe_client.get.side_effect = [open_opts, open_opts]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(tag_name="OpenChild")
        assert out["ok"] is True
        assert out.get("selectionPhase") == "PARENT_OPTIONAL"
        assert out.get("presentParentTagsToUser") is True
        assert out.get("tagSecurityMode") == "open"
        assert out.get("masterTagRequired") is False
        assert out.get("parentTagChoiceCount") == 2
        assert "No parent" in out["formattedResponse"]
        assert "no master tag step" in out["formattedResponse"].lower()
        mock_oe_client.post.assert_not_called()
        mock_oe_client.get.assert_any_call(MCP_PATH_TAGS_CREATE_OPTIONS)

    async def test_open_mode_confirm_preview_blocks_post(
        self, mock_oe_client: AsyncMock
    ) -> None:
        open_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "open",
                "parentTagChoices": [{"parentTagId": 1, "tagName": "Root"}],
            },
        }
        mock_oe_client.get.side_effect = [open_opts, open_opts, open_opts, open_opts]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="Logistics")
        preview = await fn(
            tag_name="Logistics",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        assert preview["workflowPhase"] == "confirm_create"
        assert preview.get("doNotCreateTag") is True
        assert preview.get("createConfirmedByUser") is False
        mock_oe_client.post.assert_not_called()

    async def test_open_mode_create_without_parent(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"tagId": 88, "tagName": "OpenChild", "tagSecurityMode": "open"},
        }
        open_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "open",
                "parentTagChoices": [{"parentTagId": 1, "tagName": "Root"}],
            },
        }
        open_child_gets = [open_opts, open_opts, open_opts]
        mock_oe_client.get.side_effect = [
            *open_child_gets,
            *open_child_gets,
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="OpenChild")
        await fn(
            tag_name="OpenChild",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        out = await fn(
            tag_name="OpenChild",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
            create_confirmed_by_user=True,
        )
        assert out["ok"] is True
        mock_oe_client.post.assert_called_once()
        body = mock_oe_client.post.call_args.kwargs.get("body") or {}
        assert body.get("tagName") == "OpenChild"
        assert body.get("parentTagId") is None
        desc = body.get("description") or ""
        assert "OpenChild" in desc
        assert desc.startswith("<p>")

    async def test_secure_create_auto_description_when_omitted(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {"tagId": 50, "tagName": "Pouse", "masterTagId": 1031},
        }
        secure_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "masterTagChoices": [
                    {"masterTagId": 1031, "tagName": "Investment Services"},
                ],
            },
        }
        parent_opts = {
            "ok": True,
            "data": {
                "masterTagId": 1031,
                "masterTagName": "Investment Services",
                "parentTagChoices": [
                    {"parentTagId": 1042, "tagName": "Savings Accounts"},
                ],
            },
        }
        async def secure_get(path: str, **kwargs: object) -> dict[str, object]:
            if path == MCP_PATH_TAGS_PARENT_OPTIONS:
                return parent_opts
            if path == MCP_PATH_TAGS:
                return {"ok": True, "data": {"objectId": 50, "objectName": "Pouse"}}
            return secure_opts

        mock_oe_client.get.side_effect = secure_get
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(
            tag_name="Pouse",
            master_tag_id=1031,
            master_tag_id_confirmed_by_user=True,
        )
        await fn(
            tag_name="Pouse",
            master_tag_id=1031,
            master_tag_id_confirmed_by_user=True,
            parent_tag_id=1042,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
        )
        out = await fn(
            tag_name="Pouse",
            master_tag_id=1031,
            master_tag_id_confirmed_by_user=True,
            parent_tag_id=1042,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
            create_confirmed_by_user=True,
        )
        assert out["ok"] is True
        body = mock_oe_client.post.call_args.kwargs.get("body") or {}
        desc = body.get("description") or ""
        assert "Pouse" in desc
        assert "Savings Accounts" in desc
        assert "Investment Services" in desc
        assert desc.startswith("<p>")

    async def test_open_mode_finalize_without_picker_step_reshows_picker(
        self, mock_oe_client: AsyncMock
    ) -> None:
        open_opts = {
            "ok": True,
            "data": {
                "tagSecurityMode": "open",
                "parentTagChoices": [{"parentTagId": 1, "tagName": "Root"}],
            },
        }
        mock_oe_client.get.side_effect = [open_opts, open_opts]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(
            tag_name="Local",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        assert out.get("doNotCreateTag") is True
        assert out.get("userSelectableParents")
        mock_oe_client.post.assert_not_called()

    async def test_rejects_llm_picked_valid_master_without_user_confirm(
        self, mock_oe_client: AsyncMock
    ) -> None:
        """Even if 1062 were in the list, the LLM cannot confirm on behalf of the user."""
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "tagSecurityMode": "secure",
                "masterTagChoices": [{"masterTagId": 1062, "tagName": "GPC"}],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        out = await fn(tag_name="GDPR Classification", master_tag_id=1062)
        assert out["ok"] is False
        assert out.get("masterTagIdConfirmedByUserRequired") is True
        assert out.get("doNotCreateTag") is True
        mock_oe_client.post.assert_not_called()


class TestTagAutoDescription:
    def test_build_auto_description_with_hierarchy(self) -> None:
        desc = governance_helpers._build_auto_tag_description(
            "Pouse",
            master_tag_name="Investment Services",
            parent_tag_name="Savings Accounts",
        )
        assert "Pouse" in desc
        assert "Savings Accounts" in desc
        assert "Investment Services" in desc
        assert desc.startswith("<p>") and desc.endswith("</p>")

    def test_explicit_description_wins(self) -> None:
        assert (
            governance_helpers._resolve_create_tag_description(
                "Pouse",
                "<p>custom</p>",
                master_tag_name="Investment Services",
            )
            == "<p>custom</p>"
        )

    def test_disabled_returns_none(self, monkeypatch) -> None:
        from server.config import settings

        monkeypatch.setattr(settings, "ovaledge_tag_auto_description", False)
        assert (
            governance_helpers._resolve_create_tag_description("Pouse", None) is None
        )


_MOCK_DATASTORY_REL = "#nav/story?id=42"
_MOCK_DATASTORY_ABS = "https://mock.ovaledge.com/#nav/story?id=42"
_MOCK_DATASTORY_BAD_ABS = (
    "https://mock.ovaledge.com/https://mock.ovaledge.com/#nav/story?id=42"
)
MOCK_DATASTORY_API = {
    "ok": True,
    "data": {
        "metadata": {
            "storyZoneName": "Finance",
            "storyName": "Sales",
            "objectId": 42,
            "fullQualifiedName": "Finance.Sales",
        },
        "content": {
            "story": (
                "<h3>Scope</h3><p>Applies to <strong>critical PII tables</strong>.</p>"
                "<h3>Cadence</h3><p><strong>Quarterly certification review</strong>.</p>"
            ),
        },
        "accessControl": {
            "authorizedRoles": ["OE_STORY_ZONE_READER"],
            "authorizedUsers": [],
            "permissionMappings": [],
        },
        "navLink": _MOCK_DATASTORY_REL,
        "hyperlink": _MOCK_DATASTORY_ABS,
        "navUrl": _MOCK_DATASTORY_ABS,
        "storyTitleLink": f"[Sales]({_MOCK_DATASTORY_REL})",
    },
}
def _expected_formatted_response() -> str:
    return (
        f"[Sales]({_MOCK_DATASTORY_REL}) (story zone: Finance)\n\n"
        "**Scope**\n\n"
        "Applies to critical PII tables.\n\n"
        "**Cadence**\n\n"
        "Quarterly certification review.\n\n"
        "**Access control**\n\n"
        "- **Authorized roles:** OE_STORY_ZONE_READER\n\n"
        f"{_MOCK_DATASTORY_ABS}"
    )


class TestLookupDatastory:
    async def test_passes_through_nav_links_from_api(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(object_id=42)
        assert out["data"]["navLink"] == _MOCK_DATASTORY_REL
        assert out["data"]["hyperlink"] == _MOCK_DATASTORY_ABS
        assert out["data"]["navUrl"] == _MOCK_DATASTORY_ABS
        assert out["data"]["storyTitleLink"] == f"[Sales]({_MOCK_DATASTORY_REL})"
        assert "formattedResponse" in out
        assert _MOCK_DATASTORY_ABS in out["formattedResponse"]
        assert "[Sales]" in out["formattedResponse"]
        assert "**Scope**" in out["formattedResponse"]
        assert "**Cadence**" in out["formattedResponse"]
        assert "| Field | Value |" not in out["formattedResponse"]
        assert "Open in OvalEdge" not in out["formattedResponse"]
        assert "openStoryUrl" not in out
        assert "relativeHyperlink" not in out["data"]
        assert "navLink" not in out

    async def test_passes_through_backend_hyperlink_unchanged(
        self, mock_oe_client: AsyncMock
    ) -> None:
        bad_api = {
            **MOCK_DATASTORY_API,
            "data": {
                **MOCK_DATASTORY_API["data"],
                "hyperlink": _MOCK_DATASTORY_BAD_ABS,
                "navLink": _MOCK_DATASTORY_BAD_ABS,
                "navUrl": _MOCK_DATASTORY_BAD_ABS,
            },
        }
        mock_oe_client.get.return_value = bad_api
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(object_id=42)
        assert out["data"]["hyperlink"] == _MOCK_DATASTORY_BAD_ABS
        assert out["data"]["navLink"] == _MOCK_DATASTORY_BAD_ABS

    async def test_formatted_response_for_content_query_style(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(
            content_query="Home Page Welcome View highlighting features onboard users"
        )
        assert "formattedResponse" in out
        assert "**Scope**" in out["formattedResponse"]
        assert out["data"]["navUrl"] == _MOCK_DATASTORY_ABS

    async def test_story_name_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(story_name="Sales")
        assert out["data"]["navUrl"] == _MOCK_DATASTORY_ABS
        assert out["data"]["metadata"]["storyName"] == "Sales"
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"storyName": "Sales"},
        )

    async def test_zone_and_name(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(story_zone_name="Finance", story_name="Sales")
        assert out["data"]["navUrl"] == _MOCK_DATASTORY_ABS
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"storyZoneName": "Finance", "storyName": "Sales"},
        )

    async def test_object_id_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(object_id=42)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"objectId": 42},
        )

    async def test_object_id_with_optional_zone(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(object_id=42, story_zone_name="Finance")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"objectId": 42, "storyZoneName": "Finance"},
        )

    async def test_rejects_id_with_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(object_id=1, story_name="Sales")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_rejects_no_params(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn()
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_content_query_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(content_query="revenue forecast")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"contentQuery": "revenue forecast"},
        )

    async def test_zone_and_content_query(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(story_zone_name="Finance", content_query="revenue forecast")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"storyZoneName": "Finance", "contentQuery": "revenue forecast"},
        )

    async def test_name_and_content_query(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(story_name="Sales", content_query="revenue")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"storyName": "Sales", "contentQuery": "revenue"},
        )

    async def test_zone_name_and_content_query(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(
            story_zone_name="Finance",
            story_name="Sales",
            content_query="revenue forecast",
        )
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={
                "storyZoneName": "Finance",
                "storyName": "Sales",
                "contentQuery": "revenue forecast",
            },
        )


class TestLookupDqRule:
    async def test_rule_name_lookup(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": [
                {
                    "objectId": 42,
                    "objectType": "dqrule",
                    "objectName": "Null Data Density Check",
                }
            ],
        }
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_dq_rule")
        out = await fn(rule_name="Null Data Density")
        assert out["ok"] is True
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DQ_RULES,
            params={"ruleName": "Null Data Density", "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT},
        )

    async def test_rejects_both_id_and_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        dataquality.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_dq_rule")
        out = await fn(object_id=1, rule_name="x")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()


class TestUpdateGovernanceRoles:
    async def test_rejects_unsupported_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(
            object_id=1,
            object_type="not_a_real_type",
            role_updates={"owner": "john"},
        )
        assert out["status_code"] == 400
        assert "unsupported object_type" in out["error"].lower()
        mock_oe_client.post.assert_not_called()

    async def test_rejects_owner_on_dqrule(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(
            object_id=1,
            object_type="dqrule",
            role_updates={"owner": "arun_v"},
        )
        assert out["status_code"] == 400
        assert "steward" in out["error"].lower()
        mock_oe_client.post.assert_not_called()

    async def test_rejects_missing_role_updates(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(object_id=1, object_type="oetable")
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_invalid_role_key(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(
            object_id=1,
            object_type="oetable",
            role_updates={"product_owner": "john"},
        )
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_confirm_preview_blocks_post(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(
            object_id=99,
            object_type="oetable",
            role_updates={"owner": "mike"},
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["doNotUpdate"] is True
        mock_oe_client.post.assert_not_called()

    async def test_posts_body_and_enriches_response(
        self, mock_oe_client: AsyncMock
    ) -> None:
        api_resp = {
            "status": "partial_success",
            "reasonCode": "GLOSSARY_PROPAGATED_GOVERNANCE_ROLE",
            "updatedRoles": ["owner"],
            "blockedRoles": ["steward"],
            "target": {
                "objectId": 99,
                "objectType": "oetable",
                "redirectUrl": "https://mock.ovaledge.com/#nav/table?id=99",
            },
        }
        mock_oe_client.post.return_value = api_resp

        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(
            object_id=99,
            object_type="oetable",
            role_updates={"Owner": "mike", "Steward": "john"},
            prompt="Assign John as Steward and Mike as Owner",
            reason="Ownership update request",
            create_confirmed_by_user=True,
        )

        assert out["status"] == "partial_success"
        assert out["reasonCode"] == "GLOSSARY_PROPAGATED_GOVERNANCE_ROLE"
        assert "formattedResponse" in out
        assert "Blocked roles" in out["formattedResponse"]
        assert "Open in OvalEdge" in out["formattedResponse"]

        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_UPDATE_GOVERNANCE_ROLES,
            {
                "target": {"objectId": 99, "objectType": "oetable"},
                "roleUpdates": {"owner": "mike", "steward": "john"},
                "clientContext": {
                    "prompt": "Assign John as Steward and Mike as Owner",
                    "reason": "Ownership update request",
                },
            },
        )

    async def test_role_value_empty_string_as_remove(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "status": "success",
            "updatedRoles": ["custodian"],
            "blockedRoles": [],
            "target": {"objectId": 1, "objectType": "oetable"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        await fn(
            object_id=1,
            object_type="oetable",
            role_updates={"custodian": ""},
            create_confirmed_by_user=True,
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_UPDATE_GOVERNANCE_ROLES,
            {
                "target": {"objectId": 1, "objectType": "oetable"},
                "roleUpdates": {"custodian": None},
            },
        )

    async def test_accepts_govrole5_synonym(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "status": "success",
            "updatedRoles": ["governance_role_5"],
            "blockedRoles": [],
            "target": {"objectId": 1, "objectType": "oetable"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        await fn(
            object_id=1,
            object_type="oetable",
            role_updates={"govrole5": "sarah"},
            create_confirmed_by_user=True,
        )
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_UPDATE_GOVERNANCE_ROLES,
            {
                "target": {"objectId": 1, "objectType": "oetable"},
                "roleUpdates": {"governance_role_5": "sarah"},
            },
        )

    async def test_governance_role_not_enabled_error_is_structured(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(
            400, "Governance role is not enabled: governance_role_5"
        )
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(
            object_id=1,
            object_type="oetable",
            role_updates={"governance_role_5": "sarah"},
            create_confirmed_by_user=True,
        )
        assert out["status_code"] == 400
        assert out["reason_code"] == "GOVERNANCE_ROLE_NOT_ENABLED"
        assert "not enabled" in out["error"].lower()

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(
            object_id=1,
            object_type="oetable",
            role_updates={"owner": "sarah"},
            create_confirmed_by_user=True,
        )
        assert out["status_code"] == 403


class TestUpdateCustomFieldValue:
    async def test_rejects_missing_field_updates(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(object_id=1, object_type="oetable", field_updates=[])
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_rejects_unsupported_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=1,
            object_type="project",
            field_updates=[{"field_name": "Retention Period", "value": "7 years"}],
        )
        assert out["status_code"] == 400
        mock_oe_client.post.assert_not_called()

    async def test_confirm_preview_blocks_post(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "Data Owner",
                        "fieldKey": "gtcf1",
                        "type": "text",
                        "allowMultiple": False,
                        "currentValue": "",
                        "options": [],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=99,
            object_type="oetable",
            field_updates=[{"field_name": "Data Owner", "value": "John Smith"}],
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["doNotUpdate"] is True
        mock_oe_client.post.assert_not_called()

    async def test_posts_body_and_enriches_response(
        self, mock_oe_client: AsyncMock
    ) -> None:
        api_resp = {
            "status": "success",
            "updatedFields": ["Data Owner"],
            "blockedFields": [],
            "target": {
                "objectId": 99,
                "objectType": "oetable",
                "redirectUrl": "https://mock.ovaledge.com/#nav/table?id=99",
            },
            "audit": {"source": "OE-MCP"},
        }
        mock_oe_client.post.return_value = api_resp
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "Data Owner",
                        "fieldKey": "gtcf1",
                        "type": "text",
                        "allowMultiple": False,
                        "currentValue": "",
                        "options": [],
                    }
                ]
            },
        }

        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        with patch(
            "server.tools.governance.invocations.resolve_client_timezone",
            return_value="Asia/Kolkata",
        ):
            out = await fn(
                object_id=99,
                object_type="oetable",
                field_updates=[{"field_name": "Data Owner", "value": "John Smith"}],
                prompt="Update Data Owner to John Smith",
                create_confirmed_by_user=True,
            )

        assert out["status"] == "success"
        assert "formattedResponse" in out
        assert "OE-MCP" in out["formattedResponse"]

        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES,
            {
                "target": {"objectId": 99, "objectType": "oetable"},
                "fieldUpdates": [{"fieldName": "Data Owner", "value": "John Smith"}],
                "timeZone": "Asia/Kolkata",
                "clientContext": {"prompt": "Update Data Owner to John Smith"},
            },
        )

    async def test_single_value_text_field_reaches_confirm(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "Automation_TextCF",
                        "fieldKey": "gtcf1",
                        "type": "text",
                        "allowMultiple": False,
                        "currentValue": "old",
                        "options": [],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=99,
            object_type="oeschema",
            field_updates=[{"field_name": "Automation_TextCF", "value": "hello"}],
        )
        assert out["workflowPhase"] == "confirm_update"
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_CUSTOM_FIELDS,
            params={
                "objectId": 99,
                "objectType": "oeschema",
                "fieldName": "Automation_TextCF",
            },
        )

    async def test_single_value_invalid_code_option_rejected(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "added",
                        "fieldKey": "gccf3",
                        "type": "code",
                        "allowMultiple": False,
                        "currentValue": "false",
                        "options": [
                            {"name": "true", "codeId": 1262},
                            {"name": "false", "codeId": 1263},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=6432,
            object_type="oeschema",
            field_updates=[{"field_name": "added", "value": "maybe"}],
        )
        assert out["workflowPhase"] == "invalid_code_options"
        assert out["status_code"] == 400
        assert "maybe" in out["formattedResponse"]
        assert "true, false" in out["formattedResponse"]
        mock_oe_client.post.assert_not_called()

    async def test_multi_value_invalid_code_option_rejected(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "Automation_CodeCF",
                        "fieldKey": "gccf1",
                        "type": "code",
                        "allowMultiple": True,
                        "currentValue": "option 1, option 2",
                        "options": [
                            {"name": "option 1", "codeId": 1008},
                            {"name": "option 2", "codeId": 1009},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=1000,
            object_type="oeschema",
            field_updates=[
                {
                    "field_name": "Automation_CodeCF",
                    "value": ["option 1", "option 2", "option 3"],
                }
            ],
            code_update_mode="replace_all",
        )
        assert out["workflowPhase"] == "invalid_code_options"
        assert out["status_code"] == 400
        assert "option 3" in out["formattedResponse"]
        mock_oe_client.post.assert_not_called()

    async def test_single_value_code_option_canonicalized(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "added",
                        "fieldKey": "gccf3",
                        "type": "code",
                        "allowMultiple": False,
                        "currentValue": "false",
                        "options": [
                            {"name": "true", "codeId": 1262},
                            {"name": "false", "codeId": 1263},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=6432,
            object_type="oeschema",
            field_updates=[{"field_name": "added", "value": "TRUE"}],
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["pendingUpdate"]["fieldUpdates"][0]["value"] == "true"

    async def test_multi_value_single_select_code_field_asks_clarification(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "added",
                        "fieldKey": "gccf3",
                        "type": "code",
                        "allowMultiple": False,
                        "currentValue": "false",
                        "options": [
                            {"name": "true", "codeId": 1262},
                            {"name": "false", "codeId": 1263},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=6432,
            object_type="oeschema",
            field_updates=[{"field_name": "added", "value": "TRUE,FALSE"}],
        )
        assert out["workflowPhase"] == "clarify_single_select"
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_CUSTOM_FIELDS,
            params={
                "objectId": 6432,
                "objectType": "oeschema",
                "fieldName": "added",
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_multi_value_multi_select_without_mode_asks_clarification(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "tags",
                        "fieldKey": "gccf1",
                        "type": "code",
                        "allowMultiple": True,
                        "currentValue": "a",
                        "options": [
                            {"name": "a", "codeId": 1},
                            {"name": "b", "codeId": 2},
                            {"name": "c", "codeId": 3},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=10,
            object_type="oeschema",
            field_updates=[{"field_name": "tags", "value": "b,c"}],
        )
        assert out["workflowPhase"] == "clarify_multi_select_mode"
        mock_oe_client.post.assert_not_called()

    async def test_multi_value_multi_select_replace_all_reaches_confirm(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "tags",
                        "fieldKey": "gccf1",
                        "type": "code",
                        "allowMultiple": True,
                        "currentValue": "a",
                        "options": [
                            {"name": "a", "codeId": 1},
                            {"name": "b", "codeId": 2},
                            {"name": "c", "codeId": 3},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=10,
            object_type="oeschema",
            field_updates=[{"field_name": "tags", "value": "b,c"}],
            code_update_mode="replace_all",
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["pendingUpdate"]["fieldUpdates"][0]["value"] == "b,c"

    async def test_list_value_joined_into_comma_string(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "tags",
                        "fieldKey": "gccf1",
                        "type": "code",
                        "allowMultiple": True,
                        "currentValue": "a",
                        "options": [
                            {"name": "a", "codeId": 1},
                            {"name": "b", "codeId": 2},
                            {"name": "c", "codeId": 3},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=10,
            object_type="oeschema",
            field_updates=[{"field_name": "tags", "value": ["b", "c"]}],
            code_update_mode="replace_all",
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["pendingUpdate"]["fieldUpdates"][0]["value"] == "b,c"

    async def test_and_separator_splits_code_values(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "tags",
                        "fieldKey": "gccf1",
                        "type": "code",
                        "allowMultiple": True,
                        "currentValue": "a",
                        "options": [
                            {"name": "a", "codeId": 1},
                            {"name": "b", "codeId": 2},
                            {"name": "c", "codeId": 3},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=10,
            object_type="oeschema",
            field_updates=[{"field_name": "tags", "value": "b and c"}],
            code_update_mode="replace_all",
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["pendingUpdate"]["fieldUpdates"][0]["value"] == "b,c"

    async def test_mixed_comma_and_separators_split_code_values(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "tags",
                        "fieldKey": "gccf1",
                        "type": "code",
                        "allowMultiple": True,
                        "currentValue": "",
                        "options": [
                            {"name": "a", "codeId": 1},
                            {"name": "b", "codeId": 2},
                            {"name": "c", "codeId": 3},
                        ],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=10,
            object_type="oeschema",
            field_updates=[{"field_name": "tags", "value": "a, b and c"}],
            code_update_mode="replace_all",
        )
        assert out["workflowPhase"] == "confirm_update"
        assert out["pendingUpdate"]["fieldUpdates"][0]["value"] == "a,b,c"

    async def test_confirmed_post_resolves_list_value_before_sending(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "Automation_CodeCF",
                        "fieldKey": "gccf1",
                        "type": "code",
                        "allowMultiple": True,
                        "currentValue": "",
                        "options": [
                            {"name": "option 1", "codeId": 1},
                            {"name": "option 2", "codeId": 2},
                        ],
                    }
                ]
            },
        }
        mock_oe_client.post.return_value = {
            "status": "success",
            "updatedFields": ["gccf1"],
            "target": {"objectId": 1000, "objectType": "oeschema"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=1000,
            object_type="oeschema",
            field_updates=[
                {"field_name": "Automation_CodeCF", "value": ["option 1", "option 2"]}
            ],
            code_update_mode="replace_all",
            create_confirmed_by_user=True,
        )
        assert out["status"] == "success"
        posted_body = mock_oe_client.post.call_args.args[1]
        assert posted_body["fieldUpdates"][0]["value"] == "option 1,option 2"

    async def test_stringified_list_value_coerced_to_comma_string(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "Automation_CodeCF",
                        "fieldKey": "gccf1",
                        "type": "code",
                        "allowMultiple": True,
                        "currentValue": "",
                        "options": [
                            {"name": "option 1", "codeId": 1008},
                            {"name": "option 2", "codeId": 1009},
                        ],
                    }
                ]
            },
        }
        mock_oe_client.post.return_value = {
            "status": "success",
            "updatedFields": ["gccf1"],
            "target": {"objectId": 1000, "objectType": "oeschema"},
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=1000,
            object_type="oeschema",
            field_updates=[
                {"field_name": "Automation_CodeCF", "value": "['option 1', 'option 2']"}
            ],
            code_update_mode="replace_all",
            create_confirmed_by_user=True,
        )
        assert out["status"] == "success"
        posted_body = mock_oe_client.post.call_args.args[1]
        assert posted_body["fieldUpdates"][0]["value"] == "option 1,option 2"

    async def test_multi_value_text_field_skips_code_policy(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {
            "ok": True,
            "data": {
                "fields": [
                    {
                        "fieldName": "Automation_TextCF",
                        "fieldKey": "gtcf1",
                        "type": "text",
                        "allowMultiple": False,
                        "currentValue": "old",
                        "options": [],
                    }
                ]
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_custom_field_value")
        out = await fn(
            object_id=1000,
            object_type="oeschema",
            field_updates=[
                {"field_name": "Automation_TextCF", "value": "Hello, World"}
            ],
        )
        assert out["workflowPhase"] == "confirm_update"
        assert (
            out["pendingUpdate"]["fieldUpdates"][0]["value"] == "Hello, World"
        )


