"""MCP tool registration for platform documentation search."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import MCP_PATH_SEARCH_PLATFORM_DOCS
from server.tools.common import map_ovaledge_error, ovaledge_client
from server.tools.docs.helpers import _DESC_DOCS, search_platform_docs_params


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
        params = search_platform_docs_params(query, limit, num_candidates)
        try:
            async with ovaledge_client() as client:
                return await client.get(MCP_PATH_SEARCH_PLATFORM_DOCS, params=params)
        except OvalEdgeError as e:
            return map_ovaledge_error(e)
