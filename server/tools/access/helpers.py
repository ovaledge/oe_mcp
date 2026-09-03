"""Validation and response shaping for access_explorer (catalog permissions branch)."""

from __future__ import annotations

from typing import Any

from server.constants import (
    MCP_ACCESS_OPERATIONS_DOC,
    MCP_OPERATION_CATALOG_ACCESS,
    MCP_OPERATION_SOURCE_SYSTEM_ACCESS,
    MCP_PATH_ACCESS_EXPLORER,
    MCP_SOURCE_SYSTEM_UNSUPPORTED_CODE,
)
from server.tools.common.descriptions import classify_tool_desc
from server.tools.common.errors import error_payload
from server.tools.rdam.helpers import RDAM_TO_CATALOG_OBJECT_TYPE

_DAM_UNSUPPORTED_MARKERS = (
    "not supported for native DAM",
    "Continue with operation=catalog_access",
)
# Hint vs connectionId mismatch uses mcp.source.system.hint.mismatch and must not match
# these markers (both connectors may be DAM-supported).
_CATALOG_FALLBACK_KEY = "_catalog_fallback"
# object_to_users → object_to_principals is identity-safe (catalog principals on the object).
# user_to_objects must not map to user_to_object: RDAM username is a source login, not an
# OvalEdge user id.
_SOURCE_TO_CATALOG_DIRECTION = {
    "object_to_users": "object_to_principals",
}

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
    "Directions: user_to_object | object_to_principals (username for user_to_object). "
    "Resolve via object_id+object_type, fully_qualified_name, or object_name. "
    "Present effectiveAccess/principals, redirectUrl. Prompt: `catalog_object_access`.\n\n"
    f"**`operation={MCP_OPERATION_SOURCE_SYSTEM_ACCESS}`** — native RDAM / DAM. "
    "Required: `source_system`, `query_direction` (user_to_objects | object_to_users | "
    "browse | role_to_users | group_to_users | user_to_roles | user_to_groups; more in "
    "docs://ovaledge/rdam_source_access). Named objects: this tool fills object_id, "
    "object_type, connection_id, FQN/object_path, object_name via resolve, then DAM. "
    "Known object_id+object_type → DAM only. Never fall back to `asset_explorer` after "
    "RDAM is empty or errors. On 400 `mcp.source.system.unsupported`, continue with "
    "`operation=catalog_access`. Do not probe `connection_id` — ask the user. "
    "**browse:** connection_id + object_type. **user_to_objects:** username; with "
    "connection_id + object_type=table, omit `object_path` to list tables. "
    "**object_to_users:** object_path+object_type or catalog object_id; optional object_name. "
    "**role_to_users / group_to_users / user_to_roles / user_to_groups:** membership "
    "(role/group via object_path or object_name; username for user_*); groups "
    "unsupported on Snowflake. **scope_mode:** exact | descendants. Partial paths may "
    "return matchCandidates or requiresSchemaSelection. Grants include grant_mechanism "
    "(direct / contributing_role or group) and privileges. Prompt `native_source_access`.\n\n"
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


def is_dam_connector_unsupported(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict) or result.get("status_code") != 400:
        return False
    if result.get("error_code") == MCP_SOURCE_SYSTEM_UNSUPPORTED_CODE:
        return True
    err = str(result.get("error") or "")
    return any(marker.lower() in err.lower() for marker in _DAM_UNSUPPORTED_MARKERS)


def attach_catalog_fallback_context(
    result: dict[str, Any],
    *,
    object_id: int | None = None,
    object_type: str | None = None,
    fully_qualified_name: str | None = None,
    object_name: str | list[str] | None = None,
    object_path: str | list[str] | None = None,
) -> dict[str, Any]:
    """Keep catalog identifiers from pre-DAM resolution for catalog_access fallback."""
    from server.tools.common import drop_none

    name: str | None
    if isinstance(object_name, str):
        name = object_name.strip() or None
    elif isinstance(object_name, list):
        name = object_name[0].strip() if object_name and str(object_name[0]).strip() else None
    else:
        name = None
    ctx = drop_none(
        object_id=object_id if object_id is not None and object_id > 0 else None,
        object_type=object_type,
        fully_qualified_name=fully_qualified_name.strip()
        if isinstance(fully_qualified_name, str) and fully_qualified_name.strip()
        else None,
        object_name=name,
        object_path=object_path,
    )
    if not ctx:
        return result
    out = dict(result)
    out[_CATALOG_FALLBACK_KEY] = ctx
    return out


def strip_catalog_fallback(result: dict[str, Any]) -> dict[str, Any]:
    """Drop internal fallback context before the payload leaves the MCP tool."""
    if not isinstance(result, dict) or _CATALOG_FALLBACK_KEY not in result:
        return result
    out = dict(result)
    out.pop(_CATALOG_FALLBACK_KEY, None)
    return out


def catalog_direction_for_unsupported_dam(query_direction: str | None) -> str | None:
    qd = (query_direction or "").strip().lower()
    return _SOURCE_TO_CATALOG_DIRECTION.get(qd)


def catalog_object_type_for_fallback(object_type: str | list[str] | None) -> str | None:
    if isinstance(object_type, list):
        raw = object_type[0] if object_type else None
    else:
        raw = object_type
    if not raw or not str(raw).strip():
        return None
    key = str(raw).strip().lower()
    if key.startswith("oe"):
        return key
    return RDAM_TO_CATALOG_OBJECT_TYPE.get(key, key)


def annotate_catalog_fallback(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict) or not result.get("ok"):
        return result
    data = result.get("data")
    if isinstance(data, dict) and not data.get("advisoryMessage"):
        data["advisoryMessage"] = (
            "Connector type is not supported for native DAM access; "
            "continued with operation=catalog_access."
        )
    return result
