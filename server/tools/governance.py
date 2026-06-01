import re
from html import unescape
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import (
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES_DOC,
    MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_LOOKUP_DQ_RULES,
    MCP_PATH_TAGS,
    MCP_PATH_UPDATE_GOVERNANCE_ROLES,
)

_DESC_GLOSSARY = (
    "Look up one business glossary term. Server object type is always glossary.\n\n"
    f"Backend: GET {MCP_PATH_GLOSSARY_TERMS} (objectId OR termName — mutually exclusive).\n"
    f"Optional query param limit (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT} on server; "
    f"this client caps at {MCP_GLOSSARY_TAGS_LIMIT_MAX}).\n\n"
    "Provide either term_name (search by name) or object_id (by id), never both."
)
_DESC_TAGS = (
    "Look up one OETAG (tag) document from Elasticsearch.\n\n"
    f"Backend: GET {MCP_PATH_TAGS} (objectId OR tagName — mutually exclusive).\n"
    f"Optional query param limit (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT} on server; "
    f"this client caps at {MCP_GLOSSARY_TAGS_LIMIT_MAX}).\n\n"
    "Provide either tag_name or object_id, never both."
)
_DESC_DATASTORY = (
    "Look up one OvalEdge data story the caller can access (Elasticsearch oestory + RBAC).\n\n"
    f"Backend: GET {MCP_PATH_LOOKUP_DATASTORY}\n\n"
    "Lookup modes:\n"
    "- object_id — internal story identifier (alone).\n"
    "- story_name — title lookup (optional story_zone_name).\n"
    "- content_query — search story narrative/sections; optional story_zone_name and/or "
    "story_name to narrow.\n\n"
    "Response includes formattedResponse (storyCitation line, story sections, navUrl). "
    "Present formattedResponse to the user for every lookup mode (including content_query). "
    "The first line must be storyCitation exactly — do not add lead-ins such as "
    "'Your organization governs', 'Based on', or 'According to' before the story title.\n\n"
    "Also: metadata, content, accessControl, navLink, navUrl, storyTitleLink, storyCitation, "
    "storyOpeningLine (same as storyCitation — copy verbatim as the answer's first line).\n\n"
    "After search_catalog_assets returns an oestory, call this tool (object_id or "
    "content_query) for title hyperlinks and formattedResponse — do not cite stories from "
    "search hits alone.\n\n"
    "Not found (404) if no match or the story is not visible to the authenticated user. "
    "Do not use for glossary, tags, or tables."
)

_DESC_LOOKUP_DQ_RULE = (
    "Look up Data Quality rules by name or id (not in search_catalog_assets).\n\n"
    f"Backend: GET {MCP_PATH_LOOKUP_DQ_RULES}\n\n"
    "Provide either rule_name (partial match) or object_id, never both.\n\n"
    "Each hit includes objectId, objectType (dqrule), objectName, steward, redirectUrl. "
    "Use with update_governance_roles: only steward may be updated on DQ rules."
)

_DESC_UPDATE_GOVERNANCE_ROLES = (
    "Assign, update, or remove governance responsibilities (Owner, Steward, Custodian, "
    "Governance Role 4/5/6) on supported OvalEdge assets.\n\n"
    f"Backend: POST {MCP_PATH_UPDATE_GOVERNANCE_ROLES}\n\n"
    "Workflow — resolve the target first:\n"
    "- Catalog assets (tables, columns, files, schemas, reports, APIs, queries, glossary, "
    "tags, stories): use search_catalog_assets, then pass items[].objectId and objectType.\n"
    "- Data Quality rules: use lookup_dq_rule (search_catalog_assets does NOT index dqrule). "
    "Then update_governance_roles with object_type dqrule and role_updates.steward only.\n"
    "- Other non-catalog governance targets (if you already have ids): "
    f"object_type one of {MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES_DOC}.\n\n"
    "Role updates are passed in one request via role_updates. Each key is a role name and "
    "each value is either a user login/team id (assign/update) or null (remove).\n\n"
    "Role keys (case-insensitive): owner, steward, custodian, governance_role_4, "
    "governance_role_5, governance_role_6.\n\n"
    f"Steward-only object types: {', '.join(sorted(MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES))} "
    "(owner/custodian/gov 4–6 are rejected with HTTP 400).\n\n"
    "The server enforces RBAC and governance propagation rules. If a role is inherited from "
    "a glossary term via a 'Copy <Role> to Catalog' setting, that role update will be blocked "
    "and returned in blockedRoles with reasonCode=GLOSSARY_PROPAGATED_GOVERNANCE_ROLE. "
    "Multi-role requests may return partial_success.\n\n"
    "Responses include a redirectUrl to open the target object in OvalEdge."
)


def _cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _story_zone_name(meta: dict[str, Any]) -> str:
    return _cell(meta.get("storyZoneName"))


def _story_citation(title_link: str, zone_name: str) -> str:
    """Markdown for prose: [Title](#nav/story?id=…) (story zone: Zone)."""
    title = title_link.strip()
    zone = zone_name.strip()
    if title and zone:
        return f"{title} (story zone: {zone})"
    return title or zone


def _strip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def _parse_story_sections(story: str | None) -> list[tuple[str, str]]:
    """Split story HTML or text into (heading, body) pairs for display."""
    if not story or not str(story).strip():
        return []
    raw = str(story).strip()
    sections: list[tuple[str, str]] = []
    for match in re.finditer(
        r"<h[1-6][^>]*>\s*(.*?)\s*</h[1-6]>(.*?)(?=<h[1-6]|$)",
        raw,
        flags=re.I | re.S,
    ):
        heading = _strip_html(match.group(1))
        body = _strip_html(match.group(2))
        if heading and body:
            sections.append((heading, body))
    if sections:
        return sections
    plain = _strip_html(raw) if "<" in raw else raw.strip()
    if plain:
        return [("", plain)]
    return []


def _format_datastory_display(body: dict[str, Any]) -> str:
    """Markdown layout: storyCitation, section headings (Scope, Cadence, …), nav URL."""
    data = body.get("data")
    if not isinstance(data, dict):
        return ""
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    content = data.get("content") if isinstance(data.get("content"), dict) else {}
    ac = data.get("accessControl") if isinstance(data.get("accessControl"), dict) else {}

    title_link = str(body.get("storyTitleLink") or data.get("storyTitleLink") or "").strip()
    story_name = _cell(meta.get("storyName"))
    if not title_link and story_name:
        nav = str(body.get("navLink") or data.get("navLink") or "")
        title_link = f"[{story_name}]({nav})" if nav else story_name

    zone_name = _story_zone_name(meta)
    citation = str(
        body.get("storyCitation") or data.get("storyCitation") or ""
    ).strip() or _story_citation(title_link, zone_name)

    lines: list[str] = []
    if citation:
        lines.extend([citation, ""])
    else:
        lines.extend(["Here is the data story that matches that content:", ""])

    for heading, section_body in _parse_story_sections(content.get("story")):
        if heading:
            lines.extend([f"**{heading}**", "", section_body, ""])
        else:
            lines.extend([section_body, ""])

    roles = ac.get("authorizedRoles")
    if isinstance(roles, list) and roles:
        role_str = ", ".join(_cell(r) for r in roles if r)
        if role_str:
            lines.extend(["**Access control**", "", f"- **Authorized roles:** {role_str}", ""])

    nav_url = str(body.get("navUrl") or data.get("navUrl") or "").strip()
    if nav_url:
        lines.extend(["", nav_url])

    return "\n".join(lines).rstrip()


def _enrich_datastory_response(body: dict[str, Any]) -> dict[str, Any]:
    """Add formattedResponse only; navigation URLs must come from the API unchanged."""
    if not body.get("ok"):
        return body
    formatted = _format_datastory_display(body)
    if formatted:
        body["formattedResponse"] = formatted
        data = body.get("data")
        if isinstance(data, dict):
            data["formattedResponse"] = formatted
    return body


def _q(**kwargs: object) -> dict[str, object]:
    return {k: v for k, v in kwargs.items() if v is not None}


_ROLE_KEYS_CANONICAL: dict[str, str] = {
    "owner": "owner",
    "steward": "steward",
    "custodian": "custodian",
    "governance_role_4": "governance_role_4",
    "governance_role_5": "governance_role_5",
    "governance_role_6": "governance_role_6",
}


def _normalize_role_updates(
    role_updates: dict[str, str | None] | None,
) -> tuple[dict[str, str | None] | None, str | None]:
    """
    Return (normalized_updates_or_none, error_or_none).

    The tool accepts a dict whose keys are role names; we normalize keys to the canonical set.
    """
    if role_updates is None:
        return None, "Provide role_updates with at least one role."
    if not isinstance(role_updates, dict) or not role_updates:
        return None, "Provide role_updates with at least one role."
    normalized: dict[str, str | None] = {}
    invalid: list[str] = []
    for k, v in role_updates.items():
        key = str(k or "").strip().lower()
        canon = _ROLE_KEYS_CANONICAL.get(key)
        if not canon:
            invalid.append(str(k))
            continue
        if v is None:
            normalized[canon] = None
        else:
            user = str(v).strip()
            if user == "":
                normalized[canon] = None
            else:
                normalized[canon] = user
    if invalid:
        return (
            None,
            "Invalid governance role type(s): "
            + ", ".join(sorted({s for s in invalid if str(s).strip()})),
        )
    if not normalized:
        return None, "Provide role_updates with at least one valid role."
    return normalized, None


def _format_update_governance_roles_response(body: dict[str, Any]) -> str:
    status = str(body.get("status") or "").strip()
    lines: list[str] = []
    if status:
        lines.append(f"**Status:** {status}")
    target = body.get("target")
    if isinstance(target, dict):
        oid = target.get("objectId")
        otype = target.get("objectType")
        if oid is not None and otype:
            lines.append(f"**Target:** {otype} (id {oid})")
        redirect = str(target.get("redirectUrl") or "").strip()
        if redirect:
            lines.append(f"**Open in OvalEdge:** {redirect}")

    reason_code = str(body.get("reasonCode") or "").strip()
    if reason_code:
        lines.append(f"**Reason code:** {reason_code}")

    updated = body.get("updatedRoles")
    if isinstance(updated, list) and updated:
        lines.append(f"**Updated roles:** {', '.join(str(r) for r in updated)}")
    blocked = body.get("blockedRoles")
    if isinstance(blocked, list) and blocked:
        lines.append(f"**Blocked roles:** {', '.join(str(r) for r in blocked)}")

    message = str(body.get("message") or "").strip()
    if message:
        lines.append(message)
    return "\n".join(lines).strip()


def _enrich_update_governance_roles_response(body: dict[str, Any]) -> dict[str, Any]:
    formatted = _format_update_governance_roles_response(body)
    if formatted:
        body["formattedResponse"] = formatted
    return body


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_GLOSSARY)
    async def lookup_glossary_term(
        object_id: Annotated[
            int | None,
            Field(description="Glossary term internal id; omit if using term_name.", default=None),
        ] = None,
        term_name: Annotated[
            str | None,
            Field(
                description="Term name / label to look up; omit if using object_id.",
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    f"Max hits to return (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT}; "
                    f"capped at {MCP_GLOSSARY_TAGS_LIMIT_MAX})."
                ),
                ge=1,
            ),
        ] = MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    ) -> dict[str, Any]:
        """Glossary lookup (see MCP tool description)."""
        has_id = object_id is not None
        has_name = term_name is not None and str(term_name).strip() != ""
        if has_id and has_name:
            return {
                "error": "Provide either object_id or term_name — not both.",
                "status_code": 400,
            }
        if not has_id and not has_name:
            return {
                "error": "Provide object_id or term_name.",
                "status_code": 400,
            }
        lim = min(max(limit, 1), MCP_GLOSSARY_TAGS_LIMIT_MAX)
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_GLOSSARY_TERMS,
                    params=_q(objectId=object_id, termName=term_name, limit=lim),
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_TAGS)
    async def lookup_tags(
        object_id: Annotated[
            int | None,
            Field(description="Tag internal id; omit if using tag_name.", default=None),
        ] = None,
        tag_name: Annotated[
            str | None,
            Field(description="Tag name to look up; omit if using object_id.", default=None),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    f"Max hits to return (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT}; "
                    f"capped at {MCP_GLOSSARY_TAGS_LIMIT_MAX})."
                ),
                ge=1,
            ),
        ] = MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    ) -> dict[str, Any]:
        """Tag lookup (see MCP tool description)."""
        has_id = object_id is not None
        has_name = tag_name is not None and str(tag_name).strip() != ""
        if has_id and has_name:
            return {
                "error": "Provide either object_id or tag_name — not both.",
                "status_code": 400,
            }
        if not has_id and not has_name:
            return {
                "error": "Provide object_id or tag_name.",
                "status_code": 400,
            }
        lim = min(max(limit, 1), MCP_GLOSSARY_TAGS_LIMIT_MAX)
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_TAGS,
                    params=_q(objectId=object_id, tagName=tag_name, limit=lim),
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_DATASTORY)
    async def lookup_datastory(
        story_zone_name: Annotated[
            str | None,
            Field(
                description=(
                    "Optional story zone (globaldomain.domain); use with story_name title lookup "
                    "or as a filter with content_query."
                ),
                default=None,
            ),
        ] = None,
        story_name: Annotated[
            str | None,
            Field(
                description=(
                    "Story title for name lookup, or optional filter when using content_query."
                ),
                default=None,
            ),
        ] = None,
        content_query: Annotated[
            str | None,
            Field(
                description=(
                    "Search story body text (narrative and indexed sections). "
                    "Optional story_zone_name and/or story_name narrow results. "
                    "Omit for object_id or title-only lookup."
                ),
                default=None,
            ),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(
                description=(
                    "Story internal object id (numeric identifier); "
                    "omit for other modes."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Data story lookup (see MCP tool description)."""
        has_id = object_id is not None and object_id > 0
        has_name = story_name is not None and str(story_name).strip() != ""
        has_content = content_query is not None and str(content_query).strip() != ""
        if has_id and (has_name or has_content):
            return {
                "error": "Provide object_id alone, or use story_name and/or content_query.",
                "status_code": 400,
            }
        if not has_id and not has_name and not has_content:
            return {
                "error": "Provide object_id, story_name, or content_query.",
                "status_code": 400,
            }
        zone = story_zone_name is not None and str(story_zone_name).strip() != ""
        name_for_api = story_name.strip() if has_name else None
        try:
            async with OvalEdgeClient() as client:
                body = await client.get(
                    MCP_PATH_LOOKUP_DATASTORY,
                    params=_q(
                        storyZoneName=story_zone_name.strip() if zone else None,
                        storyName=name_for_api,
                        contentQuery=content_query.strip() if has_content else None,
                        objectId=object_id if has_id else None,
                    ),
                )
                if isinstance(body, dict):
                    return _enrich_datastory_response(body)
                return body
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_LOOKUP_DQ_RULE)
    async def lookup_dq_rule(
        object_id: Annotated[
            int | None,
            Field(description="DQ rule id (dqruleid); omit if using rule_name.", default=None),
        ] = None,
        rule_name: Annotated[
            str | None,
            Field(
                description="Rule name or substring (e.g. Null Data Density Check).",
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description="Max hits for name search (default 20; server max 100).",
                default=MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
                ge=1,
            ),
        ] = MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    ) -> dict[str, Any]:
        """Resolve Data Quality rules for governance updates (see MCP tool description)."""
        has_id = object_id is not None and object_id > 0
        has_name = rule_name is not None and str(rule_name).strip() != ""
        if has_id and has_name:
            return {
                "error": "Provide either rule_name or object_id for DQ rule lookup, not both.",
                "status_code": 400,
            }
        if not has_id and not has_name:
            return {"error": "Provide rule_name or object_id.", "status_code": 400}
        capped = min(limit, MCP_GLOSSARY_TAGS_LIMIT_MAX)
        try:
            async with OvalEdgeClient() as client:
                body = await client.get(
                    MCP_PATH_LOOKUP_DQ_RULES,
                    params=_q(
                        objectId=object_id if has_id else None,
                        ruleName=rule_name.strip() if has_name else None,
                        limit=capped,
                    ),
                )
                return body if isinstance(body, dict) else {"data": body}
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_UPDATE_GOVERNANCE_ROLES)
    async def update_governance_roles(
        object_id: Annotated[
            int,
            Field(
                description=(
                    "Internal object id from search_catalog_assets, lookup_dq_rule, "
                    "lookup_glossary_term, or lookup_tags."
                ),
                ge=1,
            ),
        ],
        object_type: Annotated[
            str,
            Field(
                description=(
                    "OvalEdge objectType: catalog types (oetable, oecolumn, glossary, …) or "
                    "non-catalog governance types (dqrule, dqscheme, dag, policy, …). "
                    "Use lookup_dq_rule for dqrule — not search_catalog_assets."
                ),
            ),
        ],
        role_updates: Annotated[
            dict[str, str | None] | None,
            Field(
                description=(
                    "Map of role -> user identifier. Value is a user (assign/update) or null "
                    "(remove). Keys: owner, steward, custodian, governance_role_4/5/6."
                ),
                default=None,
            ),
        ] = None,
        prompt: Annotated[
            str | None,
            Field(
                description="Original user prompt for audit (clientContext.prompt).",
                default=None,
            ),
        ] = None,
        reason: Annotated[
            str | None,
            Field(
                description="Short reason for the change (clientContext.reason).",
                default=None,
            ),
        ] = None,
        dry_run: Annotated[
            bool | None,
            Field(description="If true, validate only; do not persist.", default=None),
        ] = None,
        idempotency_key: Annotated[
            str | None,
            Field(description="Optional client key to dedupe retries.", default=None),
        ] = None,
    ) -> dict[str, Any]:
        """
        Update governance responsibilities (see MCP tool description).

        Validation of RBAC, propagated-role restrictions, approvals, and audit is handled
        by the OvalEdge backend MCP API.
        """
        if object_type is None or str(object_type).strip() == "":
            return {"error": "object_type is required.", "status_code": 400}
        normalized_updates, err = _normalize_role_updates(role_updates)
        if err:
            return {"error": err, "status_code": 400}

        otype_key = str(object_type).strip().lower()
        if otype_key in MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES and normalized_updates:
            invalid_roles = [
                role
                for role in normalized_updates
                if role != "steward"
            ]
            if invalid_roles:
                return {
                    "error": (
                        f"Only steward may be updated on {otype_key}. "
                        f"Invalid role(s): {', '.join(sorted(invalid_roles))}."
                    ),
                    "status_code": 400,
                }

        body: dict[str, Any] = {
            "target": {"objectId": object_id, "objectType": str(object_type).strip()},
            "roleUpdates": normalized_updates,
        }
        options: dict[str, Any] = {}
        if dry_run is not None:
            options["dryRun"] = dry_run
        if idempotency_key is not None and str(idempotency_key).strip():
            options["idempotencyKey"] = str(idempotency_key).strip()
        if options:
            body["options"] = options
        client_context: dict[str, str] = {}
        if prompt is not None and str(prompt).strip():
            client_context["prompt"] = str(prompt).strip()
        if reason is not None and str(reason).strip():
            client_context["reason"] = str(reason).strip()
        if client_context:
            body["clientContext"] = client_context

        try:
            async with OvalEdgeClient() as client:
                result = await client.post(MCP_PATH_UPDATE_GOVERNANCE_ROLES, body)
                if isinstance(result, dict):
                    return _enrich_update_governance_roles_response(result)
                return result
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
