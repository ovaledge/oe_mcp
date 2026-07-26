"""Helpers for knowledge search MCP tool (data stories + platform docs)."""

from __future__ import annotations

from typing import Any

from server.constants import MCP_PATH_KNOWLEDGE_SEARCH
from server.tools.common.descriptions import classify_tool_desc

_DESC_KNOWLEDGE_SEARCH = classify_tool_desc(
    "Search organizational knowledge and OvalEdge product documentation together. "
    "Fans out to data stories and platform docs; returns whatever matches "
    "(dataStories and/or platformDocs sections).\n\n"
    f"Backend: GET {MCP_PATH_KNOWLEDGE_SEARCH}\n\n"
    "**Prefer query** as the shared text for both corpora. content_query is an optional "
    "story alias (if only query is set, stories use query too). "
    "Story targeting: story_zone_name, story_name, object_id. "
    "Docs tuning: limit, num_candidates (client ensures numCandidates >= limit).\n\n"
    "Present formattedResponse when provided. For story answers, keep storyCitation as the "
    "first line. Not a catalog discovery tool — use asset_explorer for tables/terms/tags."
)

# Backward-compatible alias used by older imports/tests during cutover.
_DESC_DOCS = _DESC_KNOWLEDGE_SEARCH


def knowledge_search_params(
    query: str | None,
    content_query: str | None,
    story_zone_name: str | None,
    story_name: str | None,
    object_id: int | None,
    limit: int | None,
    num_candidates: int | None,
) -> dict[str, Any]:
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


def search_platform_docs_params(
    query: str,
    limit: int | None,
    num_candidates: int | None,
) -> dict[str, Any]:
    """Legacy helper name — maps to knowledge_search docs params."""
    return knowledge_search_params(
        query=query,
        content_query=None,
        story_zone_name=None,
        story_name=None,
        object_id=None,
        limit=limit,
        num_candidates=num_candidates,
    )
