from typing import Any

from fastmcp import FastMCP

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import MCP_PATH_SEARCH_PLATFORM_DOCS


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_platform_docs(
        query: str,
        limit: int | None = None,
        num_candidates: int | None = None,
    ) -> dict[str, Any]:
        f"""
        Semantic search over EDGI / platform documentation chunks (Elasticsearch + vector KNN).

        limit: optional, default 10, max 50 (maps to k).
        num_candidates: optional, must be >= limit when both set (server caps at 512).

        GET {MCP_PATH_SEARCH_PLATFORM_DOCS}
        """
        params: dict[str, Any] = {"query": query}
        if limit is not None:
            params["limit"] = min(max(limit, 1), 50)
        if num_candidates is not None:
            params["numCandidates"] = num_candidates
        try:
            async with OvalEdgeClient() as client:
                return await client.get(MCP_PATH_SEARCH_PLATFORM_DOCS, params=params)
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
