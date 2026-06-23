"""Helpers for platform documentation search MCP tool."""

from __future__ import annotations

from typing import Any

from server.constants import MCP_PATH_SEARCH_PLATFORM_DOCS
from server.tools.common.descriptions import classify_tool_desc

_DESC_DOCS = classify_tool_desc(
    "Semantic search over OvalEdge / EDGI **product** documentation (RAG: embedded query, "
    "vector KNN in Elasticsearch). Use for **how-to** questions about OvalEdge features, "
    "UI, and configuration.\n\n"
    "**Do not use for organizational knowledge** (internal policies, playbooks, standards, "
    "onboarding narratives, or domain context documented in OvalEdge data stories). "
    "For that, use lookup_datastory (content_query) or the organizational_knowledge "
    "workflow prompt.\n\n"
    f"Backend: GET {MCP_PATH_SEARCH_PLATFORM_DOCS} "
    "(query params: query, optional limit, optional numCandidates).\n\n"
    "The API requires numCandidates >= limit when both apply; if you pass limit only, "
    "this client sets numCandidates automatically (at least 128, capped at 512).\n\n"
    "If the tool returns empty hits, the index may be empty or the query had no matches — "
    "that is not an MCP connectivity failure."
)


def search_platform_docs_params(
    query: str,
    limit: int | None,
    num_candidates: int | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"query": query}
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
