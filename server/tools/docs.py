from typing import Any

from fastmcp import FastMCP

from server.client import OvalEdgeClient, OvalEdgeError


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_platform_docs(
        query: str,
        top_k: int = 5,
        section_filter: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieves relevant sections from OvalEdge product documentation
        (docs.ovaledge.com) using semantic search (RAG).

        Answers how-to questions about OvalEdge features, platform
        terminology, and governance processes. Returns top-k chunks
        with source citations so answers can be attributed correctly.

        No user-level RBAC on this tool — documentation is public.

        Args:
            query: User question in natural language
            top_k: Number of doc chunks to return (default 5, max 10)
            section_filter: Narrow to: data-catalog, business-glossary,
                           data-quality, lineage, governance, askedgi

        TODO: confirm endpoint path from OvalEdge API docs
        """
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    "/api/mcp/docs/search",  # TODO: confirm path
                    params={
                        "q": query,
                        "topK": min(top_k, 10),
                        "section": section_filter,
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
