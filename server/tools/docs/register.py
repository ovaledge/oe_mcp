"""MCP tool registration for dual-corpus knowledge search."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.tools.common.annotations import READ_ONLY
from server.tools.docs.helpers import _DESC_KNOWLEDGE_SEARCH
from server.tools.docs.invocations import _invoke_knowledge_search


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        title="Search knowledge & docs",
        description=_DESC_KNOWLEDGE_SEARCH,
        annotations=READ_ONLY,
    )
    async def knowledge_search(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Your question in plain language — searches org stories and "
                    "OvalEdge product docs."
                ),
                default=None,
            ),
        ] = None,
        content_query: Annotated[
            str | None,
            Field(
                description=(
                    "Optional alternate wording focused on story body content."
                ),
                default=None,
            ),
        ] = None,
        story_zone_name: Annotated[
            str | None,
            Field(description="Limit to stories in this story zone / folder.", default=None),
        ] = None,
        story_name: Annotated[
            str | None,
            Field(description="Look up a story by its title.", default=None),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(description="Look up one data story by its catalog id.", default=None),
        ] = None,
        limit: Annotated[
            int | None,
            Field(
                description="Max product-doc results (default 10 on server; max 50 here).",
                default=None,
            ),
        ] = None,
        num_candidates: Annotated[
            int | None,
            Field(
                description=(
                    "Advanced: how many doc candidates to score (must be >= limit)."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Search organizational knowledge and OvalEdge product documentation."""
        return await _invoke_knowledge_search(
            query=query,
            content_query=content_query,
            story_zone_name=story_zone_name,
            story_name=story_name,
            object_id=object_id,
            limit=limit,
            num_candidates=num_candidates,
        )
