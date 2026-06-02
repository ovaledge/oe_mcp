"""MCP tool registration for native source-system (RDAM) access."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_SOURCE_SYSTEM_ACCESS,
    MCP_QUERY_DIRECTIONS_DOC,
    MCP_SOURCE_SYSTEMS_DOC,
)
from server.tools.common import drop_none, map_ovaledge_error, ovaledge_client, strip_or_none
from server.tools.rdam.helpers import (
    _DESC_USER_OBJECT_ACCESS,
    validate_user_object_access_args,
)


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_USER_OBJECT_ACCESS)
    async def user_object_access(
        source_system: Annotated[
            Literal["redshift", "snowflake", "tableau"],
            Field(description="Native platform: " + MCP_SOURCE_SYSTEMS_DOC + "."),
        ],
        query_direction: Annotated[
            Literal["user_to_objects", "object_to_users"],
            Field(description=MCP_QUERY_DIRECTIONS_DOC),
        ],
        username: Annotated[
            str | None,
            Field(
                description="Remote login / service account (required for user_to_objects).",
                default=None,
            ),
        ] = None,
        object_path: Annotated[
            str | None,
            Field(
                description=(
                    "Fully qualified object path (required for object_to_users). "
                    "See tool description for per-platform formats."
                ),
                default=None,
            ),
        ] = None,
        include_columns: Annotated[
            bool,
            Field(
                description=(
                    "Redshift only: include column-level grants (default false). "
                    "Ignored for Snowflake/Tableau."
                ),
                default=False,
            ),
        ] = False,
        connection_id: Annotated[
            int | None,
            Field(
                description=(
                    "Optional OvalEdge connection id to scope the query when multiple "
                    "connections share the same server type."
                ),
                default=None,
            ),
        ] = None,
        resolve_all_matches: Annotated[
            bool,
            Field(
                description=(
                    "When object_path matches multiple catalog objects (same name across "
                    "connections/schemas/tables/columns or Tableau projects/reports), return "
                    "native access for all matches. Default false returns matchCandidates."
                ),
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Native source-system access (see MCP tool description)."""
        err = validate_user_object_access_args(
            source_system, query_direction, username, object_path
        )
        if err is not None:
            return err
        params: dict[str, object] = drop_none(
            sourceSystem=source_system.strip().lower(),
            queryDirection=query_direction.strip().lower(),
            username=strip_or_none(username),
            objectPath=strip_or_none(object_path),
            includeColumns=include_columns if include_columns else None,
            connectionId=connection_id,
            resolveAllMatches=resolve_all_matches if resolve_all_matches else None,
        )
        try:
            async with ovaledge_client() as client:
                return await client.get(MCP_PATH_SOURCE_SYSTEM_ACCESS, params=params)
        except OvalEdgeError as e:
            return map_ovaledge_error(e)
