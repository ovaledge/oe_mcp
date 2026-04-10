from typing import Any

from fastmcp import FastMCP

from server.client import OvalEdgeClient, OvalEdgeError


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def lookup_business_term(
        query: str,
        domain: str | None = None,
        include_related: bool = True,
        include_data_objects: bool = True,
        status: str = "PUBLISHED",
    ) -> dict[str, Any]:
        """
        Searches the OvalEdge Business Glossary for terms matching a
        keyword or business concept.

        Returns the organisational definition — not a generic one.
        Includes the full OvalEdge relationship vocabulary (20+ types):
        synonym, contains, calculates, calculates-from, filtered-by,
        is-a-type-of, defines, contrasts-with, qualifies, and custom org types.

        Also returns all physical data objects governed by the term
        and any term-inherited governance properties (masking, classification).

        Args:
            query: Business term name or concept (e.g. 'churn rate', 'CLV')
            domain: Filter to a specific business domain
            include_related: Include related terms with relationship types
            include_data_objects: Include associated physical assets
            status: PUBLISHED (default), DRAFT, ALL

        TODO: confirm endpoint path from OvalEdge API docs
        """
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    "/api/mcp/glossary/search",  # TODO: confirm path
                    params={
                        "q": query,
                        "domain": domain,
                        "includeRelated": include_related,
                        "includeDataObjects": include_data_objects,
                        "status": status,
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
