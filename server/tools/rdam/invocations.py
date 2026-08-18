"""Invocation logic for native source-system access (used by access_explorer)."""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError
from server.constants import (
    MCP_ACCESS_INTENT_NATIVE,
    MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
    MCP_PATH_ACCESS_EXPLORER,
    MCP_RDAM_OBJECT_TYPE_ALL,
    MCP_RDAM_SCOPE_MODE_DESCENDANTS,
    MCP_RDAM_SCOPE_MODE_EXACT,
)
from server.tools.access.disambiguation import validate_access_intent_confirmed
from server.tools.common import drop_none, map_ovaledge_error, ovaledge_client
from server.tools.rdam.catalog_resolve import (
    CatalogResolvedScope,
    resolve_rdam_scope_via_asset_explorer,
    should_resolve_via_asset_explorer,
)
from server.tools.rdam.helpers import (
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
    object_id: int | None = None,
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
        object_id=object_id,
        scope_mode=scope_mode,
    )
    if err is not None:
        return err
    source = normalize_string_list(source_system)[0]
    resolved_connection_id = resolve_single_connection_id(connection_id)
    raw_object_type = resolve_single_object_type(object_type)
    resolved_object_id = object_id if object_id is not None and object_id > 0 else None
    resolved_object_name = object_name
    resolved_fqn = fully_qualified_name
    qd = query_direction.strip().lower()
    composed_path = merge_rdam_object_path(object_path, object_name, fully_qualified_name)
    if resolved_object_id is not None and not normalize_string_list(object_path):
        composed_path = None
    normalized_type: str | None = None
    if raw_object_type is not None:
        normalized_type, type_err = validate_and_normalize_object_type(source, raw_object_type)
        if type_err is not None:
            return type_err
    if should_resolve_via_asset_explorer(
        qd,
        object_id,
        object_type,
        object_path,
        object_name,
        fully_qualified_name,
        resolved_connection_id,
    ):
        try:
            async with ovaledge_client() as client:
                resolved = await resolve_rdam_scope_via_asset_explorer(
                    client,
                    source_system=source,
                    object_id=object_id,
                    object_type=raw_object_type,
                    object_name=object_name,
                    fully_qualified_name=fully_qualified_name,
                    resolve_all_matches=resolve_all_matches,
                    connection_id=resolved_connection_id,
                    object_path=object_path,
                )
        except OvalEdgeError:
            resolved = None
        if isinstance(resolved, CatalogResolvedScope):
            composed_path = resolved.object_path
            if resolved.object_type:
                raw_object_type = resolved.object_type
            if resolved.connection_id is not None:
                resolved_connection_id = resolved.connection_id
            if resolved.object_id is not None:
                resolved_object_id = resolved.object_id
            if resolved.fully_qualified_name:
                resolved_fqn = resolved.fully_qualified_name
            if resolved.object_name:
                resolved_object_name = resolved.object_name
            if resolved.object_type:
                normalized_type, type_err = validate_and_normalize_object_type(
                    source, resolved.object_type
                )
                if type_err is not None:
                    return type_err
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
    names = normalize_string_list(resolved_object_name)
    wire_object_name = names[0] if names else None
    wire_fqn = resolved_fqn.strip() if resolved_fqn else None
    descendants_scope = scope_mode == MCP_RDAM_SCOPE_MODE_DESCENDANTS
    browse_mode = qd == "browse"
    params: dict[str, object] = drop_none(
        operation=MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
        sourceSystem=source.strip().lower(),
        queryDirection=qd,
        username=wire_username,
        objectId=(
            resolved_object_id
            if resolved_object_id is not None and resolved_object_id > 0
            else None
        ),
        fullyQualifiedName=wire_fqn,
        objectName=wire_object_name if wire_object_path is None else None,
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
                return await client.get(MCP_PATH_ACCESS_EXPLORER, params=params)
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
                result = await client.get(MCP_PATH_ACCESS_EXPLORER, params=params)
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
