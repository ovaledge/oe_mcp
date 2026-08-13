"""MCP tool registration for unified access_explorer (catalog permissions + RDAM)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.constants import (
    MCP_ACCESS_INTENT_CONFIRMED_FIELD_DOC,
    MCP_ACCESS_OPERATIONS_DOC,
    MCP_ACCESS_QUERY_DIRECTIONS_DOC,
    MCP_RDAM_OBJECT_TYPES_DOC,
    MCP_RDAM_SCOPE_MODE_EXACT,
    MCP_RDAM_SCOPE_MODES_DOC,
    MCP_SOURCE_SYSTEMS_DOC,
)
from server.tools.access.helpers import _DESC_ACCESS_EXPLORER
from server.tools.access.invocations import _invoke_access_explorer
from server.tools.common.annotations import READ_ONLY

AccessQueryDirection = Literal[
    "user_to_object",
    "object_to_principals",
    "user_to_objects",
    "object_to_users",
    "browse",
]


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
            AccessQueryDirection | None,
            Field(description=MCP_ACCESS_QUERY_DIRECTIONS_DOC + "."),
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
            str | None,
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
