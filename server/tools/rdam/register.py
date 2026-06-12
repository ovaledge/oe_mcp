"""MCP tool registration for native source-system (RDAM) access."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_SOURCE_SYSTEM_ACCESS,
    MCP_QUERY_DIRECTIONS_DOC,
    MCP_RDAM_OBJECT_TYPES_DOC,
    MCP_SOURCE_SYSTEMS_DOC,
)
from server.tools.common import drop_none, map_ovaledge_error, ovaledge_client
from server.tools.rdam.helpers import (
    _DESC_SOURCE_SYSTEM_ACCESS,
    filter_user_to_objects_by_level,
    normalize_string_list,
    resolve_single_connection_id,
    resolve_single_object_type,
    validate_and_normalize_object_type,
    validate_source_system_access_args,
)


async def _invoke_source_system_access(
    source_system: str | list[str],
    query_direction: str,
    object_path: str | list[str],
    object_type: str | list[str],
    connection_id: int | list[int],
    username: str | list[str] | None,
    include_columns: bool,
    resolve_all_matches: bool,
) -> dict[str, Any]:
    err = validate_source_system_access_args(
        source_system,
        query_direction,
        username,
        object_path,
        object_type,
        connection_id,
    )
    if err is not None:
        return err
    source = normalize_string_list(source_system)[0]
    resolved_connection_id = resolve_single_connection_id(connection_id)
    assert resolved_connection_id is not None
    raw_object_type = resolve_single_object_type(object_type)
    assert raw_object_type is not None
    normalized_type, type_err = validate_and_normalize_object_type(source, raw_object_type)
    if type_err is not None:
        return type_err
    assert normalized_type is not None
    qd = query_direction.strip().lower()
    object_paths = normalize_string_list(object_path)
    usernames = normalize_string_list(username)
    wire_username: str | list[str] | None
    if not usernames:
        wire_username = None
    elif len(usernames) == 1:
        wire_username = usernames[0]
    else:
        wire_username = usernames
    wire_object_path: str | list[str] = (
        object_paths[0] if len(object_paths) == 1 else object_paths
    )
    params: dict[str, object] = drop_none(
        sourceSystem=source.strip().lower(),
        queryDirection=qd,
        username=wire_username,
        objectPath=wire_object_path,
        objectType=normalized_type,
        includeColumns=include_columns if include_columns else None,
        connectionId=resolved_connection_id,
        resolveAllMatches=resolve_all_matches if resolve_all_matches else None,
    )
    try:
        async with ovaledge_client() as client:
            result = await client.get(MCP_PATH_SOURCE_SYSTEM_ACCESS, params=params)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)
    if qd == "user_to_objects":
        return filter_user_to_objects_by_level(result, normalized_type)
    return result


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_SOURCE_SYSTEM_ACCESS)
    async def source_system_access(
        source_system: Annotated[
            Literal["redshift", "snowflake", "tableau"],
            Field(description="Native platform: " + MCP_SOURCE_SYSTEMS_DOC + "."),
        ],
        query_direction: Annotated[
            Literal["user_to_objects", "object_to_users"],
            Field(
                description=(
                    MCP_QUERY_DIRECTIONS_DOC
                    + " — infer from the question; do not ask the user to choose."
                ),
            ),
        ],
        object_path: Annotated[
            str | list[str],
            Field(
                description=(
                    "Object path(s) at the queried level (required). Redshift/Snowflake: "
                    "dbName, dbName.schema, dbName.schema.table, etc. Tableau: "
                    "Project Name or Project/Report Name. Pass one path or multiple."
                ),
            ),
        ],
        object_type: Annotated[
            str,
            Field(
                description=(
                    "RDAM native object level (required, single value only): "
                    + MCP_RDAM_OBJECT_TYPES_DOC
                    + ". E.g. database for BUSINESS, schema for SNOWFLAKE.ALERT, "
                    "table for db.schema.table. Aliases: oeschema, oetable, oecolumn."
                ),
            ),
        ],
        connection_id: Annotated[
            int | list[int],
            Field(
                description=(
                    "OvalEdge connection id for the Redshift/Snowflake/Tableau connector "
                    "(required, single value only)."
                ),
            ),
        ],
        username: Annotated[
            str | list[str] | None,
            Field(
                default=None,
                description=(
                    "Remote login(s) / service account(s). Required for user_to_objects "
                    "(what can this user access?). Pass one username or multiple. "
                    "Not used for object_to_users."
                ),
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
        return await _invoke_source_system_access(
            source_system,
            query_direction,
            object_path,
            object_type,
            connection_id,
            username,
            include_columns,
            resolve_all_matches,
        )
