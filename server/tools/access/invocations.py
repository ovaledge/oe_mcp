"""Invocation logic for access_explorer (catalog permissions + RDAM)."""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError
from server.constants import (
    MCP_ACCESS_INTENT_CATALOG_ACL,
    MCP_ACCESS_OPERATIONS_DOC,
    MCP_OPERATION_CATALOG_ACCESS,
    MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
    MCP_PATH_ACCESS_EXPLORER,
)
from server.tools.access.disambiguation import validate_access_intent_confirmed
from server.tools.access.helpers import (
    annotate_catalog_fallback,
    catalog_direction_for_unsupported_dam,
    catalog_object_type_for_fallback,
    enrich_get_user_object_access_response,
    is_dam_connector_unsupported,
    strip_catalog_fallback,
    validate_get_user_object_access_args,
)
from server.tools.common import drop_none, error_payload, map_ovaledge_error, ovaledge_client
from server.tools.common.tool_logging import logged_tool_invocation
from server.tools.rdam.invocations import _invoke_source_system_access


async def _invoke_catalog_access(
    query_direction: str,
    username: str | None,
    object_id: int | None,
    object_type: str | None,
    fully_qualified_name: str | None,
    object_name: str | None,
    resolve_all_matches: bool,
    access_intent_confirmed: str | None = None,
) -> dict[str, Any]:
    intent_err = validate_access_intent_confirmed(
        access_intent_confirmed,
        query_direction=query_direction,
        expected_intent=MCP_ACCESS_INTENT_CATALOG_ACL,
    )
    if intent_err is not None:
        return intent_err
    err = validate_get_user_object_access_args(
        query_direction,
        username,
        object_id,
        object_type,
        fully_qualified_name,
        object_name,
    )
    if err is not None:
        return err
    params: dict[str, object] = drop_none(
        operation=MCP_OPERATION_CATALOG_ACCESS,
        queryDirection=query_direction.strip().lower(),
        username=username.strip() if username else None,
        objectId=object_id,
        objectType=object_type.strip() if object_type else None,
        fullyQualifiedName=fully_qualified_name.strip() if fully_qualified_name else None,
        objectName=object_name.strip() if object_name else None,
        resolveAllMatches=resolve_all_matches if resolve_all_matches else None,
    )
    try:
        async with ovaledge_client() as client:
            result = await client.get(MCP_PATH_ACCESS_EXPLORER, params=params)
            return enrich_get_user_object_access_response(result)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


def _first_str(value: str | list[str] | None) -> str | None:
    if isinstance(value, str) or value is None:
        return value
    return value[0] if value else None


def _catalog_fqns_for_fallback(
    effective_fqn: str | None,
    effective_object_path: str | list[str] | None,
) -> list[str]:
    paths: list[str] = []
    if isinstance(effective_object_path, list):
        seen: set[str] = set()
        for item in effective_object_path:
            if not isinstance(item, str):
                continue
            token = item.strip()
            if token and token not in seen:
                seen.add(token)
                paths.append(token)
        if len(paths) > 1:
            return paths
    if isinstance(effective_fqn, str) and effective_fqn.strip():
        return [effective_fqn.strip()]
    if paths:
        return paths
    if isinstance(effective_object_path, str):
        token = effective_object_path.strip()
        return [token] if token else []
    return []


def _merge_catalog_access_results(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    ok_results = [item for item in results if isinstance(item, dict) and item.get("ok")]
    if not ok_results:
        return None
    if len(ok_results) == 1:
        return ok_results[0]
    objects: list[Any] = []
    for item in ok_results:
        data = item.get("data")
        if data is not None:
            objects.append(data)
    merged = dict(ok_results[0])
    query_direction = None
    if objects and isinstance(objects[0], dict):
        query_direction = objects[0].get("queryDirection")
    merged["data"] = {"queryDirection": query_direction, "objects": objects}
    return merged


@logged_tool_invocation
async def _invoke_access_explorer(
    operation: str,
    query_direction: str | None,
    username: str | list[str] | None,
    object_id: int | None,
    object_type: str | list[str] | None,
    fully_qualified_name: str | None,
    object_name: str | list[str] | None,
    resolve_all_matches: bool,
    source_system: str | list[str] | None,
    object_path: str | list[str] | None,
    connection_id: int | list[int] | None,
    privileges: str | list[str] | None,
    include_columns: bool,
    scope_mode: str,
    access_intent_confirmed: str | None,
) -> dict[str, Any]:
    op = (operation or "").strip().lower()
    if op == MCP_OPERATION_CATALOG_ACCESS:
        if not query_direction:
            return error_payload("query_direction is required.")
        return await _invoke_catalog_access(
            query_direction=query_direction,
            username=_first_str(username),
            object_id=object_id,
            object_type=_first_str(object_type),
            fully_qualified_name=fully_qualified_name,
            object_name=_first_str(object_name),
            resolve_all_matches=resolve_all_matches,
            access_intent_confirmed=access_intent_confirmed,
        )
    if op == MCP_OPERATION_SOURCE_SYSTEM_ACCESS:
        if source_system is None:
            return error_payload("source_system is required for operation=source_system_access.")
        if not query_direction:
            return error_payload("query_direction is required.")
        result = await _invoke_source_system_access(
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
            object_id=object_id,
            access_intent_confirmed=access_intent_confirmed,
        )
        return strip_catalog_fallback(
            await _continue_catalog_access_if_dam_unsupported(
                result,
                query_direction=query_direction,
                object_id=object_id,
                object_type=object_type,
                fully_qualified_name=fully_qualified_name,
                object_name=object_name,
                object_path=object_path,
                resolve_all_matches=resolve_all_matches,
            )
        )
    return error_payload(f"operation must be one of: {MCP_ACCESS_OPERATIONS_DOC}.")


async def _continue_catalog_access_if_dam_unsupported(
    result: dict[str, Any],
    *,
    query_direction: str | None,
    object_id: int | None,
    object_type: str | list[str] | None,
    fully_qualified_name: str | None,
    object_name: str | list[str] | None,
    object_path: str | list[str] | None,
    resolve_all_matches: bool,
) -> dict[str, Any]:
    if not is_dam_connector_unsupported(result):
        return result
    catalog_qd = catalog_direction_for_unsupported_dam(query_direction)
    if catalog_qd is None:
        return result
    fallback_ctx = result.get("_catalog_fallback")
    result = strip_catalog_fallback(result)
    if not isinstance(fallback_ctx, dict):
        fallback_ctx = {}
    effective_object_id = fallback_ctx.get("object_id") or object_id
    effective_object_type = fallback_ctx.get("object_type") or object_type
    effective_fqn = fallback_ctx.get("fully_qualified_name") or fully_qualified_name
    effective_object_name = fallback_ctx.get("object_name") or object_name
    effective_object_path = fallback_ctx.get("object_path") or object_path
    catalog_type = catalog_object_type_for_fallback(effective_object_type)
    catalog_name = _first_str(effective_object_name)
    catalog_fqns = _catalog_fqns_for_fallback(effective_fqn, effective_object_path)
    has_id = effective_object_id is not None and effective_object_id > 0 and bool(catalog_type)
    has_fqn = bool(catalog_fqns)
    has_name = bool(catalog_name and str(catalog_name).strip())
    if not (has_id or has_fqn or has_name):
        return result
    if has_id or not has_fqn or len(catalog_fqns) == 1:
        fallback = await _invoke_catalog_access(
            query_direction=catalog_qd,
            username=None,
            object_id=effective_object_id if has_id else None,
            object_type=catalog_type if has_id else None,
            fully_qualified_name=None if has_id else (catalog_fqns[0] if has_fqn else None),
            object_name=None if has_id or has_fqn else catalog_name,
            resolve_all_matches=resolve_all_matches,
            access_intent_confirmed=MCP_ACCESS_INTENT_CATALOG_ACL,
        )
        if fallback.get("ok"):
            return annotate_catalog_fallback(fallback)
        return result
    fallbacks: list[dict[str, Any]] = []
    for catalog_fqn in catalog_fqns:
        fallbacks.append(
            await _invoke_catalog_access(
                query_direction=catalog_qd,
                username=None,
                object_id=None,
                object_type=None,
                fully_qualified_name=catalog_fqn,
                object_name=None,
                resolve_all_matches=resolve_all_matches,
                access_intent_confirmed=MCP_ACCESS_INTENT_CATALOG_ACL,
            )
        )
    merged = _merge_catalog_access_results(fallbacks)
    if merged is not None:
        return annotate_catalog_fallback(merged)
    return result
