"""
Native source-system access helpers (RDAM harvest).

Queries OvalEdge-harvested RDAM privilege metadata — not OvalEdge catalog ACLs
(see get_catalog_object_access when that ships) and not catalog data-sources.
"""

from __future__ import annotations

from typing import Any

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
from server.tools.common import blank, error_payload

_DESC_SOURCE_SYSTEM_ACCESS = (
    "Resolve **native** access grants harvested from Redshift, Snowflake, or Tableau — "
    "independent of OvalEdge catalog permissions.\n\n"
    "Use for questions like:\n"
    '- "What tables can svc_analytics query in Redshift?"\n'
    '- "Who has native access to prod_db.public.orders?"\n'
    '- "Which Snowflake roles give john.doe access?"\n'
    '- "Who can view the Revenue Dashboard in Tableau?"\n\n'
    f"Backend: GET {MCP_PATH_SOURCE_SYSTEM_ACCESS}\n\n"
    "**Not** OvalEdge `get_catalog_object_access` (catalog ACL layer; may ship later).\n\n"
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
    "- Redshift/Snowflake database: `rdam_dbprivilege` (USAGE, etc.) included in grants.\n"
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
    "**contributing_group** / **contributing_role** when access is indirect.\n"
    "When **principal_note** is set on a row, the role/group name appears as **principal** because "
    "no RDAM user memberships were harvested for that role/group; roles with members are expanded "
    "to users (see **contributing_role**, e.g. associate, twitchdemo).\n\n"
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


def validate_source_system_access_args(
    source_system: str,
    query_direction: str,
    username: str | None,
    object_path: str | None,
) -> dict[str, Any] | None:
    ss = source_system.strip().lower()
    if ss not in MCP_SOURCE_SYSTEMS:
        return error_payload(
            f"source_system must be one of {sorted(MCP_SOURCE_SYSTEMS)}, got {source_system!r}",
        )
    qd = query_direction.strip().lower()
    if qd not in MCP_QUERY_DIRECTIONS:
        return error_payload(
            f"query_direction must be one of {sorted(MCP_QUERY_DIRECTIONS)}, "
            f"got {query_direction!r}",
        )
    has_user = not blank(username)
    has_path = not blank(object_path)
    if qd == "user_to_objects" and not has_user:
        return error_payload(
            "username is required when query_direction is user_to_objects.",
        )
    if qd == "object_to_users":
        if not has_path:
            return error_payload(
                "object_path is required when query_direction is object_to_users.",
            )
        if has_user:
            return error_payload("Do not pass username for object_to_users.")
    return None
