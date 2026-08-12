"""Invocation logic for knowledge_search."""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError
from server.constants import MCP_PATH_KNOWLEDGE_SEARCH
from server.tools.common import map_ovaledge_error, ovaledge_client
from server.tools.common.tool_logging import logged_tool_invocation
from server.tools.docs.helpers import knowledge_search_params
from server.tools.governance.datastory_helpers import _enrich_datastory_response


@logged_tool_invocation
async def _invoke_knowledge_search(
    query: str | None = None,
    content_query: str | None = None,
    story_zone_name: str | None = None,
    story_name: str | None = None,
    object_id: int | None = None,
    limit: int | None = None,
    num_candidates: int | None = None,
) -> dict[str, Any]:
    """GET knowledge-search — dual corpus (data stories + platform docs)."""
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
