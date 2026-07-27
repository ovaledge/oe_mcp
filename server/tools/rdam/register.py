"""MCP tool registration for native source-system (RDAM) access."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_ACCESS_INTENT_CONFIRMED_FIELD_DOC,
    MCP_ACCESS_INTENT_NATIVE,
    MCP_PATH_SOURCE_SYSTEM_ACCESS,
    MCP_QUERY_DIRECTIONS_DOC,
    MCP_RDAM_OBJECT_TYPE_ALL,
    MCP_RDAM_OBJECT_TYPES_DOC,
    MCP_RDAM_SCOPE_MODE_DESCENDANTS,
    MCP_RDAM_SCOPE_MODE_EXACT,
    MCP_RDAM_SCOPE_MODES_DOC,
    MCP_SOURCE_SYSTEMS_DOC,
)
from server.tools.access.disambiguation import validate_access_intent_confirmed
from server.tools.common import drop_none, map_ovaledge_error, ovaledge_client
from server.tools.common.annotations import READ_ONLY
from server.tools.common.tool_logging import logged_tool_invocation
from server.tools.rdam.helpers import (
    _DESC_SOURCE_SYSTEM_ACCESS,
    annotate_multi_connection_advisory,
    enrich_column_grants_fallback,
    enrich_table_schema_candidates,
    filter_grants_by_object_level,
    filter_grants_by_privileges,
    is_incomplete_table_object_path,
    merge_rdam_object_path,
    normalize_string_list,
    resolve_single_connection_id,
    resolve_single_object_type,
    shape_object_to_users_disambiguation,
    validate_and_normalize_object_type,
    validate_resolved_rdam_paths,
    validate_source_system_access_args,
)


@logged_tool_invocation
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
    scope_mode: str = MCP_RDAM_SCOPE_MODE_EXACT,
    fully_qualified_name: str | None = None,
    access_intent_confirmed: str | None = None,
) -> dict[str, Any]:
    intent_err = validate_access_intent_confirmed(
        access_intent_confirmed,
        query_direction=query_direction,
        expected_intent=MCP_ACCESS_INTENT_NATIVE,
    )
    if intent_err is not None:
        return intent_err
    err = validate_source_system_access_args(
        source_system,
        query_direction,
        username,
        object_path,
        object_type,
        connection_id,
        object_name=object_name,
        fully_qualified_name=fully_qualified_name,
        scope_mode=scope_mode,
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
    composed_path = merge_rdam_object_path(object_path, object_name, fully_qualified_name)
    if normalized_type is not None and composed_path is not None:
        path_err = validate_resolved_rdam_paths(
            composed_path,
            normalized_type,
            browse=qd == "browse",
        )
        if path_err is not None:
            return path_err
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
    descendants_scope = scope_mode == MCP_RDAM_SCOPE_MODE_DESCENDANTS
    browse_mode = qd == "browse"
    params: dict[str, object] = drop_none(
        sourceSystem=source.strip().lower(),
        queryDirection=qd,
        username=wire_username,
        objectPath=wire_object_path,
        objectType=None if normalized_type == MCP_RDAM_OBJECT_TYPE_ALL else normalized_type,
        includeColumns=include_columns if include_columns else None,
        connectionId=resolved_connection_id,
        resolveAllMatches=resolve_all_matches if resolve_all_matches else None,
        scopeMode=scope_mode if scope_mode != MCP_RDAM_SCOPE_MODE_EXACT else None,
    )
    if browse_mode:
        try:
            async with ovaledge_client() as client:
                return await client.get(MCP_PATH_SOURCE_SYSTEM_ACCESS, params=params)
        except OvalEdgeError as e:
            return map_ovaledge_error(e)
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
            if qd == "user_to_objects" and not descendants_scope:
                result = filter_grants_by_object_level(result, filter_level)
            elif not descendants_scope:
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
                result = await enrich_column_grants_fallback(
                    client,
                    result,
                    source,
                    resolved_connection_id,
                    composed_path,
                    normalized_type,
                )
                if filter_level is not None:
                    result = filter_grants_by_object_level(result, filter_level)
            else:
                shaped = shape_object_to_users_disambiguation(
                    result, composed_path, normalized_type
                )
                if shaped.get("ok"):
                    result = shaped
                elif initial_error is not None:
                    return map_ovaledge_error(initial_error)
            result = filter_grants_by_privileges(result, privileges)
            return annotate_multi_connection_advisory(result, resolved_connection_id)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        title="Check native source access",
        description=_DESC_SOURCE_SYSTEM_ACCESS,
        annotations=READ_ONLY,
    )
    async def source_system_access(
        source_system: Annotated[
            Literal["redshift", "snowflake", "tableau"],
            Field(description="Native platform: " + MCP_SOURCE_SYSTEMS_DOC + "."),
        ],
        query_direction: Annotated[
            Literal["user_to_objects", "object_to_users", "browse"],
            Field(
                description=(
                    MCP_QUERY_DIRECTIONS_DOC
                    + " — infer from the question. See tool description for browse vs grants."
                ),
            ),
        ],
        object_path: Annotated[
            str | list[str] | None,
            Field(
                default=None,
                description=(
                    "RDAM scope path; see docs://ovaledge/mcp_workflows. "
                    "Pair with object_type."
                ),
            ),
        ] = None,
        fully_qualified_name: Annotated[
            str | None,
            Field(
                default=None,
                description="Catalog-style dotted FQN; alias for object_path.",
            ),
        ] = None,
        object_name: Annotated[
            str | list[str] | None,
            Field(
                default=None,
                description=(
                    "Bare table/report name; composes with object_path (object_type=table)."
                ),
            ),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "RDAM object level: "
                    + MCP_RDAM_OBJECT_TYPES_DOC
                    + ". Required for browse and when object_path is set."
                ),
            ),
        ] = None,
        connection_id: Annotated[
            int | list[int] | None,
            Field(
                default=None,
                description="OvalEdge connector id (required for browse). From user only.",
            ),
        ] = None,
        username: Annotated[
            str | list[str] | None,
            Field(
                default=None,
                description="Remote login for user_to_objects; exact match, case-insensitive.",
            ),
        ] = None,
        privileges: Annotated[
            str | list[str] | None,
            Field(
                default=None,
                description="Optional post-filter on native privilege names (e.g. INSERT, SELECT).",
            ),
        ] = None,
        include_columns: Annotated[
            bool,
            Field(
                description=(
                    "Redshift only: include column-level grants (default false). "
                    "Ignored for Snowflake/Tableau and browse."
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
                    "all matches. Default false returns matchCandidates."
                ),
                default=False,
            ),
        ] = False,
        scope_mode: Annotated[
            Literal["exact", "descendants"],
            Field(
                description=MCP_RDAM_SCOPE_MODES_DOC + " (default exact).",
                default="exact",
            ),
        ] = "exact",
        access_intent_confirmed: Annotated[
            Literal["native", "catalog_acl"] | None,
            Field(
                default=None,
                description=MCP_ACCESS_INTENT_CONFIRMED_FIELD_DOC,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Native source-system access and DAM browse (see MCP tool description)."""
        return await _invoke_source_system_access(
            source_system=source_system,
            query_direction=query_direction,
            object_path=object_path,
            object_name=object_name,
            object_type=object_type,
            connection_id=connection_id,
            username=username,
            privileges=privileges,
            include_columns=include_columns,
            resolve_all_matches=resolve_all_matches,
            scope_mode=scope_mode,
            fully_qualified_name=fully_qualified_name,
            access_intent_confirmed=access_intent_confirmed,
        )
