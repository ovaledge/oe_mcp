from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import MCP_PATH_KNOWLEDGE_SEARCH, TOOL_KNOWLEDGE_SEARCH
from server.tools import docs as docs_tools
from tests.conftest import MOCK_DOCS_SEARCH
from tests.helpers import get_tool_fn


async def _knowledge_fn(mcp: FastMCP | None = None) -> Any:
    mcp = mcp or FastMCP(name="test", version="0.0.1")
    docs_tools.register(mcp)
    return await get_tool_fn(mcp, TOOL_KNOWLEDGE_SEARCH)


def _story_body(stories: dict[str, Any], **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"dataStories": stories}
    data.update(extra)
    return {"ok": True, "data": data}


class TestKnowledgeSearch:
    async def test_limit_cap(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "knowledge_search")
        await fn(query="how to", limit=100)
        assert mock_oe_client.get.call_args[0][0] == MCP_PATH_KNOWLEDGE_SEARCH
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["query"] == "how to"
        assert params["limit"] == 50
        assert params["numCandidates"] == 128

    async def test_limit_only_sets_num_candidates(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "knowledge_search")
        await fn(query="dq rules", limit=15)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 15
        assert params["numCandidates"] == 128

    async def test_num_candidates_query_param(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "knowledge_search")
        await fn(query="x", limit=5, num_candidates=200)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 5
        assert params["numCandidates"] == 200

    async def test_num_candidates_clamped_below_limit(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "knowledge_search")
        await fn(query="x", limit=20, num_candidates=5)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["limit"] == 20
        assert params["numCandidates"] == 20

    async def test_oval_edge_error_returns_dict(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(500, "Internal error")
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "knowledge_search")
        out = await fn(query="failure query")
        assert out["status_code"] == 500
        assert "500" in out["error"]

    async def test_query_only_omits_limit_and_num_candidates(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "knowledge_search")
        out = await fn(query="how to crawl")
        assert out == MOCK_DOCS_SEARCH
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_KNOWLEDGE_SEARCH,
            params={"query": "how to crawl"},
        )

    async def test_num_candidates_only_without_limit(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "knowledge_search")
        await fn(query="dq rules", num_candidates=64)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"query": "dq rules", "numCandidates": 64}
        assert "limit" not in params

    async def test_num_candidates_only_clamped(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        mcp = FastMCP(name="test", version="0.0.1")
        docs_tools.register(mcp)
        fn = await get_tool_fn(mcp, "knowledge_search")
        await fn(query="x", num_candidates=0)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["numCandidates"] == 1
        await fn(query="x", num_candidates=9999)
        assert mock_oe_client.get.call_args[1]["params"]["numCandidates"] == 512


class TestKnowledgeSearchStoryParams:
    """Story-targeting parameters must reach the API under their wire names."""

    async def test_content_query_alias_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        fn = await _knowledge_fn()
        await fn(content_query="member approval steps")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"contentQuery": "member approval steps"}

    async def test_story_zone_name_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        fn = await _knowledge_fn()
        await fn(query="policy", story_zone_name="Governance")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["storyZoneName"] == "Governance"

    async def test_story_name_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        fn = await _knowledge_fn()
        await fn(story_name="Data Lineage Demo")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"storyName": "Data Lineage Demo"}

    async def test_object_id_forwarded(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        fn = await _knowledge_fn()
        await fn(object_id=1034)
        params = mock_oe_client.get.call_args[1]["params"]
        assert params == {"objectId": 1034}

    @pytest.mark.parametrize("object_id", [0, -1])
    async def test_non_positive_object_id_is_omitted(
        self, mock_oe_client: AsyncMock, object_id: int
    ) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        fn = await _knowledge_fn()
        await fn(query="policy", object_id=object_id)
        assert "objectId" not in mock_oe_client.get.call_args[1]["params"]

    async def test_all_story_params_combined(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        fn = await _knowledge_fn()
        await fn(
            query="approval policy",
            content_query="approval steps",
            story_zone_name="Governance",
            story_name="Member Approval",
            object_id=7,
            limit=5,
            num_candidates=64,
        )
        assert mock_oe_client.get.call_args[1]["params"] == {
            "query": "approval policy",
            "contentQuery": "approval steps",
            "storyZoneName": "Governance",
            "storyName": "Member Approval",
            "objectId": 7,
            "limit": 5,
            "numCandidates": 64,
        }

    async def test_values_are_stripped(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        fn = await _knowledge_fn()
        await fn(query="  spaced query  ", story_name="  Story  ")
        params = mock_oe_client.get.call_args[1]["params"]
        assert params["query"] == "spaced query"
        assert params["storyName"] == "Story"


class TestKnowledgeSearchValidation:
    """No usable parameter must be rejected client-side, before any HTTP call."""

    async def test_no_parameters_returns_400_without_calling_api(
        self, mock_oe_client: AsyncMock
    ) -> None:
        fn = await _knowledge_fn()
        out = await fn()
        assert out["status_code"] == 400
        assert "query" in out["error"]
        mock_oe_client.get.assert_not_called()

    async def test_whitespace_only_inputs_are_rejected(
        self, mock_oe_client: AsyncMock
    ) -> None:
        fn = await _knowledge_fn()
        out = await fn(query="   ", content_query="", story_name="  ")
        assert out["status_code"] == 400
        mock_oe_client.get.assert_not_called()

    async def test_num_candidates_alone_is_enough_to_call(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = MOCK_DOCS_SEARCH
        fn = await _knowledge_fn()
        out = await fn(num_candidates=32)
        assert "error" not in out
        mock_oe_client.get.assert_called_once()


class TestKnowledgeSearchStoryEnrichment:
    """Data-story hits are reformatted for presentation; docs-only hits pass through."""

    STORY = {
        "metadata": {"storyName": "Member Approval Policy", "storyZoneName": "Governance"},
        "content": {"story": "<p>Members are approved by the credit committee.</p>"},
        "accessControl": {"authorizedRoles": ["Data Steward", "Analyst"]},
        "navUrl": "https://mock.ovaledge.com/ovaledge/#nav/story?id=1021",
    }

    async def test_story_section_produces_formatted_response(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _story_body(self.STORY)
        fn = await _knowledge_fn()
        out = await fn(query="member approval")
        formatted = out["formattedResponse"]
        assert "Member Approval Policy" in formatted
        assert "credit committee" in formatted
        assert "Data Steward" in formatted
        assert out["data"]["dataStories"]["formattedResponse"] == formatted

    async def test_story_enrichment_preserves_platform_docs_section(
        self, mock_oe_client: AsyncMock
    ) -> None:
        docs_section = [{"title": "Crawling guide", "score": 0.91}]
        mock_oe_client.get.return_value = _story_body(self.STORY, platformDocs=docs_section)
        fn = await _knowledge_fn()
        out = await fn(query="member approval")
        assert out["data"]["platformDocs"] == docs_section
        assert "formattedResponse" in out

    async def test_story_navigation_url_is_passed_through_unchanged(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _story_body(self.STORY)
        fn = await _knowledge_fn()
        out = await fn(query="member approval")
        assert self.STORY["navUrl"] in out["formattedResponse"]

    async def test_non_dict_story_section_is_left_untouched(
        self, mock_oe_client: AsyncMock
    ) -> None:
        body = {"ok": True, "data": {"dataStories": ["not-a-dict"]}}
        mock_oe_client.get.return_value = body
        fn = await _knowledge_fn()
        out = await fn(query="x")
        assert out["data"]["dataStories"] == ["not-a-dict"]
        assert "formattedResponse" not in out

    async def test_docs_only_response_is_not_enriched(
        self, mock_oe_client: AsyncMock
    ) -> None:
        body = {"ok": True, "data": {"platformDocs": [{"title": "Crawlers"}]}}
        mock_oe_client.get.return_value = body
        fn = await _knowledge_fn()
        out = await fn(query="how to crawl")
        assert out == body

    async def test_non_dict_backend_payload_is_wrapped(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = ["raw", "list"]
        fn = await _knowledge_fn()
        out = await fn(query="x")
        assert out == {"data": ["raw", "list"]}
