from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_TAGS,
    MCP_PATH_TAGS_CREATE_OPTIONS,
    MCP_PATH_TAGS_PARENT_OPTIONS,
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
        masters = governance._build_user_selectable_masters(choices)
        assert len(masters) == 3
        assert [m["masterTagId"] for m in masters] == [1, 2, 3]
        text = governance._format_master_list_for_user(masters)
        assert "3 accessible" in text
        assert "parentTagId=99" not in text


@pytest.fixture(autouse=True)
def _clear_parent_picker_pending() -> None:
    governance._pending_parent_picker_expiry.clear()
    yield
    governance._pending_parent_picker_expiry.clear()


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
        mock_oe_client.get.side_effect = [
            secure_opts,
            secure_opts,
            parent_opts,
            secure_opts,
            secure_opts,
            parent_opts,
            parent_opts,
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
        out = await fn(
            tag_name="Confidential",
            description="<p>secret</p>",
            master_tag_id=10,
            master_tag_id_confirmed_by_user=True,
            parent_tag_id=20,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
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
        mock_oe_client.get.side_effect = [
            {"ok": True, "data": {"tagSecurityMode": "open"}},
            open_create_opts,
            {"ok": True, "data": {"tagSecurityMode": "open"}},
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.0")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        step1 = await fn(tag_name="Ranchi")
        assert step1.get("selectionPhase") == "PARENT_OPTIONAL"
        out = await fn(
            tag_name="Ranchi",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
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
        mock_oe_client.get.side_effect = [
            open_opts,
            open_opts,
            open_opts,
            open_opts,
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="PII")
        out = await fn(
            tag_name="PII",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
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
        mock_oe_client.get.side_effect = [open_opts, open_opts, open_opts, open_opts]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="x")
        out = await fn(
            tag_name="x",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
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
        mock_oe_client.post.assert_not_called()

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
        mock_oe_client.get.side_effect = [
            {"ok": True, "data": {"tagSecurityMode": "open"}},
            open_create_opts,
            {"ok": True, "data": {"tagSecurityMode": "open"}},
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        step1 = await fn(tag_name="SkipTest")
        assert step1.get("selectionPhase") == "PARENT_OPTIONAL"
        assert step1.get("userSelectableParents")
        mock_oe_client.post.assert_not_called()
        out = await fn(
            tag_name="SkipTest",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
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
        mock_oe_client.get.side_effect = [
            open_opts,
            open_opts,
            open_opts,
            open_opts,
            open_opts,
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="Child")
        out = await fn(
            tag_name="Child",
            parent_tag_id=1055,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
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
        mock_oe_client.get.side_effect = [
            open_opts,
            open_opts,
            open_opts,
            OvalEdgeError(404, "Not found"),
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(tag_name="OpenChild")
        out = await fn(
            tag_name="OpenChild",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
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
        mock_oe_client.get.side_effect = [
            secure_opts,
            secure_opts,
            parent_opts,
            secure_opts,
            secure_opts,
            parent_opts,
            parent_opts,
            {"ok": True, "data": {"objectId": 50, "objectName": "Pouse"}},
        ]
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, "create_tag")
        await fn(
            tag_name="Pouse",
            master_tag_id=1031,
            master_tag_id_confirmed_by_user=True,
        )
        out = await fn(
            tag_name="Pouse",
            master_tag_id=1031,
            master_tag_id_confirmed_by_user=True,
            parent_tag_id=1042,
            parent_tag_id_confirmed_by_user=True,
            parent_step_completed_by_user=True,
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
        desc = governance._build_auto_tag_description(
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
            governance._resolve_create_tag_description(
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
            governance._resolve_create_tag_description("Pouse", None) is None
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


