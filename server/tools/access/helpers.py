"""Validation and response shaping for access_explorer (catalog permissions branch)."""

from __future__ import annotations

from typing import Any

from server.constants import (
    MCP_ACCESS_OPERATIONS_DOC,
    MCP_OPERATION_CATALOG_ACCESS,
    MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
    MCP_PATH_ACCESS_EXPLORER,
)
from server.tools.common.descriptions import classify_tool_desc
from server.tools.common.errors import error_payload

_DESC_ACCESS_EXPLORER = classify_tool_desc(
    "Explore access permissions: OvalEdge **catalog permissions** or **native** RDAM "
    "grants (Redshift/Snowflake/Tableau). Say **catalog permissions** to users (not ACL).\n\n"
    f"Backend: GET {MCP_PATH_ACCESS_EXPLORER}\n\n"
    "**Who-has-access:** `resolve_object_access` then `access_intent_confirmed` "
    "(native / catalog_acl). Snowflake/Redshift/Tableau alone do not skip disambiguation. "
    "First-person inventory without a named principal "
    '(e.g. "What tables/schemas/columns can I see/view/access?") → `asset_explorer` '
    "— not `access_explorer`. Named principal → `access_explorer`.\n\n"
    f"**Required:** `operation` ({MCP_ACCESS_OPERATIONS_DOC}).\n\n"
    f"**`operation={MCP_OPERATION_CATALOG_ACCESS}`** — catalog permissions (user/role grants). "
    "Directions: user_to_object | object_to_principals (username required for "
    "user_to_object). Asset resolution (one mode): object_id+object_type, "
    "fully_qualified_name, or object_name. Present effectiveAccess/principals, "
    "redirectUrl. Prompt: `catalog_object_access`.\n\n"
    f"**`operation={MCP_OPERATION_SOURCE_SYSTEM_ACCESS}`** — native RDAM grants / DAM browse. "
    "Required: `source_system`, `query_direction` (user_to_objects | object_to_users | "
    "browse). **Not** catalog permissions or `asset_explorer` — never fall back to "
    "`asset_explorer` when RDAM is empty or errors. Do not probe `connection_id` — ask "
    "the user. **browse:** connection_id + object_type. **user_to_objects:** username "
    "required; with connection_id + object_type=table, omit `object_path` to list tables. "
    "**object_to_users:** object_path + object_type. Optional object_name composes path. "
    "**scope_mode:** exact | descendants (default exact). Partial paths may return "
    "matchCandidates or requiresSchemaSelection. Grant rows include grant_mechanism "
    "(direct / contributing_role/group) and privileges. "
    "docs://ovaledge/rdam_source_access; prompt `native_source_access`.\n\n"
    "docs://ovaledge/mcp_workflows (Who has access?). Read-only. "
    "RBAC / Instance-Connector **Data Access Admin** enforced server-side.",
    confidential=True,
)


def validate_get_user_object_access_args(
    query_direction: str | None,
    username: str | None,
    object_id: int | None,
    object_type: str | None,
    fully_qualified_name: str | None,
    object_name: str | None,
) -> dict[str, Any] | None:
    if not query_direction or not str(query_direction).strip():
        return error_payload("query_direction is required.")
    qd = str(query_direction).strip().lower()
    if qd not in {"user_to_object", "object_to_principals"}:
        return error_payload(
            "query_direction must be user_to_object or object_to_principals.",
        )
    if qd == "user_to_object" and not (username and str(username).strip()):
        return error_payload("username is required for user_to_object.")
    has_id = object_id is not None and object_id > 0 and object_type and str(object_type).strip()
    has_fqn = bool(fully_qualified_name and str(fully_qualified_name).strip())
    has_name = bool(object_name and str(object_name).strip())
    mode_count = int(bool(has_id)) + int(has_fqn) + int(has_name)
    if mode_count == 0:
        return error_payload(
            "Provide object_id+object_type, fully_qualified_name, or object_name.",
        )
    if mode_count > 1:
        return error_payload("Use only one object resolution mode at a time.")
    if has_id and not has_fqn and not has_name:
        if object_id is None or object_id <= 0:
            return error_payload("object_id must be a positive integer.")
    return None


def enrich_get_user_object_access_response(result: dict[str, Any]) -> dict[str, Any]:
    from server.nav_links import build_absolute_nav_url

    if not isinstance(result, dict):
        return result
    data = result.get("data")
    if not isinstance(data, dict):
        return result
    redirect = data.get("redirectUrl") or data.get("redirect_url")
    nav = data.get("navLink") or data.get("nav_link")
    if not redirect and nav:
        data["redirectUrl"] = build_absolute_nav_url(str(nav))
    elif redirect:
        data["redirectUrl"] = build_absolute_nav_url(str(redirect))
    inherited = data.get("inheritedFrom")
    if isinstance(inherited, dict) and data.get("objectType") == "oestory":
        zone_name = inherited.get("objectName") or inherited.get("object_name")
        zone_type = inherited.get("objectType") or inherited.get("object_type")
        if zone_name and not data.get("advisoryMessage"):
            data["advisoryMessage"] = (
                f"Data story access is inherited from Story Zone '{zone_name}' "
                f"({zone_type}); the story has no direct catalog permissions."
            )
    return result
