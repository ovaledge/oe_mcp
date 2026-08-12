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
    enrich_get_user_object_access_response,
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
    return error_payload(f"operation must be one of: {MCP_ACCESS_OPERATIONS_DOC}.")
