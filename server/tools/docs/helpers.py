"""Helpers for knowledge_search MCP tool (data stories + platform docs)."""

from __future__ import annotations

from typing import Any

from server.constants import MCP_PATH_KNOWLEDGE_SEARCH
from server.tools.common.descriptions import classify_tool_desc

_DESC_KNOWLEDGE_SEARCH = classify_tool_desc(
    "**Search knowledge & docs** (`knowledge_search`) — find organizational policies, "
    "playbooks, and data stories, plus OvalEdge product how-to documentation, in one "
    "search. Not for finding physical tables or files — use asset_explorer for catalog "
    "discovery.\n\n"
    f"Backend: GET {MCP_PATH_KNOWLEDGE_SEARCH}\n\n"
    "Prefer query as the shared question text. content_query is an optional story-content "
    "alias. Narrow stories with story_zone_name, story_name, or object_id. "
    "Docs tuning: limit, num_candidates (client ensures numCandidates >= limit).\n\n"
    "Present formattedResponse when provided; for story answers keep storyCitation as the "
    "first line. Playbooks: docs://ovaledge/mcp_workflows; guide: docs://ovaledge/governance."
)


def knowledge_search_params(
    query: str | None,
    content_query: str | None,
    story_zone_name: str | None,
    story_name: str | None,
    object_id: int | None,
    limit: int | None,
    num_candidates: int | None,
) -> dict[str, Any]:
    """Build GET /knowledge-search query params (omit empties)."""
    params: dict[str, Any] = {}
    if query is not None and str(query).strip():
        params["query"] = str(query).strip()
    if content_query is not None and str(content_query).strip():
        params["contentQuery"] = str(content_query).strip()
    if story_zone_name is not None and str(story_zone_name).strip():
        params["storyZoneName"] = str(story_zone_name).strip()
    if story_name is not None and str(story_name).strip():
        params["storyName"] = str(story_name).strip()
    if object_id is not None and object_id > 0:
        params["objectId"] = object_id
    if limit is not None:
        lim = min(max(limit, 1), 50)
        params["limit"] = lim
        if num_candidates is None:
            params["numCandidates"] = min(512, max(128, lim))
        else:
            params["numCandidates"] = min(512, max(num_candidates, lim))
    elif num_candidates is not None:
        params["numCandidates"] = min(512, max(1, num_candidates))
    return params
