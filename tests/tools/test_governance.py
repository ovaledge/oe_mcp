from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_DOMAIN_METADATA_SIZE_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_PATH_DOMAIN_METADATA,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_TAGS,
)
from server.tools import governance
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
        out = await fn(
            term_name="Revenue Recognition",
            domain_id=12,
            description="ASC 606 revenue recognition policy.",
            category_id=55,
            subcategory_id=88,
            domain_name="Finance",
            category_name="cost",
            subcategory_name="money",
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

    async def test_create_uses_term_details_as_redirect_link(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                "businessGlossaryId": 2463,
                "termName": "joyful",
                "status": "DRAFT",
                "domainId": 1066,
                "termDetails": "#nav/glossary?browse=summary&id=2463",
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
        )
        assert out["termDetails"] == "#nav/glossary?browse=summary&id=2463"
        assert out["redirectUrl"].endswith("#nav/glossary?browse=summary&id=2463")
        assert out["data"]["termDetails"] == "#nav/glossary?browse=summary&id=2463"
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


MOCK_DATASTORY_CITATION = f"[Sales]({_MOCK_DATASTORY_REL}) (story zone: Finance)"

MOCK_DATASTORY_RESULT = {
    "ok": True,
    "navLink": _MOCK_DATASTORY_REL,
    "hyperlink": _MOCK_DATASTORY_ABS,
    "navUrl": _MOCK_DATASTORY_ABS,
    "storyZoneName": "Finance",
    "storyTitleLink": f"[Sales]({_MOCK_DATASTORY_REL})",
    "storyCitation": MOCK_DATASTORY_CITATION,
    "storyOpeningLine": MOCK_DATASTORY_CITATION,
    "formattedResponse": _expected_formatted_response(),
    "data": {
        **MOCK_DATASTORY_API["data"],
        "formattedResponse": _expected_formatted_response(),
    },
}


class TestLookupDatastory:
    async def test_normalize_nav_links_in_data(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(object_id=42)
        assert out["data"]["navLink"] == _MOCK_DATASTORY_REL
        assert out["data"]["hyperlink"] == _MOCK_DATASTORY_ABS
        assert out["navLink"] == _MOCK_DATASTORY_REL
        assert out["hyperlink"] == _MOCK_DATASTORY_ABS
        assert out["navUrl"] == _MOCK_DATASTORY_ABS
        assert out["storyTitleLink"] == f"[Sales]({_MOCK_DATASTORY_REL})"
        assert out["storyCitation"] == MOCK_DATASTORY_CITATION
        assert out["storyOpeningLine"] == MOCK_DATASTORY_CITATION
        assert out["storyZoneName"] == "Finance"
        assert "formattedResponse" in out
        assert _MOCK_DATASTORY_ABS in out["formattedResponse"]
        assert "[Sales]" in out["formattedResponse"]
        assert "**Scope**" in out["formattedResponse"]
        assert "**Cadence**" in out["formattedResponse"]
        assert "| Field | Value |" not in out["formattedResponse"]
        assert "Open in OvalEdge" not in out["formattedResponse"]
        assert "openStoryUrl" not in out
        assert "relativeHyperlink" not in out["data"]

    async def test_normalize_fixes_duplicated_backend_hyperlink(
        self, mock_oe_client: AsyncMock
    ) -> None:
        bad_api = {
            **MOCK_DATASTORY_API,
            "data": {
                **MOCK_DATASTORY_API["data"],
                "hyperlink": _MOCK_DATASTORY_BAD_ABS,
                "navLink": _MOCK_DATASTORY_BAD_ABS,
            },
        }
        mock_oe_client.get.return_value = bad_api
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(object_id=42)
        assert out["data"]["navLink"] == _MOCK_DATASTORY_REL
        assert out["data"]["hyperlink"] == _MOCK_DATASTORY_ABS

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
        assert out["navUrl"] == _MOCK_DATASTORY_ABS

    async def test_normalize_builds_nav_from_object_id_only(
        self, mock_oe_client: AsyncMock
    ) -> None:
        api = {
            "ok": True,
            "data": {
                "metadata": {
                    "storyName": "Sales",
                    "objectId": 42,
                    "storyZoneName": "Finance",
                },
                "content": {"story": "narrative"},
            },
        }
        mock_oe_client.get.return_value = api
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(object_id=42)
        assert out["data"]["navLink"] == _MOCK_DATASTORY_REL
        assert out["data"]["hyperlink"] == _MOCK_DATASTORY_ABS

    async def test_story_name_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_API
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        out = await fn(story_name="Sales")
        assert out["navUrl"] == _MOCK_DATASTORY_ABS
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
        assert out["navUrl"] == _MOCK_DATASTORY_ABS
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"storyZoneName": "Finance", "storyName": "Sales"},
        )

    async def test_object_id_only(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(object_id=42)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"objectId": 42},
        )

    async def test_object_id_with_optional_zone(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_RESULT
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
        mock_oe_client.get.return_value = MOCK_DATASTORY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(content_query="revenue forecast")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"contentQuery": "revenue forecast"},
        )

    async def test_zone_and_content_query(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(story_zone_name="Finance", content_query="revenue forecast")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"storyZoneName": "Finance", "contentQuery": "revenue forecast"},
        )

    async def test_name_and_content_query(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_RESULT
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_datastory")
        await fn(story_name="Sales", content_query="revenue")
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DATASTORY,
            params={"storyName": "Sales", "contentQuery": "revenue"},
        )

    async def test_zone_name_and_content_query(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DATASTORY_RESULT
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


