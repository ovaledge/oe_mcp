"""MCP tool registration for dual-corpus knowledge search."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import MCP_PATH_KNOWLEDGE_SEARCH
from server.tools.common import map_ovaledge_error, ovaledge_client
from server.tools.docs.helpers import _DESC_KNOWLEDGE_SEARCH, knowledge_search_params
from server.tools.governance.datastory_helpers import _enrich_datastory_response


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_KNOWLEDGE_SEARCH)
    async def knowledge_search(
        query: Annotated[
            str | None,
            Field(
                description="Primary shared text for both data stories and platform docs.",
                default=None,
            ),
        ] = None,
        content_query: Annotated[
            str | None,
            Field(
                description=(
                    "Optional story-content alias for query "
                    "(parity with legacy story API)."
                ),
                default=None,
            ),
        ] = None,
        story_zone_name: Annotated[
            str | None,
            Field(description="Optional story zone filter/name.", default=None),
        ] = None,
        story_name: Annotated[
            str | None,
            Field(description="Optional story title filter/lookup.", default=None),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(description="Optional data-story object id for targeted lookup.", default=None),
        ] = None,
        limit: Annotated[
            int | None,
            Field(
                description=(
                    "Max platform-doc hits (maps to API limit; default 10 on server if omitted). "
                    "This client caps at 50."
                ),
                default=None,
            ),
        ] = None,
        num_candidates: Annotated[
            int | None,
            Field(
                description=(
                    "KNN numCandidates for docs (optional). Must be >= limit if both sent; "
                    "client enforces that."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """knowledge search (see MCP tool description)."""
        params = knowledge_search_params(
            query=query,
            content_query=content_query,
            story_zone_name=story_zone_name,
            story_name=story_name,
            object_id=object_id,
            limit=limit,
            num_candidates=num_candidates,
        )
        if not params:
            return {
                "error": (
                    "Provide query (or content_query), story_name/object_id, or story_zone_name."
                ),
                "status_code": 400,
            }
        try:
            async with ovaledge_client() as client:
                body = await client.get(MCP_PATH_KNOWLEDGE_SEARCH, params=params)
            if not isinstance(body, dict):
                return {"data": body}
            data = body.get("data")
            if isinstance(data, dict) and data.get("dataStories") is not None:
                stories = data.get("dataStories")
                if isinstance(stories, dict):
                    enriched = _enrich_datastory_response({"ok": True, "data": stories})
                    data = dict(data)
                    data["dataStories"] = enriched.get("data", stories)
                    out = dict(body)
                    out["data"] = data
                    if enriched.get("formattedResponse"):
                        out["formattedResponse"] = enriched["formattedResponse"]
                    return out
            return body
        except OvalEdgeError as e:
            return map_ovaledge_error(e)
