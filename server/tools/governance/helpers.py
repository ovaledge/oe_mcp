import html
import re
import time
from html import unescape
from typing import Any

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import (
    MCP_DOMAIN_METADATA_SIZE_MAX,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES_DOC,
    MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES,
    MCP_PATH_DOMAIN_METADATA,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_LOOKUP_DQ_RULES,
    MCP_PATH_TAGS,
    MCP_PATH_TAGS_CREATE_OPTIONS,
    MCP_PATH_TAGS_PARENT_OPTIONS,
    MCP_PATH_UPDATE_GOVERNANCE_ROLES,
    NAV_GLOSSARY_TERM_HASH,
    SELECTION_PHASE_MASTER_REQUIRED,
    SELECTION_PHASE_PARENT_OPTIONAL,
    STATUS_AWAITING_USER_SELECTION,
)
from server.nav_links import (
    build_absolute_nav_url,
    extract_hash_nav_link,
    get_link_base_url,
    markdown_link,
)
from server.tools.common import as_dict as _as_dict
from server.tools.common import blank as _blank

_DESC_GLOSSARY = (
    "Look up business glossary term(s) by id or name. Server object type is always "
    "glossary; name search may return multiple hits.\n\n"
    f"Backend: GET {MCP_PATH_GLOSSARY_TERMS} (objectId OR termName — mutually exclusive).\n"
    f"Optional query param limit (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT} on server; "
    f"this client caps at {MCP_GLOSSARY_TAGS_LIMIT_MAX}).\n\n"
    "Provide either term_name (search by name) or object_id (by id), never both."
)
_DESC_TAGS = (
    "Look up OETAG (tag) document(s) by id or name from Elasticsearch; name search "
    "may return multiple hits.\n\n"
    f"Backend: GET {MCP_PATH_TAGS} (objectId OR tagName — mutually exclusive).\n"
    f"Optional query param limit (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT} on server; "
    f"this client caps at {MCP_GLOSSARY_TAGS_LIMIT_MAX}).\n\n"
    "Provide either tag_name or object_id, never both."
)
_DESC_CREATE_GLOSSARY = (
    "Create a business glossary term or list domain/category/subcategory placement options.\n\n"
    "**User-facing rule:** Every picker response includes formattedResponse. Present "
    "formattedResponse to the user verbatim and wait for their choice. Never guess or "
    "auto-select domain_id, category_id, or subcategory_id. Never invent a description.\n\n"
    "When the user asks to create a term by name only, call with term_name (and optional "
    "description) but without domain_id — returns the domain list.\n\n"
    "When the user specifies domain by name (for example: 'create term X under Finance' or "
    "'in domain Finance'), call with domain_name='Finance' on the first create_glossary_term "
    "call (even when domain_id is unknown). Do not force a domain picker first.\n\n"
    "Guided workflow (tool advances automatically; do not set search_on for normal flow):\n"
    "1. term_name only → domain picker.\n"
    "1a. term_name + domain_name (without domain_id) → tool resolves domain automatically; "
    "if unique match, continue to category step.\n"
    "2. term_name + domain_id → category picker when categories exist under the domain "
    "(never set skip_category on this step). User may pick one or reply skip; only then set "
    "skip_category=true and category_skip_confirmed=true together.\n"
    "3. term_name + domain_id + category_id → subcategory picker only when subcategories "
    "exist (user may pick one or reply skip; only then set skip_subcategory=true and "
    "subcategory_skip_confirmed=true together).\n"
    "4. term_name + domain_id + non-blank description → confirm_create preview "
    "(doNotCreate=true). Show formattedResponse; wait for explicit user approval.\n"
    "5. Re-call with create_confirmed_by_user=true and the same placement + description "
    "→ POST. Never set create_confirmed_by_user until the user confirms.\n\n"
    "Manual picker: search_on=oeglobaldomain|category|subcategory (mutually exclusive with "
    "advancing create flow only when used alone without conflicting create fields).\n\n"
    f"Backend picker: GET {MCP_PATH_DOMAIN_METADATA}. "
    f"Backend create: POST {MCP_PATH_GLOSSARY_TERMS}."
)

_DESC_CREATE_TAG = (
    "Create a new OETAG in OvalEdge. Flow depends on tagSecurityMode from create-options.\n\n"
    f"Backend: GET {MCP_PATH_TAGS_CREATE_OPTIONS}, GET {MCP_PATH_TAGS_PARENT_OPTIONS}, "
    f"POST {MCP_PATH_TAGS}.\n\n"
    "Parent suggestions mirror Create Tag UI GET site/v1/tag/list:\n"
    "- OPEN: objectType=mastertag, isMasterTagSelectable=true, isRoot=false, "
    "isDataAsset=false (no parentId).\n"
    "- SECURE (after master): same + parentId=<masterTagId>, isRoot=true, "
    "isMasterTagSelectable=false.\n\n"
    "SECURE mode (master mandatory, parent optional):\n"
    "1) tag_name only → MASTER_REQUIRED: show ALL userSelectableMasters. User must pick "
    "exactly one masterTagId (required). Do not show or ask about parent tags yet.\n"
    "2) master_tag_id + master_tag_id_confirmed_by_user=true → PARENT_OPTIONAL for that "
    "master only: show userSelectableParents filtered by masterTagId. Parent is optional:\n"
    "   - Under master only (no parent tag): create_directly_under_master=true + "
    "parent_step_completed_by_user=true (POST uses masterTagId only, like UI under master).\n"
    "   - Under a parent: parent_tag_id + parent_tag_id_confirmed_by_user=true + "
    "parent_step_completed_by_user=true.\n\n"
    "**Parameter create_directly_under_master (name is shared; meaning depends on mode):**\n"
    "- SECURE: create as a direct child of the chosen masterTagId (no parentTagId).\n"
    "- OPEN: create a root tag with no parent (do not send masterTagId).\n\n"
    "OPEN mode (no master step; parent list optional):\n"
    "1) tag_name only → PARENT_OPTIONAL: show ALL userSelectableParents. Ask the human "
    "whether to use a parent BEFORE calling POST. Never create on this call.\n"
    "2) After the human answers, call again with parent_step_completed_by_user=true, plus "
    "parent_tag_id + parent_tag_id_confirmed_by_user=true "
    "OR create_directly_under_master=true (no parent). Never skip step 1 or set finalize "
    "flags on the same call as tag_name only. Always present userSelectableParents and "
    "formattedResponse to the human before step 2.\n\n"
    "If description is omitted on the final POST, MCP auto-fills meaningful wiki HTML from "
    "tag_name and master/parent names (override with description=; disable via "
    "OVALEDGE_TAG_AUTO_DESCRIPTION=false).\n\n"
    "Final create gate (after placement steps): when ready to POST, the tool returns "
    "confirm_create with doNotCreateTag=true. Show formattedResponse; wait for explicit "
    "user approval. Re-call with create_confirmed_by_user=true and the same tag_name, "
    "placement flags, and optional description — then POST.\n"
)
_DESC_DATASTORY = (
    "Look up one OvalEdge data story the caller can access (Elasticsearch oestory + RBAC).\n\n"
    "**Prefer this tool when** the user asks about organizational knowledge onboarded as "
    "data stories: internal policies, standards, playbooks, onboarding, operating "
    "procedures, domain narratives, or 'what we documented' — not OvalEdge product how-to "
    "(use search_platform_docs) and not locating a table/report (use search_catalog_assets). "
    "Default for open-ended org-knowledge questions: content_query with the user's question.\n\n"
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
    "**Human confirmation (same pattern as create_glossary_term / create_tag):** "
    "When ready to persist (and dry_run is not true), call without "
    "create_confirmed_by_user to receive a confirm_update preview (doNotUpdate=true). "
    "Show formattedResponse; wait for explicit user approval. Re-call with "
    "create_confirmed_by_user=true and the same object_id, object_type, role_updates, "
    "and clientContext — then POST. Never set create_confirmed_by_user until the user "
    "confirms.\n\n"
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
    data = _as_dict(body.get("data"))
    if not data:
        return ""
    meta = _as_dict(data.get("metadata"))
    content = _as_dict(data.get("content"))
    ac = _as_dict(data.get("accessControl"))

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


def _picker_data_key(search_on: str) -> str:
    return {"oeglobaldomain": "domains", "category": "Category", "subcategory": "SubCategory"}[
        search_on
    ]


def _extract_picker_items(data: dict[str, Any], search_on: str) -> list[dict[str, Any]]:
    raw = data.get(_picker_data_key(search_on))
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def _resolve_domain_id_by_name(
    items: list[dict[str, Any]], requested_domain_name: str
) -> tuple[int | None, str | None, int]:
    """Return (domain_id, matched_name, match_count) with normalized exact/fallback matching."""
    target = requested_domain_name.strip()
    if not target:
        return (None, None, 0)

    def _normalize(name: str) -> str:
        # Ignore whitespace, separators, and case so "prakashDomain" matches "Prakash Domain".
        return re.sub(r"[\s_\-]+", "", name).casefold()

    target_norm = _normalize(target)
    exact_matches: list[tuple[int, str]] = []
    contains_matches: list[tuple[int, str]] = []

    for item in items:
        name_raw = item.get("domain")
        oid = item.get("globaldomainid")
        if not isinstance(name_raw, str) or not isinstance(oid, int) or oid <= 0:
            continue
        clean_name = name_raw.strip()
        name_norm = _normalize(clean_name)
        if name_norm == target_norm:
            exact_matches.append((oid, clean_name))
        elif target_norm and target_norm in name_norm:
            contains_matches.append((oid, clean_name))

    if len(exact_matches) == 1:
        return (exact_matches[0][0], exact_matches[0][1], 1)
    if len(exact_matches) > 1:
        return (None, None, len(exact_matches))
    if len(contains_matches) == 1:
        return (contains_matches[0][0], contains_matches[0][1], 1)
    return (None, None, len(contains_matches))


def _resolve_category_id_by_name(
    items: list[dict[str, Any]], requested_category_name: str
) -> tuple[int | None, str | None, int]:
    """Return (category_id, matched_name, match_count) with normalized exact/fallback matching."""
    target = requested_category_name.strip()
    if not target:
        return (None, None, 0)

    def _normalize(name: str) -> str:
        return re.sub(r"[\s_\-]+", "", name).casefold()

    target_norm = _normalize(target)
    exact_matches: list[tuple[int, str]] = []
    contains_matches: list[tuple[int, str]] = []

    for item in items:
        name_raw = item.get("categoryName")
        oid = item.get("categoryId")
        if not isinstance(name_raw, str) or not isinstance(oid, int) or oid <= 0:
            continue
        clean_name = name_raw.strip()
        name_norm = _normalize(clean_name)
        if name_norm == target_norm:
            exact_matches.append((oid, clean_name))
        elif target_norm and target_norm in name_norm:
            contains_matches.append((oid, clean_name))

    if len(exact_matches) == 1:
        return (exact_matches[0][0], exact_matches[0][1], 1)
    if len(exact_matches) > 1:
        return (None, None, len(exact_matches))
    if len(contains_matches) == 1:
        return (contains_matches[0][0], contains_matches[0][1], 1)
    return (None, None, len(contains_matches))


def _extract_placement_from_path(
    domain_name: str | None, category_name: str | None, subcategory_name: str | None
) -> tuple[str | None, str | None, str | None]:
    """Support natural path input like 'Domain > Category > Subcategory'."""
    clean_domain = (
        str(domain_name).strip()
        if isinstance(domain_name, str) and not _blank(domain_name)
        else None
    )
    clean_category = (
        str(category_name).strip()
        if isinstance(category_name, str) and not _blank(category_name)
        else None
    )
    clean_subcategory = (
        str(subcategory_name).strip()
        if isinstance(subcategory_name, str) and not _blank(subcategory_name)
        else None
    )
    if clean_domain and ">" in clean_domain:
        parts = [p.strip() for p in clean_domain.split(">") if p and p.strip()]
        if len(parts) >= 3:
            return parts[0], clean_category or parts[1], clean_subcategory or parts[2]
        if len(parts) == 2:
            return parts[0], clean_category or parts[1], clean_subcategory
    if clean_category and ">" in clean_category and not clean_subcategory:
        parts = [p.strip() for p in clean_category.split(">") if p and p.strip()]
        if len(parts) >= 2:
            return clean_domain, parts[0], parts[1]
    return clean_domain, clean_category, clean_subcategory


def _format_placement_options(search_on: str, items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, item in enumerate(items, 1):
        if search_on == "oeglobaldomain":
            oid = item.get("globaldomainid")
            name = _cell(item.get("domain"))
            lines.append(f"{i}. **{name}** (`domain_id={oid}`)")
        elif search_on == "category":
            cid = item.get("categoryId")
            name = _cell(item.get("categoryName"))
            sub = " — has subcategories" if item.get("isSubCategory") else ""
            lines.append(f"{i}. **{name}** (`category_id={cid}`){sub}")
        else:
            sid = item.get("subCategoryId")
            name = _cell(item.get("subCategoryName"))
            lines.append(f"{i}. **{name}** (`subcategory_id={sid}`)")
    return "\n".join(lines) if lines else "_No placement options returned (check RBAC or filters)._"


def _picker_workflow_phase(search_on: str) -> str:
    return {
        "oeglobaldomain": "select_domain",
        "category": "select_category",
        "subcategory": "select_subcategory",
    }[search_on]


def _picker_selection_field(search_on: str) -> str:
    return {
        "oeglobaldomain": "domain_id",
        "category": "category_id",
        "subcategory": "subcategory_id",
    }[search_on]


def _picker_user_prompt(
    search_on: str,
    *,
    pending_term_name: str | None = None,
    domain_id: int | None = None,
    domain_name: str | None = None,
    category_id: int | None = None,
    category_name: str | None = None,
) -> str:
    if search_on == "oeglobaldomain":
        if pending_term_name:
            return (
                f'You asked to create the glossary term **"{pending_term_name}"**. '
                "Which **domain** should it live under? Reply with the domain name "
                "or **domain_id** from the list below."
            )
        return (
            "Which **domain** should the new glossary term belong to? "
            "Reply with the domain name or **domain_id** from the list below."
        )
    if search_on == "category":
        dom = domain_name or (f"domain_id {domain_id}" if domain_id else "the selected domain")
        term = f' for **"{pending_term_name}"**' if pending_term_name else ""
        return (
            f"Under **{dom}**{term}: pick a **category** (reply with name or **category_id**), "
            "or reply **skip** to place the term directly under the domain only."
        )
    cat = category_name or (f"category_id {category_id}" if category_id else "the category")
    term = f' for **"{pending_term_name}"**' if pending_term_name else ""
    return (
        f"Under **{cat}**{term}: pick a **subcategory** (reply with name or **subcategory_id**), "
        "or reply **skip** to place the term under the category only."
    )


def _format_picker_response(
    search_on: str,
    items: list[dict[str, Any]],
    *,
    pending_term_name: str | None = None,
    domain_id: int | None = None,
    domain_name: str | None = None,
    category_id: int | None = None,
    category_name: str | None = None,
) -> str:
    options = _format_placement_options(search_on, items)
    prompt = _picker_user_prompt(
        search_on,
        pending_term_name=pending_term_name,
        domain_id=domain_id,
        domain_name=domain_name,
        category_id=category_id,
        category_name=category_name,
    )
    title = "**Glossary term placement**"
    if pending_term_name:
        title = f"**Create glossary term: {pending_term_name}**"
    return (
        f"{title}\n\n{prompt}\n\n{options}\n\n"
        "_Do not call create until the user confirms their choice._"
    )


def _picker_next_step(search_on: str) -> str:
    if search_on == "oeglobaldomain":
        return (
            "STOP: Show formattedResponse to the user and wait. After they choose domain_id, "
            "call again with term_name and domain_id (category picker runs automatically)."
        )
    if search_on == "category":
        return (
            "STOP: Show formattedResponse to the user and wait. They may pick category_id "
            "(tool will offer subcategories if any) or reply skip and re-call with "
            "skip_category=true and category_skip_confirmed=true (both required)."
        )
    return (
        "STOP: Show formattedResponse to the user and wait. They may pick subcategory_id "
        "or reply skip and re-call with skip_subcategory=true. Then supply description "
        "before create."
    )


def _shape_picker_response(
    body: dict[str, Any],
    search_on: str,
    *,
    pending_term_name: str | None = None,
    pending_description: str | None = None,
    domain_id: int | None = None,
    domain_name: str | None = None,
    category_id: int | None = None,
    category_name: str | None = None,
) -> dict[str, Any]:
    data = _as_dict(body.get("data"))
    items = _extract_picker_items(data, search_on)
    formatted = _format_picker_response(
        search_on,
        items,
        pending_term_name=pending_term_name,
        domain_id=domain_id,
        domain_name=domain_name,
        category_id=category_id,
        category_name=category_name,
    )
    out = dict(body)
    out["searchOn"] = search_on
    out["workflowPhase"] = _picker_workflow_phase(search_on)
    out["awaitingUserSelection"] = True
    out["selectionField"] = _picker_selection_field(search_on)
    out["placementOptions"] = items
    out["formattedPlacementOptions"] = _format_placement_options(search_on, items)
    out["formattedResponse"] = formatted
    out["userPrompt"] = _picker_user_prompt(
        search_on,
        pending_term_name=pending_term_name,
        domain_id=domain_id,
        domain_name=domain_name,
        category_id=category_id,
        category_name=category_name,
    )
    out["nextStep"] = _picker_next_step(search_on)
    if search_on == "category":
        out["agentInstruction"] = (
            "Present formattedResponse to the user exactly. Do not create the term or "
            "continue until they reply with their selection. Never set skip_category unless "
            "the user explicitly replied skip after seeing this list; then re-call with "
            "skip_category=true and category_skip_confirmed=true."
        )
    else:
        out["agentInstruction"] = (
            "Present formattedResponse to the user exactly. Do not create the term or "
            "continue until they reply with their selection."
        )
    if pending_term_name:
        out["pendingTermName"] = pending_term_name
    if pending_description:
        out["pendingDescription"] = pending_description
    if domain_id and domain_id > 0:
        out["pendingDomainId"] = domain_id
    if domain_name:
        out["pendingDomainName"] = domain_name
    if category_id and category_id > 0:
        out["pendingCategoryId"] = category_id
    return out


async def _fetch_domain_metadata(
    client: OvalEdgeClient,
    search_on: str,
    *,
    page: int,
    size: int,
    domain_id: int,
    category_id: int,
) -> dict[str, Any]:
    lim = min(max(size, 1), MCP_DOMAIN_METADATA_SIZE_MAX)
    params: dict[str, object] = {
        "searchOn": search_on,
        "page": page,
        "size": lim,
        "domainId": domain_id,
        "categoryId": category_id,
    }
    if search_on == "subcategory":
        params["subCategoryId"] = 0
    body = await client.get(MCP_PATH_DOMAIN_METADATA, params=params)
    if isinstance(body, dict):
        return body
    return {"ok": False, "data": {}}


def _build_placement_path(
    *,
    term_name: str,
    domain_id: int,
    domain_name: str | None,
    category_id: int | None,
    category_name: str | None,
    subcategory_id: int | None,
    subcategory_name: str | None,
) -> str:
    parts: list[str] = []
    if domain_name is not None and not _blank(domain_name):
        parts.append(str(domain_name).strip())
    elif domain_id > 0:
        parts.append(f"domain:{domain_id}")
    if category_id and category_id > 0:
        if category_name is not None and not _blank(category_name):
            parts.append(str(category_name).strip())
        else:
            parts.append(f"category:{category_id}")
    if subcategory_id and subcategory_id > 0:
        if subcategory_name is not None and not _blank(subcategory_name):
            parts.append(str(subcategory_name).strip())
        else:
            parts.append(f"subcategory:{subcategory_id}")
    parts.append(term_name.strip())
    return " > ".join(parts)


def _shape_create_response(
    body: dict[str, Any],
    *,
    term_name: str,
    domain_id: int,
    domain_name: str | None,
    category_id: int | None,
    category_name: str | None,
    subcategory_id: int | None,
    subcategory_name: str | None,
    placement_note: str | None = None,
) -> dict[str, Any]:
    out = dict(body)
    data = _as_dict(body.get("data"))
    term_details = (
        str(data.get("termDetails")).strip()
        if isinstance(data.get("termDetails"), str)
        else ""
    )
    nav = extract_hash_nav_link(term_details) if term_details else ""
    gid = data.get("businessGlossaryId")
    if not nav and isinstance(gid, int) and gid > 0:
        nav = f"{NAV_GLOSSARY_TERM_HASH}{gid}"
    if nav:
        absolute = build_absolute_nav_url(nav)
        out["termDetails"] = nav
        out["redirectUrl"] = absolute
        out["navLink"] = nav
        out["navUrl"] = absolute
        if isinstance(data, dict):
            data = dict(data)
            data["termDetails"] = nav
            data["redirectUrl"] = absolute
            data["navLink"] = nav
            data["navUrl"] = absolute
            out["data"] = data
    out["placementPath"] = _build_placement_path(
        term_name=term_name,
        domain_id=domain_id,
        domain_name=domain_name,
        category_id=category_id,
        category_name=category_name,
        subcategory_id=subcategory_id,
        subcategory_name=subcategory_name,
    )
    path = out["placementPath"]
    status = _cell(data.get("status")) or "created"
    nav_url = str(out.get("navUrl") or "")
    out["formattedResponse"] = (
        f"**Glossary term created:** {term_name}\n\n"
        + f"- **Placement:** {path}\n"
        + (f"- **Placement note:** {placement_note}\n" if placement_note else "")
        + f"- **Status:** {status}\n"
        + (f"- **Redirect:** {nav_url}\n" if nav_url else "")
        + (f"- **Open:** {nav_url}\n" if nav_url else "")
    )
    out["workflowPhase"] = "created"
    return out


_CREATE_CONFIRM_AGENT_INSTRUCTION = (
    "Show formattedResponse and wait for explicit user approval. "
    "Do not set create_confirmed_by_user=true until the user confirms. "
    "Then re-call with create_confirmed_by_user=true and the same parameters."
)


def _format_glossary_create_confirmation_preview(
    *,
    term_name: str,
    domain_id: int,
    domain_name: str | None,
    category_id: int | None,
    category_name: str | None,
    subcategory_id: int | None,
    subcategory_name: str | None,
    description: str,
    definition: str | None,
    publish: bool,
    placement_note: str | None = None,
) -> dict[str, Any]:
    path = _build_placement_path(
        term_name=term_name,
        domain_id=domain_id,
        domain_name=domain_name,
        category_id=category_id,
        category_name=category_name,
        subcategory_id=subcategory_id,
        subcategory_name=subcategory_name,
    )
    desc_text = description.strip()
    desc_preview = (
        desc_text if len(desc_text) <= 400 else desc_text[:397] + "..."
    )
    publish_label = "published" if publish else "draft"
    return {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_create",
        "doNotCreate": True,
        "createConfirmedByUser": False,
        "placementPath": path,
        "formattedResponse": (
            "**Confirm glossary term creation**\n\n"
            f"- **Term:** {term_name.strip()}\n"
            f"- **Placement:** {path}\n"
            + (f"- **Placement note:** {placement_note}\n" if placement_note else "")
            + f"- **Description:** {desc_preview}\n"
            + (
                f"- **Definition:** {definition.strip()}\n"
                if definition and not _blank(definition)
                else ""
            )
            + f"- **Publish:** {publish_label}\n\n"
            "Ask the user to confirm. After they approve, call again with "
            "`create_confirmed_by_user=true` and the same `term_name`, `domain_id`, "
            "placement ids (or skip flags), and `description`."
        ),
        "agentInstruction": _CREATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingCreate": {
            "termName": term_name.strip(),
            "domainId": domain_id,
            "category1Id": category_id or 0,
            "category2Id": subcategory_id or 0,
            "publish": publish,
        },
    }


def _format_tag_create_confirmation_preview(
    *,
    tag_name: str,
    description: str | None,
    secure_mode: bool,
    master_tag_id: int | None,
    master_tag_name: str | None,
    parent_tag_id: int | None,
    parent_tag_name: str | None,
    create_directly_under_master: bool,
) -> dict[str, Any]:
    if secure_mode:
        if parent_tag_id is not None and parent_tag_id > 0:
            placement = (
                f"under parent **{parent_tag_name or parent_tag_id}** "
                f"(master **{master_tag_name or master_tag_id}**)"
            )
        else:
            placement = (
                f"directly under master **{master_tag_name or master_tag_id}** "
                "(no parent tag)"
            )
        mode_label = "SECURE"
    elif parent_tag_id is not None and parent_tag_id > 0:
        placement = f"under parent **{parent_tag_name or parent_tag_id}** (open mode)"
        mode_label = "OPEN"
    else:
        placement = "with no parent (open mode, root tag)"
        mode_label = "OPEN"

    desc_line = ""
    if description and not _blank(description):
        desc_preview = str(description).strip()
        if len(desc_preview) > 200:
            desc_preview = desc_preview[:197] + "..."
        desc_line = f"- **Description:** {desc_preview}\n"
    elif create_directly_under_master or secure_mode:
        desc_line = (
            "- **Description:** (auto-generated from tag and hierarchy if omitted on create)\n"
        )

    return {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_create",
        "doNotCreateTag": True,
        "createConfirmedByUser": False,
        "tagSecurityMode": "secure" if secure_mode else "open",
        "formattedResponse": (
            f"**Confirm tag creation** ({mode_label} mode)\n\n"
            f"- **Tag name:** {tag_name.strip()}\n"
            f"- **Placement:** {placement}\n"
            f"{desc_line}\n"
            "Ask the user to confirm. After they approve, call again with "
            "`create_confirmed_by_user=true` and the same `tag_name`, placement "
            "parameters, and optional `description`."
        ),
        "agentInstruction": _CREATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingCreate": {
            "tagName": tag_name.strip(),
            "masterTagId": master_tag_id if secure_mode else None,
            "parentTagId": parent_tag_id if parent_tag_id and parent_tag_id > 0 else None,
            "createDirectlyUnderMaster": create_directly_under_master,
        },
    }


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


def _format_update_governance_roles_confirmation_preview(
    body: dict[str, Any],
) -> dict[str, Any]:
    target = body.get("target")
    oid = otype = None
    if isinstance(target, dict):
        oid = target.get("objectId")
        otype = target.get("objectType")
    role_updates = body.get("roleUpdates")
    role_lines: list[str] = []
    if isinstance(role_updates, dict):
        for role, principal in sorted(role_updates.items()):
            if principal is None:
                role_lines.append(f"- **{role}:** (remove)")
            else:
                role_lines.append(f"- **{role}:** {principal}")
    roles_block = "\n".join(role_lines) if role_lines else "- (no role_updates)"
    dry = body.get("options", {})
    dry_note = ""
    if isinstance(dry, dict) and dry.get("dryRun"):
        dry_note = "\n- **Note:** dry_run=true — validate only on confirm.\n"
    return {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_update",
        "doNotUpdate": True,
        "createConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm governance role update**\n\n"
            f"- **Target:** {otype} (id {oid})\n"
            f"{roles_block}\n"
            f"{dry_note}\n"
            "Ask the user to confirm. After they approve, call again with "
            "`create_confirmed_by_user=true` and the same object_id, object_type, "
            "role_updates, and clientContext."
        ),
        "agentInstruction": _CREATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingUpdate": {
            "target": target,
            "roleUpdates": role_updates,
        },
    }

# In-memory proof that step 1 (parent picker) ran for a tag name — not exposed to clients.
_PENDING_PARENT_PICKER_TTL_SEC = 3600
_pending_parent_picker_expiry: dict[str, float] = {}


def _register_parent_picker_shown(tag_name: str) -> None:
    key = tag_name.strip().lower()
    _pending_parent_picker_expiry[key] = time.time() + _PENDING_PARENT_PICKER_TTL_SEC


def _parent_picker_was_shown(tag_name: str) -> bool:
    """Whether step 1 registered the parent picker for this tag name (MCP-internal)."""
    key = tag_name.strip().lower()
    exp = _pending_parent_picker_expiry.get(key)
    if exp is None:
        return False
    return exp >= time.time()


def _consume_parent_picker_shown(tag_name: str) -> bool:
    """One-time consume before POST — preview steps must use _parent_picker_was_shown only."""
    if not _parent_picker_was_shown(tag_name):
        return False
    key = tag_name.strip().lower()
    _pending_parent_picker_expiry.pop(key, None)
    return True


def _catalog_doc_from_lookup(lookup_body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not lookup_body or not lookup_body.get("ok"):
        return None
    data = lookup_body.get("data")
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return None


def _plain_description(catalog: dict[str, Any] | None, fallback: str | None) -> str:
    if catalog:
        bd = catalog.get("businessDescription")
        if isinstance(bd, dict):
            for key in ("plainText", "wikitextplain", "wikiTextPlain"):
                val = bd.get(key)
                if val is not None and str(val).strip():
                    return str(val).strip()
        for key in ("description", "businessDescription"):
            val = catalog.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return (fallback or "").strip()


_AUDIT_TAG_TRAIL_NAV = "#nav/audittrail?activeTab=audittagtermdomain/audittag"


def _positive_int(value: object) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return None


def _catalog_is_root_tag(catalog: dict[str, Any] | None) -> bool:
    if not catalog:
        return False
    for key in ("isRootTag", "isMasterTag"):
        raw = catalog.get(key)
        if raw in (1, True, "1", "true", "True"):
            return True
    for block_key in ("catalogDetails", "objectDetails"):
        block = catalog.get(block_key)
        if not isinstance(block, list):
            continue
        for item in block:
            if not isinstance(item, dict):
                continue
            if item.get("key") == "isRootTag" and str(item.get("value", "")).strip() in (
                "1",
                "true",
                "True",
            ):
                return True
    tag_details = catalog.get("tagDetails")
    if isinstance(tag_details, list) and tag_details:
        first = tag_details[0]
        if isinstance(first, dict) and first.get("isRootTag") in (1, True, "1"):
            return True
    return False


def _resolve_effective_master_tag_id(
    tag_id: int,
    *,
    catalog: dict[str, Any] | None,
    master_tag_id: int | None,
    parent_tag_id: int | None,
) -> int | None:
    master = _positive_int(master_tag_id)
    if catalog:
        for key in ("masterTagId", "superParentTagId", "rootTagId"):
            from_catalog = _positive_int(catalog.get(key))
            if from_catalog:
                master = from_catalog
                break
        parent_oid = _positive_int(catalog.get("parentObjectId"))
        if master is None and parent_oid:
            master = parent_oid
    if master is None:
        master = _positive_int(parent_tag_id)
    if master is None and _catalog_is_root_tag(catalog):
        return tag_id
    return master


def _tag_is_master_summary_page(
    tag_id: int,
    *,
    catalog: dict[str, Any] | None,
    master_tag_id: int | None,
    parent_tag_id: int | None,
    effective_master: int | None,
) -> bool:
    """True when the tag detail page uses objectType=mastertag (root / master tag)."""
    if tag_id == effective_master:
        return True
    if _positive_int(parent_tag_id):
        return False
    ext_master = _positive_int(master_tag_id)
    if ext_master is not None and ext_master != tag_id:
        return False
    if _catalog_is_root_tag(catalog):
        return True
    # Open-mode root tag: no parent and no separate master (e.g. create_directly_under_master).
    return effective_master is None and ext_master is None


def _tag_summary_page_nav(
    tag_id: int,
    *,
    catalog: dict[str, Any] | None,
    master_tag_id: int | None,
    parent_tag_id: int | None,
) -> str:
    """Full tag summary route (matches OvalEdge tag detail / OETP anchors)."""
    effective_master = _resolve_effective_master_tag_id(
        tag_id,
        catalog=catalog,
        master_tag_id=master_tag_id,
        parent_tag_id=parent_tag_id,
    )
    is_master_page = _tag_is_master_summary_page(
        tag_id,
        catalog=catalog,
        master_tag_id=master_tag_id,
        parent_tag_id=parent_tag_id,
        effective_master=effective_master,
    )
    if is_master_page:
        return f"#nav/tag?id={tag_id}&objectType=mastertag&masterTagId={tag_id}"
    if effective_master and effective_master > 0:
        return (
            f"#nav/tag?id={tag_id}&objectType=oetag&masterTagId={effective_master}"
        )
    return f"#nav/tag?id={tag_id}&objectType=oetag"


def _tag_redirect_nav(tag_id: int) -> str:
    """Minimal post-create redirect (id only), as used across tag list links."""
    return f"#nav/tag?id={tag_id}"


def _resolve_tag_nav(
    catalog: dict[str, Any] | None,
    tag_id: int,
    *,
    master_tag_id: int | None,
    parent_tag_id: int | None,
) -> tuple[str, str, str, str]:
    """
    Return (summary_page_nav, summary_page_url, redirect_nav, redirect_url).

    Prefer catalog navLink only when it already includes objectType (backend-shaped).
    """
    catalog_nav = extract_hash_nav_link(
        str((catalog or {}).get("navLink") or (catalog or {}).get("hyperlink") or "")
    )
    if catalog_nav and "objectType=" in catalog_nav.lower():
        summary_nav = catalog_nav
    else:
        summary_nav = _tag_summary_page_nav(
            tag_id,
            catalog=catalog,
            master_tag_id=master_tag_id,
            parent_tag_id=parent_tag_id,
        )
    redirect_nav = _tag_redirect_nav(tag_id)
    return (
        summary_nav,
        build_absolute_nav_url(summary_nav),
        redirect_nav,
        build_absolute_nav_url(redirect_nav),
    )


def _audit_trail_nav() -> tuple[str, str]:
    return _AUDIT_TAG_TRAIL_NAV, build_absolute_nav_url(_AUDIT_TAG_TRAIL_NAV)


def _build_tag_summary(
    *,
    tag_id: int,
    tag_name: str,
    description: str | None,
    master_tag_id: int | None,
    parent_tag_id: int | None,
    catalog: dict[str, Any] | None,
    indexed: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "tagId": tag_id,
        "tagName": tag_name,
        "objectType": "oetag",
        "description": _plain_description(catalog, description),
        "indexedInCatalog": indexed,
    }
    if master_tag_id is not None and master_tag_id > 0:
        summary["masterTagId"] = master_tag_id
    if parent_tag_id is not None and parent_tag_id > 0:
        summary["parentTagId"] = parent_tag_id
    if catalog:
        for key in (
            "fullQualifiedName",
            "parentObjectId",
            "parentHierarchies",
            "catalogDetails",
            "objectDetails",
            "uuid",
        ):
            if key in catalog and catalog[key] is not None:
                summary[key] = catalog[key]
    effective_master = _resolve_effective_master_tag_id(
        tag_id,
        catalog=catalog,
        master_tag_id=master_tag_id,
        parent_tag_id=parent_tag_id,
    )
    if effective_master and effective_master > 0:
        summary["effectiveMasterTagId"] = effective_master
    if _tag_is_master_summary_page(
        tag_id,
        catalog=catalog,
        master_tag_id=master_tag_id,
        parent_tag_id=parent_tag_id,
        effective_master=effective_master,
    ):
        summary["objectType"] = "mastertag"
    return summary


def _build_audit_reference(tag_id: int, tag_name: str) -> dict[str, Any]:
    trail_nav, trail_url = _audit_trail_nav()
    return {
        "action": "ADD",
        "store": "a_tag",
        "tagId": tag_id,
        "tagName": tag_name,
        "description": (
            "Tag creation appears on Governance Catalog → Audit Trails → Tags "
            "(audittagtermdomain/audittag)."
        ),
        "navLink": trail_nav,
        "redirectUrl": trail_url,
        "activeTab": "audittagtermdomain/audittag",
    }


def _master_tag_ids_from_guidance_data(data: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for item in _iter_master_choice_dicts(data.get("masterTagChoices")):
        raw = item.get("masterTagId")
        if isinstance(raw, int) and raw > 0:
            ids.add(raw)
    return ids


def _iter_master_choice_dicts(choices: object) -> list[dict[str, Any]]:
    if not isinstance(choices, list):
        return []
    return [item for item in choices if isinstance(item, dict)]


def _build_user_selectable_masters(choices: object) -> list[dict[str, Any]]:
    """Compact list of every accessible root master tag (no parent nesting)."""
    masters: list[dict[str, Any]] = []
    for item in _iter_master_choice_dicts(choices):
        mid = item.get("masterTagId")
        if not isinstance(mid, int) or mid <= 0:
            continue
        name = item.get("tagName") or item.get("masterTagsName")
        entry: dict[str, Any] = {"masterTagId": mid, "tagName": name}
        desc = item.get("description")
        if isinstance(desc, str) and desc.strip():
            plain = desc.strip()
            if len(plain) > 120:
                plain = plain[:117] + "..."
            entry["description"] = plain
        masters.append(entry)
    masters.sort(key=lambda m: (str(m.get("tagName") or "").lower(), m["masterTagId"]))
    return masters


def _format_master_list_for_user(masters: list[dict[str, Any]]) -> str:
    """Human-readable list of all accessible masters (never truncated)."""
    if not masters:
        return "No accessible master tags were returned for your account."
    lines = [
        f"Choose one master tag ({len(masters)} accessible — list is complete):",
    ]
    for m in masters:
        mid = m["masterTagId"]
        name = m.get("tagName") or "(unnamed)"
        desc = m.get("description")
        if desc:
            lines.append(f"  - masterTagId={mid}: {name} — {desc}")
        else:
            lines.append(f"  - masterTagId={mid}: {name}")
    lines.append(
        "Reply with the master tag id or name only (required). "
        "You will be asked about an optional parent tag in the next step."
    )
    return "\n".join(lines)


def _build_user_selectable_parents(parents: object) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(parents, list):
        return items
    for row in parents:
        if not isinstance(row, dict):
            continue
        pid = row.get("parentTagId")
        if not isinstance(pid, int) or pid <= 0:
            continue
        entry: dict[str, Any] = {
            "parentTagId": pid,
            "tagName": row.get("tagName"),
        }
        if row.get("rootTag") is True:
            entry["rootTag"] = True
        items.append(entry)
    items.sort(key=lambda p: (str(p.get("tagName") or "").lower(), p["parentTagId"]))
    return items


def _format_open_parent_list_for_user(parents: list[dict[str, Any]]) -> str:
    lines = [
        "OPEN mode — Step 1 of 1 (parent selection only; no master tag step).",
        "Parent tag is completely optional (same as Create Tag UI open mode).",
        "",
        "Ask the human which option they want BEFORE creating the tag.",
        "",
        "  - **No parent** (root/open tag) → call create_tag again with "
        "create_directly_under_master=true and parent_step_completed_by_user=true "
        "(do not set masterTagId).",
        "  - **Under a parent** → call create_tag with parent_tag_id, "
        "parent_tag_id_confirmed_by_user=true, and parent_step_completed_by_user=true "
        "(pick from list below; root/master rows use parent_tag_id only).",
        "",
    ]
    if not parents:
        lines.append(
            "No parent tags are listed. Use create_directly_under_master=true and "
            "parent_step_completed_by_user=true to create without a parent."
        )
        return "\n".join(lines)
    lines.append(
        f"Suggested parent tags ({len(parents)} choices — complete list):"
    )
    for p in parents:
        pid = p["parentTagId"]
        pname = p.get("tagName") or "(unnamed)"
        root_note = (
            " (root/master — use parent_tag_id; backend sets master)"
            if p.get("rootTag")
            else ""
        )
        lines.append(f"  - parentTagId={pid}: {pname}{root_note}")
    return "\n".join(lines)


def _create_under_master_option(master_tag_id: int, master_tag_name: str | None) -> dict[str, Any]:
    label = master_tag_name or f"master tag {master_tag_id}"
    return {
        "optionType": "CREATE_UNDER_MASTER_ONLY",
        "masterTagId": master_tag_id,
        "tagName": master_tag_name,
        "description": (
            f"Create as a direct child of master '{label}' (masterTagId={master_tag_id}, "
            "no parentTagId — same as UI 'under master only')."
        ),
        "mcpAction": (
            "create_directly_under_master=true, parent_step_completed_by_user=true, "
            f"master_tag_id={master_tag_id}, master_tag_id_confirmed_by_user=true"
        ),
    }


def _format_parent_list_for_user(
    master_tag_id: int,
    master_tag_name: str | None,
    parents: list[dict[str, Any]],
) -> str:
    label = master_tag_name or f"master {master_tag_id}"
    lines = [
        "SECURE mode — Step 2 of 2 (parent selection under the chosen master).",
        f"Master tag selected: {label} (masterTagId={master_tag_id}) — required step done.",
        "",
        "Parent tag is optional. Choose one:",
        "",
        f"  - **Under master only** (no parent tag; child of masterTagId={master_tag_id}):",
        "    create_directly_under_master=true, parent_step_completed_by_user=true",
        f"    (keep master_tag_id={master_tag_id}, master_tag_id_confirmed_by_user=true)",
        "",
        "  - **Under a parent tag** (pick parentTagId from list below):",
        "    parent_tag_id + parent_tag_id_confirmed_by_user=true + "
        "parent_step_completed_by_user=true",
        "",
    ]
    if not parents:
        lines.append(
            f"No additional parent tags under this master. Use create_directly_under_master=true "
            f"(tag created under masterTagId={master_tag_id} only)."
        )
        return "\n".join(lines)
    lines.append(
        f"Parent tags under masterTagId={master_tag_id} ({len(parents)} choices — complete list):"
    )
    for p in parents:
        pid = p["parentTagId"]
        pname = p.get("tagName") or "(unnamed)"
        lines.append(f"  - parentTagId={pid}: {pname}")
    return "\n".join(lines)


def _master_label_from_guidance(
    guidance: dict[str, Any] | None,
    master_tag_id: int,
) -> str | None:
    if not guidance:
        return None
    for m in guidance.get("userSelectableMasters") or []:
        if isinstance(m, dict) and m.get("masterTagId") == master_tag_id:
            name = m.get("tagName")
            return name if isinstance(name, str) else None
    for item in _iter_master_choice_dicts(guidance.get("masterTagChoices")):
        if item.get("masterTagId") == master_tag_id:
            name = item.get("tagName") or item.get("masterTagsName")
            return name if isinstance(name, str) else None
    return None


def _tag_name_from_parent_list(
    parents: list[dict[str, Any]],
    parent_tag_id: int | None,
) -> str | None:
    if parent_tag_id is None or parent_tag_id <= 0:
        return None
    for row in parents:
        if row.get("parentTagId") == parent_tag_id:
            name = row.get("tagName")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return None


def _tag_auto_description_enabled() -> bool:
    from server.config import get_settings

    return get_settings().ovaledge_tag_auto_description


def _build_auto_tag_description(
    tag_name: str,
    *,
    master_tag_name: str | None = None,
    parent_tag_name: str | None = None,
) -> str:
    """Wiki HTML description derived from tag name and optional hierarchy labels."""
    label = tag_name.strip() or "tag"
    safe = html.escape(label)
    if parent_tag_name and master_tag_name:
        sentence = (
            f"{safe} is a governance tag classified under "
            f"<strong>{html.escape(parent_tag_name.strip())}</strong> "
            f"within the <strong>{html.escape(master_tag_name.strip())}</strong> "
            "master tag hierarchy."
        )
    elif master_tag_name:
        sentence = (
            f"{safe} is a governance tag in the "
            f"<strong>{html.escape(master_tag_name.strip())}</strong> "
            "master tag hierarchy."
        )
    elif parent_tag_name:
        sentence = (
            f"{safe} is a governance tag classified under "
            f"<strong>{html.escape(parent_tag_name.strip())}</strong>."
        )
    else:
        sentence = (
            f"{safe} is a governance tag in OvalEdge used to classify and "
            "govern data assets."
        )
    return f"<p>{sentence}</p>"


def _resolve_create_tag_description(
    tag_name: str,
    explicit: str | None,
    *,
    master_tag_name: str | None = None,
    parent_tag_name: str | None = None,
) -> str | None:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    if not _tag_auto_description_enabled():
        return None
    return _build_auto_tag_description(
        tag_name,
        master_tag_name=master_tag_name,
        parent_tag_name=parent_tag_name,
    )


async def _resolve_tag_hierarchy_names_for_create(
    client: OvalEdgeClient,
    *,
    secure_mode: bool,
    master_tag_id: int | None,
    parent_tag_id: int | None,
    secure_guidance: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    master_name: str | None = None
    parent_name: str | None = None
    if secure_mode and master_tag_id is not None and master_tag_id > 0:
        master_name, parents = await _fetch_parent_choices_for_master(
            client, master_tag_id, secure_guidance
        )
        parent_name = _tag_name_from_parent_list(parents, parent_tag_id)
    elif parent_tag_id is not None and parent_tag_id > 0:
        open_parents = await _fetch_open_parent_choices(client)
        parent_name = _tag_name_from_parent_list(open_parents, parent_tag_id)
    return master_name, parent_name


async def _fetch_open_parent_choices(client: OvalEdgeClient) -> list[dict[str, Any]]:
    """
    Open mode parent list — same sources as Create Tag UI (tag/list / create-options).

    Prefer GET /mcp/tags/create-options parentTagChoices, then parent-options.
    """
    try:
        opts = await client.get(MCP_PATH_TAGS_CREATE_OPTIONS)
        if isinstance(opts, dict) and opts.get("ok"):
            data = opts.get("data")
            if isinstance(data, dict) and data.get("tagSecurityMode") == "open":
                parents = _build_user_selectable_parents(data.get("parentTagChoices"))
                if parents:
                    return parents
    except OvalEdgeError:
        pass
    try:
        result = await client.get(MCP_PATH_TAGS_PARENT_OPTIONS)
        if isinstance(result, dict) and result.get("ok"):
            data = result.get("data")
            if isinstance(data, dict):
                return _build_user_selectable_parents(data.get("parentTagChoices"))
    except OvalEdgeError:
        pass
    return []


def _parent_picker_guidance_payload(
    *,
    tag_name: str,
    parents: list[dict[str, Any]],
    formatted_response: str,
    extra: dict[str, Any],
) -> dict[str, Any]:
    """Return value for create_tag when the human must pick or skip a parent first."""
    _register_parent_picker_shown(tag_name)
    count = len(parents)
    payload: dict[str, Any] = {
        "ok": True,
        "status": STATUS_AWAITING_USER_SELECTION,
        "message": (
            f"Parent tag selection required for \"{tag_name}\" ({count} option(s)). "
            "Present userSelectableParents and formattedResponse to the user. "
            "Then call create_tag again with parent_step_completed_by_user=true and "
            "the human's parent choice (or create_directly_under_master=true)."
        ),
        "selectionPhase": SELECTION_PHASE_PARENT_OPTIONAL,
        "userMustSelectParentOrSkip": True,
        "awaitingUserSelection": True,
        "doNotCreateTag": True,
        "presentParentTagsToUser": True,
        "suggestParentTagSelection": True,
        "parentTagChoiceCount": count,
        "userSelectableParents": parents,
        "formattedResponse": formatted_response,
    }
    payload.update(extra)
    return payload


def _format_open_parent_selection_guidance(
    *,
    parents: list[dict[str, Any]],
    tag_name: str,
) -> dict[str, Any]:
    lines = [
        "STOP — do not create the tag yet.",
        f"Tag name: {tag_name}",
        _format_open_parent_list_for_user(parents),
        "",
        "Ask the human: use a parent from the list, or no parent.",
        "Next create_tag call: parent_step_completed_by_user=true plus their choice.",
    ]
    return _parent_picker_guidance_payload(
        tag_name=tag_name,
        parents=parents,
        formatted_response="\n".join(lines),
        extra={
            "tagSecurityMode": "open",
            "masterTagRequired": False,
            "parentTagRequired": False,
        },
    )


async def _fetch_parent_choices_for_master(
    client: OvalEdgeClient,
    master_tag_id: int,
    secure_guidance: dict[str, Any] | None,
) -> tuple[str | None, list[dict[str, Any]]]:
    master_name = _master_label_from_guidance(secure_guidance, master_tag_id)
    try:
        result = await client.get(
            MCP_PATH_TAGS_PARENT_OPTIONS,
            params={"masterTagId": master_tag_id},
        )
        if isinstance(result, dict) and result.get("ok"):
            data = result.get("data")
            if isinstance(data, dict):
                if not master_name and isinstance(data.get("masterTagName"), str):
                    master_name = data["masterTagName"]
                return master_name, _build_user_selectable_parents(
                    data.get("parentTagChoices")
                )
    except OvalEdgeError:
        pass
    if secure_guidance and isinstance(secure_guidance.get("masterTagChoices"), list):
        parents_raw: list[dict[str, Any]] = []
        for item in _iter_master_choice_dicts(secure_guidance["masterTagChoices"]):
            if item.get("masterTagId") != master_tag_id:
                continue
            raw = item.get("parentTagChoices")
            if isinstance(raw, list):
                parents_raw = [p for p in raw if isinstance(p, dict)]
            break
        return master_name, _build_user_selectable_parents(parents_raw)
    return master_name, []


def _format_parent_selection_guidance(
    *,
    master_tag_id: int,
    master_tag_name: str | None,
    parents: list[dict[str, Any]],
    tag_name: str,
) -> dict[str, Any]:
    lines = [
        "STOP — do not create the tag yet.",
        f"Tag name: {tag_name}",
        _format_parent_list_for_user(master_tag_id, master_tag_name, parents),
    ]
    return _parent_picker_guidance_payload(
        tag_name=tag_name,
        parents=parents,
        formatted_response="\n".join(lines),
        extra={
            "tagSecurityMode": "secure",
            "masterTagRequired": True,
            "parentTagRequired": False,
            "masterTagId": master_tag_id,
            "masterTagName": master_tag_name,
            "createUnderMasterOnlyOption": _create_under_master_option(
                master_tag_id, master_tag_name
            ),
        },
    )


def _parent_choice_finalized(
    *,
    secure_mode: bool,
    parent_tag_id: int | None,
    parent_tag_id_confirmed_by_user: bool,
    create_directly_under_master: bool,
    parent_step_completed_by_user: bool,
) -> bool:
    """
    True only after the human was shown parent options and answered (second MCP call).

    Always requires parent_step_completed_by_user=true so a single call with
    create_directly_under_master cannot skip the parent list (open or secure).
    """
    if not parent_step_completed_by_user:
        return False
    if parent_tag_id is not None and parent_tag_id > 0:
        return parent_tag_id_confirmed_by_user
    return create_directly_under_master


async def _fetch_tag_create_context(
    client: OvalEdgeClient,
) -> tuple[bool, set[int]]:
    """
    Returns (secure_mode, accessible_master_tag_ids).
    In open mode the second value is empty.
    """
    try:
        opts = await client.get(MCP_PATH_TAGS_CREATE_OPTIONS)
    except OvalEdgeError as exc:
        if exc.status_code == 422 and isinstance(exc.body.get("data"), dict):
            data = exc.body["data"]
            if data.get("tagSecurityMode") == "secure":
                return True, _master_tag_ids_from_guidance_data(data)
        return False, set()
    if not isinstance(opts, dict) or not opts.get("ok"):
        return False, set()
    data = opts.get("data")
    if not isinstance(data, dict):
        return False, set()
    if data.get("tagSecurityMode") == "secure":
        return True, _master_tag_ids_from_guidance_data(data)
    return False, set()


def _reject_invented_master_tag_id(
    master_tag_id: int,
    valid_ids: set[int],
    guidance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lines = [
        f"master_tag_id {master_tag_id} is not valid for this user.",
        "Do not guess master tag ids. Ask the user to pick one from masterTagChoices.",
    ]
    if valid_ids:
        lines.append("Valid masterTagId values: " + ", ".join(str(i) for i in sorted(valid_ids)))
    out: dict[str, Any] = {
        "ok": False,
        "status_code": 422,
        "message": lines[0],
        "userMustSelectMasterTag": True,
        "formattedResponse": "\n".join(lines),
    }
    if guidance:
        for key, value in guidance.items():
            if key == "ok":
                continue
            out[key] = value
    return out


def _format_guidance_from_create_options_data(
    data: dict[str, Any],
    *,
    message: str,
    status_code: int = 422,
) -> dict[str, Any]:
    """Present secure-mode master/parent choices for the human user (not the LLM)."""
    mode = data.get("tagSecurityMode")
    choices = data.get("masterTagChoices")
    user_selectable_masters = _build_user_selectable_masters(choices)
    master_count = len(user_selectable_masters)
    lines = [
        "STOP — do not create the tag yet.",
        message,
        "SECURE mode — Step 1 of 2: select a master tag (mandatory).",
        "Show every entry in userSelectableMasters (complete list).",
        "Ask the user for masterTagId or master tag name only.",
        "Do not show parent tags or parentTagId until step 2 after master is confirmed.",
    ]
    if mode:
        lines.append(f"Tag security mode: {mode}.")
    note = data.get("masterTagIdFieldNote")
    if isinstance(note, str) and note.strip():
        lines.append(note.strip())
    lines.append(_format_master_list_for_user(user_selectable_masters))
    return {
        "ok": False,
        "status_code": status_code,
        "message": message,
        "selectionPhase": SELECTION_PHASE_MASTER_REQUIRED,
        "tagSecurityMode": "secure",
        "masterTagRequired": True,
        "parentTagRequired": False,
        "userMustSelectMasterTag": True,
        "awaitingUserSelection": True,
        "doNotCreateTag": True,
        "presentAllMasterTagsToUser": True,
        "masterTagChoiceCount": master_count,
        "userSelectableMasters": user_selectable_masters,
        "status": data.get("status"),
        "requiredFields": data.get("requiredFields"),
        "optionalFields": data.get("optionalFields"),
        "masterTagChoices": choices,
        "masterTagIdFieldNote": data.get("masterTagIdFieldNote"),
        "formattedResponse": "\n".join(lines),
    }


def _format_create_tag_input_required(exc: OvalEdgeError) -> dict[str, Any]:
    """Map 422 MCP create-tag guidance into a tool payload the agent can present."""
    body = _as_dict(exc.body)
    data = _as_dict(body.get("data"))
    raw_message = body.get("message")
    message = raw_message if isinstance(raw_message, str) else str(exc)
    return _format_guidance_from_create_options_data(
        data,
        message=message,
        status_code=exc.status_code,
    )


async def _load_secure_create_guidance(client: OvalEdgeClient) -> dict[str, Any] | None:
    """Fetch master/parent choices from the backend (no tag create)."""
    try:
        opts = await client.get(MCP_PATH_TAGS_CREATE_OPTIONS)
    except OvalEdgeError as exc:
        if exc.status_code == 422:
            return _format_create_tag_input_required(exc)
        return None
    if not isinstance(opts, dict) or not opts.get("ok"):
        return None
    data = opts.get("data")
    if not isinstance(data, dict) or data.get("tagSecurityMode") != "secure":
        return None
    return _format_guidance_from_create_options_data(
        data,
        message=(
            "Select a master tag (required). Reply with masterTagId or master tag name."
        ),
    )


def _block_llm_master_selection(
    guidance: dict[str, Any] | None,
    *,
    master_tag_id: int | None,
) -> dict[str, Any]:
    lines = [
        "master_tag_id was sent without master_tag_id_confirmed_by_user=true.",
        "The LLM must not choose the master tag — ask the human to pick from "
        "masterTagChoices, then retry with their id and master_tag_id_confirmed_by_user=true.",
    ]
    if master_tag_id is not None and master_tag_id > 0:
        lines.insert(0, f"Rejected master_tag_id={master_tag_id} (not human-confirmed).")
    out: dict[str, Any] = {
        "ok": False,
        "status_code": 422,
        "message": lines[0],
        "userMustSelectMasterTag": True,
        "awaitingUserSelection": True,
        "doNotCreateTag": True,
        "masterTagIdConfirmedByUserRequired": True,
        "formattedResponse": "\n".join(lines),
    }
    if guidance:
        for key, value in guidance.items():
            if key in ("ok", "message", "formattedResponse"):
                continue
            out[key] = value
        master_block = guidance.get("formattedResponse") or ""
        if master_block:
            out["formattedResponse"] = "\n".join(lines) + "\n\n" + str(master_block)
    return out


def _block_llm_parent_selection(
    guidance: dict[str, Any] | None,
    *,
    parent_tag_id: int,
) -> dict[str, Any]:
    lines = [
        f"Rejected parent_tag_id={parent_tag_id} (not human-confirmed).",
        "Set parent_tag_id_confirmed_by_user=true only after the human picks from "
        "parentTagChoices, or omit parent_tag_id to create under the master only.",
    ]
    out: dict[str, Any] = {
        "ok": False,
        "status_code": 422,
        "message": lines[0],
        "awaitingUserSelection": True,
        "doNotCreateTag": True,
        "parentTagIdConfirmedByUserRequired": True,
        "formattedResponse": "\n".join(lines),
    }
    if guidance:
        for key, value in guidance.items():
            if key in ("ok", "message", "formattedResponse"):
                continue
            out[key] = value
    return out


def _format_create_tag_display(
    tag_name: str,
    tag_id: int,
    summary_page_url: str,
    redirect_url: str,
    audit_url: str,
    summary: dict[str, Any],
) -> str:
    fqn = summary.get("fullQualifiedName")
    lines = [
        f"Created tag **{tag_name}** (id {tag_id}).",
    ]
    if isinstance(fqn, str) and fqn.strip():
        lines.append(f"- **Fully qualified name:** {fqn.strip()}")
    desc = summary.get("description")
    if isinstance(desc, str) and desc.strip():
        lines.append(f"- **Description:** {desc.strip()[:500]}")
    # Only the field labels are hyperlinks (not the tag name).
    if summary_page_url:
        lines.append(f"- {markdown_link('Tag summary', summary_page_url)}")
    if redirect_url:
        lines.append(f"- {markdown_link('Redirect URL', redirect_url)}")
    if audit_url:
        lines.append(f"- {markdown_link('Audit reference', audit_url)}")
    return "\n".join(lines)


def _tag_response_links(
    *,
    summary_nav: str,
    summary_url: str,
    redirect_nav: str,
    redirect_url: str,
    audit_nav: str,
    audit_url: str,
) -> dict[str, Any]:
    """Structured links for clients that do not render markdown."""
    return {
        "tagSummary": {
            "label": "Tag summary",
            "navLink": summary_nav,
            "url": summary_url,
        },
        "redirect": {
            "label": "Redirect URL",
            "navLink": redirect_nav,
            "url": redirect_url,
        },
        "audit": {
            "label": "Audit reference",
            "navLink": audit_nav,
            "url": audit_url,
            "activeTab": "audittagtermdomain/audittag",
        },
    }


def _enrich_create_tag_response(
    create_body: dict[str, Any],
    *,
    description: str | None,
    master_tag_id: int | None,
    parent_tag_id: int | None,
    lookup_body: dict[str, Any] | None,
) -> dict[str, Any]:
    if not create_body.get("ok"):
        return create_body
    data = create_body.get("data")
    if not isinstance(data, dict):
        return create_body

    tag_id_raw = data.get("tagId")
    tag_name = str(data.get("tagName") or "").strip()
    if not isinstance(tag_id_raw, int) or tag_id_raw <= 0:
        return create_body
    tag_id = tag_id_raw

    # Preserve OvalEdge POST /mcp/tags payload before adding MCP fields.
    backend_create_payload = dict(data)
    effective_master = _positive_int(data.get("masterTagId")) or master_tag_id
    effective_parent = _positive_int(data.get("parentTagId")) or parent_tag_id
    app_base = get_link_base_url()

    catalog = _catalog_doc_from_lookup(lookup_body)
    indexed = catalog is not None
    summary_nav, summary_url, redirect_nav, redirect_url = _resolve_tag_nav(
        catalog,
        tag_id,
        master_tag_id=effective_master,
        parent_tag_id=effective_parent,
    )

    summary = _build_tag_summary(
        tag_id=tag_id,
        tag_name=tag_name,
        description=description,
        master_tag_id=effective_master,
        parent_tag_id=effective_parent,
        catalog=catalog,
        indexed=indexed,
    )
    summary["summaryPageNavLink"] = summary_nav
    summary["summaryPageUrl"] = summary_url
    summary["redirectNavLink"] = redirect_nav
    summary["redirectUrl"] = redirect_url
    audit = _build_audit_reference(tag_id, tag_name)
    audit_url = str(audit.get("redirectUrl") or "")
    audit_nav = str(audit.get("navLink") or "")
    links = _tag_response_links(
        summary_nav=summary_nav,
        summary_url=summary_url,
        redirect_nav=redirect_nav,
        redirect_url=redirect_url,
        audit_nav=audit_nav,
        audit_url=audit_url,
    )

    data["tagSummary"] = summary
    data["navLink"] = summary_nav
    data["summaryPageUrl"] = summary_url
    data["redirectNavLink"] = redirect_nav
    data["redirectUrl"] = redirect_url
    data["auditReference"] = audit
    data["links"] = links
    data["appBaseUrl"] = app_base
    data["backendCreatePayload"] = backend_create_payload
    if lookup_body is not None:
        data["catalogLookup"] = lookup_body
    data["formattedResponse"] = _format_create_tag_display(
        tag_name,
        tag_id,
        summary_url,
        redirect_url,
        audit_url,
        summary,
    )

    create_body["tagSummary"] = summary
    create_body["navLink"] = summary_nav
    create_body["summaryPageUrl"] = summary_url
    create_body["redirectNavLink"] = redirect_nav
    create_body["redirectUrl"] = redirect_url
    create_body["auditReference"] = audit
    create_body["links"] = links
    create_body["appBaseUrl"] = app_base
    create_body["backendCreatePayload"] = backend_create_payload
    create_body["formattedResponse"] = data["formattedResponse"]
    # Full API envelopes for clients that want unmodified backend JSON.
    create_body["backend"] = {
        "create": {
            "ok": create_body.get("ok"),
            "message": create_body.get("message"),
            "status_code": create_body.get("status_code"),
            "data": backend_create_payload,
        },
        "catalogLookup": lookup_body,
    }
    if lookup_body is not None:
        create_body["catalogLookup"] = lookup_body
    if not indexed:
        create_body["catalogLookupNote"] = (
            "Tag catalog document not indexed yet; nav link built from create ids. "
            "Retry lookup_tags(object_id) later for full summary."
        )
        data["catalogLookupNote"] = create_body["catalogLookupNote"]

    return create_body


async def _lookup_tag_after_create(
    client: OvalEdgeClient,
    tag_id: int,
) -> dict[str, Any] | None:
    try:
        return await client.get(
            MCP_PATH_TAGS,
            params={"objectId": tag_id, "limit": 1},
        )
    except OvalEdgeError:
        return None

