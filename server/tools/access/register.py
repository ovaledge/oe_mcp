"""MCP tool registration for unified access_explorer (catalog permissions + RDAM)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_ACCESS_INTENT_CATALOG_ACL,
    MCP_ACCESS_INTENT_CONFIRMED_FIELD_DOC,
    MCP_ACCESS_OPERATIONS_DOC,
    MCP_OPERATION_CATALOG_ACCESS,
    MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
    MCP_PATH_ACCESS_EXPLORER,
    MCP_QUERY_DIRECTIONS_DOC,
    MCP_RDAM_OBJECT_TYPES_DOC,
    MCP_RDAM_SCOPE_MODE_EXACT,
    MCP_RDAM_SCOPE_MODES_DOC,
    MCP_SOURCE_SYSTEMS_DOC,
)
from server.tools.access.disambiguation import validate_access_intent_confirmed
from server.tools.access.helpers import (
    _DESC_ACCESS_EXPLORER,
    enrich_get_user_object_access_response,
    validate_get_user_object_access_args,
)
from server.tools.common import drop_none, map_ovaledge_error, ovaledge_client
from server.tools.common.annotations import READ_ONLY
from server.tools.common.tool_logging import logged_tool_invocation
from server.tools.rdam.register import _invoke_source_system_access


@logged_tool_invocation
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
        catalog_username = username if isinstance(username, str) or username is None else (
            username[0] if username else None
        )
        catalog_object_type = (
            object_type
            if isinstance(object_type, str) or object_type is None
            else (object_type[0] if object_type else None)
        )
        catalog_object_name = (
            object_name
            if isinstance(object_name, str) or object_name is None
            else (object_name[0] if object_name else None)
        )
        if not query_direction:
            return {"error": "query_direction is required.", "status_code": 400}
        return await _invoke_catalog_access(
            query_direction=query_direction,
            username=catalog_username,
            object_id=object_id,
            object_type=catalog_object_type,
            fully_qualified_name=fully_qualified_name,
            object_name=catalog_object_name,
            resolve_all_matches=resolve_all_matches,
            access_intent_confirmed=access_intent_confirmed,
        )
    if op == MCP_OPERATION_SOURCE_SYSTEM_ACCESS:
        if source_system is None:
            return {
                "error": "source_system is required for operation=source_system_access.",
                "status_code": 400,
            }
        if not query_direction:
            return {"error": "query_direction is required.", "status_code": 400}
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
    return {
        "error": f"operation must be one of: {MCP_ACCESS_OPERATIONS_DOC}.",
        "status_code": 400,
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Explore access permissions",
        description=_DESC_ACCESS_EXPLORER,
        annotations=READ_ONLY,
    )
    async def access_explorer(
        operation: Annotated[
            Literal["catalog_access", "source_system_access"],
            Field(description="Access layer: " + MCP_ACCESS_OPERATIONS_DOC + "."),
        ],
        query_direction: Annotated[
            str | None,
            Field(
                description=(
                    "catalog_access: user_to_object | object_to_principals. "
                    "source_system_access: " + MCP_QUERY_DIRECTIONS_DOC + "."
                ),
            ),
        ] = None,
        username: Annotated[
            str | list[str] | None,
            Field(
                description=(
                    "catalog: OvalEdge user id (user_to_object). "
                    "RDAM: remote login for user_to_objects."
                ),
            ),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(description="Catalog object id (catalog_access; from asset_explorer)."),
        ] = None,
        object_type: Annotated[
            str | list[str] | None,
            Field(
                description=(
                    "catalog: e.g. oetable, oeschema, connection. "
                    "RDAM: " + MCP_RDAM_OBJECT_TYPES_DOC + "."
                ),
            ),
        ] = None,
        fully_qualified_name: Annotated[
            str | None,
            Field(description="Catalog FQN or RDAM alias for object_path."),
        ] = None,
        object_name: Annotated[
            str | list[str] | None,
            Field(description="Catalog asset name or RDAM bare table/report name."),
        ] = None,
        resolve_all_matches: Annotated[
            bool,
            Field(description="Resolve all ambiguous name matches (default false)."),
        ] = False,
        source_system: Annotated[
            Literal["redshift", "snowflake", "tableau"] | None,
            Field(
                description="Required for source_system_access: " + MCP_SOURCE_SYSTEMS_DOC + ".",
            ),
        ] = None,
        object_path: Annotated[
            str | list[str] | None,
            Field(description="RDAM scope path; see docs://ovaledge/mcp_workflows."),
        ] = None,
        connection_id: Annotated[
            int | list[int] | None,
            Field(description="OvalEdge connector id (required for RDAM browse)."),
        ] = None,
        privileges: Annotated[
            str | list[str] | None,
            Field(description="Optional RDAM privilege post-filter (e.g. SELECT)."),
        ] = None,
        include_columns: Annotated[
            bool,
            Field(description="Redshift RDAM: include column-level grants (default false)."),
        ] = False,
        scope_mode: Annotated[
            Literal["exact", "descendants"],
            Field(description=MCP_RDAM_SCOPE_MODES_DOC + " (default exact)."),
        ] = "exact",
        access_intent_confirmed: Annotated[
            Literal["native", "catalog_acl"] | None,
            Field(
                default=None,
                description=MCP_ACCESS_INTENT_CONFIRMED_FIELD_DOC,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Unified catalog permissions and native source-system access."""
        return await _invoke_access_explorer(
            operation=operation,
            query_direction=query_direction,
            username=username,
            object_id=object_id,
            object_type=object_type,
            fully_qualified_name=fully_qualified_name,
            object_name=object_name,
            resolve_all_matches=resolve_all_matches,
            source_system=source_system,
            object_path=object_path,
            connection_id=connection_id,
            privileges=privileges,
            include_columns=include_columns,
            scope_mode=scope_mode or MCP_RDAM_SCOPE_MODE_EXACT,
            access_intent_confirmed=access_intent_confirmed,
        )
