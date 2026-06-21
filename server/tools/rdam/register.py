"""MCP tool registration for native source-system (RDAM) access."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_SOURCE_SYSTEM_ACCESS,
    MCP_QUERY_DIRECTIONS_DOC,
    MCP_RDAM_OBJECT_TYPE_ALL,
    MCP_RDAM_OBJECT_TYPES_DOC,
    MCP_SOURCE_SYSTEMS_DOC,
)
from server.tools.common import drop_none, map_ovaledge_error, ovaledge_client
from server.tools.rdam.helpers import (
    _DESC_SOURCE_SYSTEM_ACCESS,
    annotate_multi_connection_advisory,
    compose_object_path,
    enrich_table_schema_candidates,
    filter_grants_by_privileges,
    filter_user_to_objects_by_level,
    is_incomplete_table_object_path,
    normalize_string_list,
    resolve_single_connection_id,
    resolve_single_object_type,
    shape_object_to_users_disambiguation,
    validate_and_normalize_object_type,
    validate_source_system_access_args,
)


async def _invoke_source_system_access(
    source_system: str | list[str],
    query_direction: str,
    object_path: str | list[str] | None,
    object_name: str | list[str] | None,
    object_type: str | list[str] | None,
    connection_id: int | list[int] | None,
    username: str | list[str] | None,
    privileges: str | list[str] | None,
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
    raw_object_type = resolve_single_object_type(object_type)
    normalized_type: str | None = None
    if raw_object_type is not None:
        normalized_type, type_err = validate_and_normalize_object_type(source, raw_object_type)
        if type_err is not None:
            return type_err
    qd = query_direction.strip().lower()
    composed_path = compose_object_path(object_path, object_name)
    object_paths = normalize_string_list(composed_path)
    usernames = normalize_string_list(username)
    wire_username: str | list[str] | None
    if not usernames:
        wire_username = None
    elif len(usernames) == 1:
        wire_username = usernames[0]
    else:
        wire_username = usernames
    wire_object_path: str | list[str] | None
    if not object_paths:
        wire_object_path = None
    elif len(object_paths) == 1:
        wire_object_path = object_paths[0]
    else:
        wire_object_path = object_paths
    params: dict[str, object] = drop_none(
        sourceSystem=source.strip().lower(),
        queryDirection=qd,
        username=wire_username,
        objectPath=wire_object_path,
        objectType=None if normalized_type == MCP_RDAM_OBJECT_TYPE_ALL else normalized_type,
        includeColumns=include_columns if include_columns else None,
        connectionId=resolved_connection_id,
        resolveAllMatches=resolve_all_matches if resolve_all_matches else None,
    )
    incomplete_table_lookup = (
        qd == "object_to_users"
        and normalized_type == "table"
        and composed_path is not None
        and len(normalize_string_list(composed_path)) == 1
        and is_incomplete_table_object_path(normalize_string_list(composed_path)[0])
        and not resolve_all_matches
    )
    filter_level = (
        None
        if normalized_type in (None, MCP_RDAM_OBJECT_TYPE_ALL)
        else normalized_type
    )
    try:
        async with ovaledge_client() as client:
            initial_error: OvalEdgeError | None = None
            try:
                result = await client.get(MCP_PATH_SOURCE_SYSTEM_ACCESS, params=params)
            except OvalEdgeError as e:
                if not incomplete_table_lookup:
                    return map_ovaledge_error(e)
                initial_error = e
                result = {"ok": False, "message": str(e), "data": None}
            if qd == "user_to_objects":
                result = filter_user_to_objects_by_level(result, filter_level)
            else:
                shaped = shape_object_to_users_disambiguation(
                    result, composed_path, normalized_type
                )
                enriched = await enrich_table_schema_candidates(
                    client,
                    shaped,
                    source,
                    resolved_connection_id,
                    composed_path,
                    qd,
                    normalized_type,
                    resolve_all_matches,
                    grants_hint_result=result,
                )
                if enriched.get("ok"):
                    result = enriched
                elif initial_error is not None:
                    return map_ovaledge_error(initial_error)
                else:
                    result = enriched
            result = filter_grants_by_privileges(result, privileges)
            return annotate_multi_connection_advisory(result, resolved_connection_id)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


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
            str | list[str] | None,
            Field(
                default=None,
                description=(
                    "Query scope. Redshift/Snowflake: dbName, dbName.schema, dbName.schema.table, "
                    "etc. Tableau: Project Name or Project/Report Name. For \"what tables can user "
                    "X access?\" with connection_id, omit object_path (all tables on connector). "
                    "Narrow with dbName.schema or dbName when the user names a schema/database. "
                    "When the user names a table without schema, pass table name (or dbName.table) "
                    "only — if multiple schemas match, ask the user to pick schema before retrying "
                    "with dbName.schema.table. Never guess a schema or full table path."
                ),
            ),
        ] = None,
        object_name: Annotated[
            str | list[str] | None,
            Field(
                default=None,
                description=(
                    "Bare table name when database/schema scope is in object_path. "
                    "Composed as object_path.object_name (e.g. object_path=prod_db + "
                    "object_name=orders → prod_db.orders). Use with object_type=table."
                ),
            ),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "RDAM native object level (optional, single value only): "
                    + MCP_RDAM_OBJECT_TYPES_DOC
                    + ". E.g. database for BUSINESS, schema for SNOWFLAKE.ALERT, "
                    "table for db.schema.table. Aliases: oeschema, oetable, oecolumn."
                ),
            ),
        ] = None,
        connection_id: Annotated[
            int | list[int] | None,
            Field(
                default=None,
                description=(
                    "OvalEdge connection id for the Redshift/Snowflake/Tableau connector "
                    "(optional, single value only). Must come from the user — do not probe or "
                    "discover connection ids."
                ),
            ),
        ] = None,
        username: Annotated[
            str | list[str] | None,
            Field(
                default=None,
                description=(
                    "Remote login(s) / service account(s) for user_to_objects "
                    "(what can this user access?). Pass one username or multiple. "
                    "Exact match, case-insensitive — not LIKE/substring search. "
                    "Not used for object_to_users."
                ),
            ),
        ] = None,
        privileges: Annotated[
            str | list[str] | None,
            Field(
                default=None,
                description=(
                    "Optional response filter: keep grants whose native privileges include any "
                    "listed value (e.g. INSERT, UPDATE, DELETE for write-access checks). "
                    "Case-insensitive."
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
            object_name,
            object_type,
            connection_id,
            username,
            privileges,
            include_columns,
            resolve_all_matches,
        )
