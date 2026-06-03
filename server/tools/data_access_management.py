"""
Native source-system access MCP tools (NFD-48785).

Queries OvalEdge-harvested RDAM privilege metadata — not OvalEdge catalog ACLs
(see get_user_object_access when that ships) and not catalog data-sources.

Backend: GET /api/v1/mcp/source-system-access
  → McpSourceSystemAccessReadService (oe-api) over rdam_*privilege tables.
  Instance/Connector Data Access Admin checks run in that service (RdamValidationDao),
  not via separate MCP REST routes.
"""

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_DAA_SCOPE_DOC,
    MCP_OBJECT_PATH_FORMATS_DOC,
    MCP_OBJECT_PATH_PARTIAL_DOC,
    MCP_PATH_SOURCE_SYSTEM_ACCESS,
    MCP_QUERY_DIRECTIONS,
    MCP_QUERY_DIRECTIONS_DOC,
    MCP_SOURCE_SYSTEMS,
    MCP_SOURCE_SYSTEMS_DOC,
)
from server.tools.common import ovaledge_client

_DESC_GET_SOURCE_SYSTEM_ACCESS = (
    "Resolve **native** access grants harvested from Redshift, Snowflake, or Tableau — "
    "independent of OvalEdge catalog permissions.\n\n"
    "Use for questions like:\n"
    '- "What tables can svc_analytics query in Redshift?"\n'
    '- "Who has native access to prod_db.public.orders?"\n'
    '- "Which Snowflake roles give john.doe access?"\n'
    '- "Who can view the Revenue Dashboard in Tableau?"\n\n'
    f"Backend: GET {MCP_PATH_SOURCE_SYSTEM_ACCESS}\n\n"
    "**Not** OvalEdge `get_user_object_access` (catalog ACL layer).\n\n"
    "**source_system** (required): "
    + MCP_SOURCE_SYSTEMS_DOC
    + ".\n\n"
    "**query_direction** (required): "
    + MCP_QUERY_DIRECTIONS_DOC
    + ".\n"
    "- user_to_objects: provide **username** (service account or login).\n"
    "- object_to_users: provide **object_path** (see levels below).\n\n"
    "**Grant models:**\n"
    "- Redshift: direct user, group membership, role assignment (all returned).\n"
    "- Snowflake: role assignment only (no direct user grants / groups).\n"
    "- Tableau: direct user/service account on project/report.\n\n"
    "**object_path** formats:\n"
    "- Redshift/Snowflake table: `database.schema.table` (e.g. prod_db.public.orders).\n"
    "- Redshift/Snowflake schema: `database.schema`.\n"
    "- Redshift/Snowflake database: `database`.\n"
    "- Redshift column (opt-in): `database.schema.table.column` — set include_columns=true.\n"
    "- Tableau project: `Project Name` or path segment.\n"
    "- Tableau report: `Project/Report Name`.\n\n"
    + MCP_OBJECT_PATH_FORMATS_DOC
    + "\n\n"
    "Response includes **grant_mechanism** per entry: direct | group | role, **principal_type** "
    "(user | role | group), native **privileges** (SELECT, INSERT, …), and "
    "**contributing_group** / **contributing_role** when access is indirect.\n\n"
    "**summary** (server-computed): `totalGrants`, `byObjectLevel` "
    "(database/schema/table/column for RS/SF; project/report for Tableau), "
    "`byGrantMechanism` (direct/group/role).\n\n"
    "Partial-path disambiguation (**object_to_users** and optional **object_path** on "
    "**user_to_objects**): when the path is not exact and multiple assets match, returns "
    "**matchCandidates** or **resolve_all_matches=true** (max 50).\n"
    + MCP_OBJECT_PATH_PARTIAL_DOC
    + " "
    "Tableau uses `rdam_reportgroup_privilege` (project) and `rdam_report_privilege` "
    "(report).\n\n"
    + MCP_DAA_SCOPE_DOC
    + "\n\n"
    "Read-only. Returns validation errors for unsupported source_system; not-found when "
    "username or object_path is absent from harvested metadata; RDAM no-access when the caller "
    "lacks Instance/Connector DAA for the scoped connection(s)."
)


def _q(**kwargs: object) -> dict[str, object]:
    return {k: v for k, v in kwargs.items() if v is not None}


def _validate_source_system_access_args(
    source_system: str,
    query_direction: str,
    username: str | None,
    object_path: str | None,
) -> dict[str, Any] | None:
    ss = source_system.strip().lower()
    if ss not in MCP_SOURCE_SYSTEMS:
        return {
            "error": (
                f"source_system must be one of {sorted(MCP_SOURCE_SYSTEMS)}, got {source_system!r}"
            ),
            "status_code": 400,
        }
    qd = query_direction.strip().lower()
    if qd not in MCP_QUERY_DIRECTIONS:
        return {
            "error": (
                f"query_direction must be one of {sorted(MCP_QUERY_DIRECTIONS)}, "
                f"got {query_direction!r}"
            ),
            "status_code": 400,
        }
    has_user = username is not None and str(username).strip() != ""
    has_path = object_path is not None and str(object_path).strip() != ""
    if qd == "user_to_objects":
        if not has_user:
            return {
                "error": "username is required when query_direction is user_to_objects.",
                "status_code": 400,
            }
    if qd == "object_to_users":
        if not has_path:
            return {
                "error": "object_path is required when query_direction is object_to_users.",
                "status_code": 400,
            }
        if has_user:
            return {
                "error": "Do not pass username for object_to_users.",
                "status_code": 400,
            }
    return None


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_GET_SOURCE_SYSTEM_ACCESS)
    async def get_source_system_access(
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
                    "Object path (required for object_to_users). Redshift/Snowflake: "
                    "dbName, connectionName.dbName, dbName.schema.table, etc. "
                    "See tool description."
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
        err = _validate_source_system_access_args(
            source_system, query_direction, username, object_path
        )
        if err is not None:
            return err
        params: dict[str, object] = _q(
            sourceSystem=source_system.strip().lower(),
            queryDirection=query_direction.strip().lower(),
            username=username.strip() if username else None,
            objectPath=object_path.strip() if object_path else None,
            includeColumns=include_columns if include_columns else None,
            connectionId=connection_id,
            resolveAllMatches=resolve_all_matches if resolve_all_matches else None,
        )
        try:
            async with ovaledge_client() as client:
                return await client.get(MCP_PATH_SOURCE_SYSTEM_ACCESS, params=params)
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
