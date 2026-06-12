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
    MCP_RDAM_NO_CATALOG_FALLBACK_DOC,
    MCP_RDAM_OBJECT_TYPE_DOC,
    MCP_RDAM_OBJECT_TYPES,
    MCP_RDAM_PRIVILEGE_MAP_DOC,
    MCP_SNOWFLAKE_BUILTIN_OBJECTS_DOC,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_OBJECT_TYPE_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_MULTI_SOURCE_ERROR,
    MCP_SOURCE_SYSTEM_ACCESS_REQUIRED_DOC,
    MCP_SOURCE_SYSTEMS,
    MCP_SOURCE_SYSTEMS_DOC,
)
from server.tools.common import error_payload

_RDAM_OBJECT_TYPE_ALIASES = {
    "oeschema": "schema",
    "oetable": "table",
    "oecolumn": "column",
}

_GRANT_SUMMARY_LEVELS = ("database", "schema", "table", "column", "project", "report")
_GRANT_MECHANISMS = ("direct", "group", "role")


def normalize_string_list(value: str | list[str] | None) -> list[str]:
    """Split comma-separated or list values into distinct non-blank strings."""
    if value is None:
        return []
    items = [value] if isinstance(value, str) else value
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        for part in item.split(","):
            token = part.strip()
            if token and token not in seen:
                seen.add(token)
                out.append(token)
    return out


def normalize_rdam_object_type(object_type: str | None) -> str | None:
    if object_type is None:
        return None
    normalized = object_type.strip().lower()
    if not normalized:
        return None
    return _RDAM_OBJECT_TYPE_ALIASES.get(normalized, normalized)


def filter_user_to_objects_by_level(
    result: dict[str, Any],
    object_type: str,
) -> dict[str, Any]:
    """Backend user_to_objects ignores objectType; filter grants client-side by level."""
    if not result.get("ok"):
        return result
    data = result.get("data")
    if not isinstance(data, dict):
        return result
    grants = data.get("grants")
    if not isinstance(grants, list):
        return result

    level = object_type.lower()
    filtered = [
        grant
        for grant in grants
        if isinstance(grant.get("objectLevel"), str)
        and grant["objectLevel"].lower() == level
    ]
    by_level = dict.fromkeys(_GRANT_SUMMARY_LEVELS, 0)
    by_mech = dict.fromkeys(_GRANT_MECHANISMS, 0)
    for grant in filtered:
        obj_level = grant.get("objectLevel")
        if isinstance(obj_level, str) and obj_level in by_level:
            by_level[obj_level] += 1
        mechanism = grant.get("grantMechanism")
        if isinstance(mechanism, str) and mechanism in by_mech:
            by_mech[mechanism] += 1

    return {
        **result,
        "data": {
            **data,
            "grants": filtered,
            "summary": {
                "totalGrants": len(filtered),
                "byObjectLevel": by_level,
                "byGrantMechanism": by_mech,
            },
            "filteredToObjectLevel": object_type,
        },
    }


_DESC_SOURCE_SYSTEM_ACCESS = (
    "Resolve **native** access grants harvested from Redshift, Snowflake, or Tableau — "
    "independent of OvalEdge catalog permissions.\n\n"
    "Use for questions like:\n"
    '- "What tables can svc_analytics query in Redshift?"\n'
    '- "Who has native access to prod_db.public.orders?"\n'
    '- "Which Snowflake roles give john.doe access?"\n'
    '- "Who can view the Revenue Dashboard in Tableau?"\n'
    '- "Who has native access to the SNOWFLAKE.ALERT schema?"\n\n'
    f"Backend: GET {MCP_PATH_SOURCE_SYSTEM_ACCESS}\n\n"
    "**Not** OvalEdge `get_catalog_object_access` (catalog ACL layer; may ship later).\n\n"
    "**source_system** (required): "
    + MCP_SOURCE_SYSTEMS_DOC
    + ".\n\n"
    "**query_direction** (required): "
    + MCP_QUERY_DIRECTIONS_DOC
    + " — infer from the question; do not ask the user to pick manually.\n\n"
    + MCP_SOURCE_SYSTEM_ACCESS_REQUIRED_DOC
    + "\n\n"
    + MCP_RDAM_OBJECT_TYPE_DOC
    + "\n\n"
    "**Grant models:**\n"
    "- Redshift: direct user, group membership, role assignment (all returned).\n"
    "- Snowflake: role assignment only (no direct user grants / groups).\n"
    "- Tableau: direct site-user grants and site-group grants on project/report.\n\n"
    + MCP_RDAM_PRIVILEGE_MAP_DOC
    + "\n\n"
    + MCP_OBJECT_PATH_FORMATS_DOC
    + "\n\n"
    + MCP_SNOWFLAKE_BUILTIN_OBJECTS_DOC
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
    "Partial-path disambiguation: when the path is not exact and multiple assets match, returns "
    "**matchCandidates** or **resolve_all_matches=true** (max 50).\n"
    + MCP_OBJECT_PATH_PARTIAL_DOC
    + "\n\n"
    + MCP_DAA_SCOPE_DOC
    + "\n\n"
    + MCP_RDAM_NO_CATALOG_FALLBACK_DOC
    + "\n\n"
    "Read-only. Returns validation errors for unsupported source_system; not-found when "
    "username or object_path is absent from harvested metadata; RDAM no-access when the caller "
    "lacks Instance/Connector DAA for the scoped connection(s)."
)


def validate_and_normalize_object_type(
    source_system: str,
    object_type: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Validate object_type for source_system; normalize aliases."""
    ss = source_system.strip().lower()
    normalized_type = normalize_rdam_object_type(object_type)
    if normalized_type is None:
        return None, error_payload(
            f"The following parameters are mandatory: object_type "
            f"(one of {sorted(MCP_RDAM_OBJECT_TYPES)}).",
        )
    if normalized_type not in MCP_RDAM_OBJECT_TYPES:
        return None, error_payload(
            f"object_type must be one of {sorted(MCP_RDAM_OBJECT_TYPES)} "
            f"(catalog aliases oeschema/oetable/oecolumn accepted), got {object_type!r}",
        )
    if normalized_type == "column" and ss != "redshift":
        return None, error_payload("object_type=column is supported for redshift only.")
    if normalized_type in {"project", "report"} and ss != "tableau":
        return None, error_payload(
            f"object_type={normalized_type!r} is supported for tableau only.",
        )
    if normalized_type in {"database", "schema", "table", "column"} and ss == "tableau":
        return None, error_payload(
            f"object_type={normalized_type!r} is not valid for tableau; use project or report.",
        )
    return normalized_type, None


def reject_multiple_source_system(source_system: str | list[str]) -> dict[str, Any] | None:
    values = normalize_string_list(source_system)
    if len(values) > 1:
        return error_payload(MCP_SOURCE_SYSTEM_ACCESS_MULTI_SOURCE_ERROR)
    return None


def reject_multiple_connection_id(
    connection_id: int | list[int] | None,
) -> dict[str, Any] | None:
    if isinstance(connection_id, list):
        ids = [value for value in connection_id if value is not None]
        if len(ids) > 1:
            return error_payload(MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_ERROR)
    return None


def reject_multiple_object_type(
    object_type: str | list[str] | None,
) -> dict[str, Any] | None:
    if len(normalize_string_list(object_type)) > 1:
        return error_payload(MCP_SOURCE_SYSTEM_ACCESS_MULTI_OBJECT_TYPE_ERROR)
    return None


def resolve_single_connection_id(connection_id: int | list[int] | None) -> int | None:
    if connection_id is None:
        return None
    if isinstance(connection_id, list):
        ids = [value for value in connection_id if value is not None]
        return ids[0] if ids else None
    return connection_id


def resolve_single_object_type(object_type: str | list[str] | None) -> str | None:
    values = normalize_string_list(object_type)
    return values[0] if values else None


def _missing_mandatory_source_system_access_fields(
    query_direction: str,
    username: str | list[str] | None,
    object_path: str | list[str] | None,
    object_type: str | list[str] | None,
    connection_id: int | list[int] | None,
) -> list[str]:
    qd = query_direction.strip().lower()
    missing: list[str] = []
    if qd == "user_to_objects" and not normalize_string_list(username):
        missing.append("username")
    if not normalize_string_list(object_path):
        missing.append("object_path")
    if not normalize_string_list(object_type):
        missing.append("object_type")
    if resolve_single_connection_id(connection_id) is None:
        missing.append("connection_id")
    return missing


def validate_source_system_access_args(
    source_system: str | list[str],
    query_direction: str,
    username: str | list[str] | None,
    object_path: str | list[str] | None,
    object_type: str | list[str] | None,
    connection_id: int | list[int] | None,
) -> dict[str, Any] | None:
    multi_source_err = reject_multiple_source_system(source_system)
    if multi_source_err is not None:
        return multi_source_err
    multi_conn_err = reject_multiple_connection_id(connection_id)
    if multi_conn_err is not None:
        return multi_conn_err
    multi_type_err = reject_multiple_object_type(object_type)
    if multi_type_err is not None:
        return multi_type_err

    source_values = normalize_string_list(source_system)
    source = source_values[0] if source_values else str(source_system).strip()
    if source.lower() not in MCP_SOURCE_SYSTEMS:
        return error_payload(
            f"source_system must be one of {sorted(MCP_SOURCE_SYSTEMS)}, got {source!r}",
        )
    qd = query_direction.strip().lower()
    if qd not in MCP_QUERY_DIRECTIONS:
        return error_payload(
            f"query_direction must be one of {sorted(MCP_QUERY_DIRECTIONS)}, "
            f"got {query_direction!r}",
        )
    missing = _missing_mandatory_source_system_access_fields(
        qd, username, object_path, object_type, connection_id
    )
    if missing:
        fields = ", ".join(missing)
        msg = f"The following parameters are mandatory: {fields}."
        if qd == "user_to_objects" and "username" in missing:
            msg += " For user_to_objects, username is the remote login to look up."
        return error_payload(msg)
    return None
