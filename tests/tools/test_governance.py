from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_LOOKUP_DQ_RULES,
    MCP_PATH_TAGS,
    MCP_PATH_UPDATE_GOVERNANCE_ROLES,
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
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_dq_rule")
        out = await fn(rule_name="Null Data Density")
        assert out["ok"] is True
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_LOOKUP_DQ_RULES,
            params={"ruleName": "Null Data Density", "limit": MCP_GLOSSARY_TAGS_LIMIT_DEFAULT},
        )

    async def test_rejects_both_id_and_name(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "lookup_dq_rule")
        out = await fn(object_id=1, rule_name="x")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()


class TestUpdateGovernanceRoles:
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
        await fn(object_id=1, object_type="oetable", role_updates={"custodian": ""})
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_UPDATE_GOVERNANCE_ROLES,
            {
                "target": {"objectId": 1, "objectType": "oetable"},
                "roleUpdates": {"custodian": None},
            },
        )

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(403, "Forbidden")
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "update_governance_roles")
        out = await fn(
            object_id=1,
            object_type="oetable",
            role_updates={"owner": "sarah"},
        )
        assert out["status_code"] == 403


