"""Validation and response shaping for get_user_object_access."""

from __future__ import annotations

from typing import Any

from server.constants import (
    MCP_CATALOG_OBJECT_ACCESS_DIRECTIONS,
    MCP_CATALOG_OBJECT_ACCESS_OBJECT_TYPES_DOC,
    MCP_CATALOG_OBJECT_ACCESS_OVERVIEW_DOC,
)

_DESC_GET_USER_OBJECT_ACCESS = (
    "Discover effective OvalEdge **catalog ACL** permissions (user-based and role-based grants). "
    "Not native Redshift/Snowflake/Tableau grants — use source_system_access for those.\n\n"
    f"{MCP_CATALOG_OBJECT_ACCESS_OVERVIEW_DOC}\n\n"
    "**Directions:** "
    f"{MCP_CATALOG_OBJECT_ACCESS_DIRECTIONS}\n\n"
    "**Asset resolution (pick one):**\n"
    "- `object_id` + `object_type` (preferred after search_catalog_assets or "
    "GET /v1/mcp/data-sources)\n"
    "- `fully_qualified_name` (connector name works for connections)\n"
    "- `object_name` (may return matchCandidates when ambiguous)\n\n"
    f"**Supported object_type values:** {MCP_CATALOG_OBJECT_ACCESS_OBJECT_TYPES_DOC}\n\n"
    "**Connectors:** Use `object_type`=`connection` (aliases: `connector`, `data source`) with "
    "`object_name` such as `looker` or `looker connector`. Connectors are not in "
    "search_catalog_assets — resolve by connector display name. When multiple "
    "Looker/Snowflake connections match, disambiguate using matchCandidates or pass "
    "`object_id` from data-sources.\n\n"
    "**JDBC-backed types (search then access):** These types may be absent from "
    "Elasticsearch. Use `search_catalog_assets` with the matching exclusive `object_type`, "
    "then `get_user_object_access` with `object_id` + `object_type` from the hit:\n"
    "- **Data Domains** — `object_type=dp_domain` alone\n"
    "- **Data Products** — `object_type=dp_product` alone (includes unpublished/NEW)\n"
    "- **Glossary Domains** — `object_type=oeglobaldomain` alone\n"
    "- **Story Zones** — `object_type=storyzone` alone\n"
    "**Data Stories (`oestory`)** — discover via `search_catalog_assets` with "
    "`object_type=oestory` or `lookup_datastory`; access is inherited from the parent "
    "Story Zone (no story-level ACL). Present `inheritedFrom` when returned.\n\n"
    "**Workflow:** When the user names a catalog asset, call search_catalog_assets "
    "first, then pass "
    "object_id and object_type from the chosen hit. For connectors, pass object_name + "
    "object_type=connection (or a name ending in \"connector\"). Present effectiveAccess "
    "(user-centric) or principals (object-centric), grantSources, contributingRoles, "
    "inheritedFrom when present, and redirectUrl."
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
        return {"error": "query_direction is required.", "status_code": 400}
    qd = str(query_direction).strip().lower()
    if qd not in {"user_to_object", "object_to_principals"}:
        return {
            "error": "query_direction must be user_to_object or object_to_principals.",
            "status_code": 400,
        }
    if qd == "user_to_object" and not (username and str(username).strip()):
        return {"error": "username is required for user_to_object.", "status_code": 400}
    has_id = object_id is not None and object_id > 0 and object_type and str(object_type).strip()
    has_fqn = bool(fully_qualified_name and str(fully_qualified_name).strip())
    has_name = bool(object_name and str(object_name).strip())
    mode_count = int(bool(has_id)) + int(has_fqn) + int(has_name)
    if mode_count == 0:
        return {
            "error": "Provide object_id+object_type, fully_qualified_name, or object_name.",
            "status_code": 400,
        }
    if mode_count > 1:
        return {
            "error": "Use only one object resolution mode at a time.",
            "status_code": 400,
        }
    if has_id and not has_fqn and not has_name:
        if object_id is None or object_id <= 0:
            return {"error": "object_id must be a positive integer.", "status_code": 400}
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
                f"({zone_type}); the story has no direct ACL grants."
            )
    return result
