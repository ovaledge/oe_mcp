from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import MCP_PATH_SEARCH_PLATFORM_DOCS

_DESC_DOCS = (
    "Semantic search over OvalEdge / EDGI platform documentation (RAG: embedded query, "
    "vector KNN in Elasticsearch).\n\n"
    f"Backend: GET {MCP_PATH_SEARCH_PLATFORM_DOCS} "
    "(query params: query, optional limit, optional numCandidates).\n\n"
    "The API requires numCandidates >= limit when both apply; if you pass limit only, "
    "this client sets numCandidates automatically (at least 128, capped at 512).\n\n"
    "If the tool returns empty hits, the index may be empty or the query had no matches — "
    "that is not an MCP connectivity failure."
)


def _search_platform_docs_params(
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


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_DOCS)
    async def search_platform_docs(
        query: Annotated[
            str,
            Field(description="Natural-language question or keywords for documentation search."),
        ],
        limit: Annotated[
            int | None,
            Field(
                description=(
                    "Max hits to return (maps to API limit; default 10 on server if omitted). "
                    "This client caps at 50."
                ),
                default=None,
            ),
        ] = None,
        num_candidates: Annotated[
            int | None,
            Field(
                description=(
                    "KNN numCandidates (optional). Must be >= limit if both sent; "
                    "client enforces that. If omitted while limit is set, client picks "
                    "max(128, limit) capped at 512."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Platform docs search (see MCP tool description)."""
        params = _search_platform_docs_params(query, limit, num_candidates)
        try:
            async with OvalEdgeClient() as client:
                return await client.get(MCP_PATH_SEARCH_PLATFORM_DOCS, params=params)
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
