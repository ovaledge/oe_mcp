import re
from html import unescape
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import (
    MCP_DOMAIN_METADATA_SEARCH_ON,
    MCP_DOMAIN_METADATA_SIZE_DEFAULT,
    MCP_DOMAIN_METADATA_SIZE_MAX,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_PATH_DOMAIN_METADATA,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_TAGS,
    NAV_GLOSSARY_TERM_HASH,
)
from server.nav_links import build_absolute_nav_url, extract_hash_nav_link

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
    "4. Create only when term_name + domain_id + non-blank description; placement flags "
    "as above. Missing description returns collect_description — never POST without it.\n\n"
    "Manual picker: search_on=oeglobaldomain|category|subcategory (mutually exclusive with "
    "advancing create flow only when used alone without conflicting create fields).\n\n"
    f"Backend picker: GET {MCP_PATH_DOMAIN_METADATA}. "
    f"Backend create: POST {MCP_PATH_GLOSSARY_TERMS}."
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


def _normalize_datastory_nav_links(body: dict[str, Any]) -> dict[str, Any]:
    """Ensure navLink (hash) and hyperlink (absolute) are consistent; pass through API payload."""
    if not body.get("ok"):
        return body
    data = body.get("data")
    if not isinstance(data, dict):
        return body
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else None
    nav = extract_hash_nav_link(str(data.get("navLink") or data.get("hyperlink") or ""))
    if not nav and meta is not None:
        oid = meta.get("objectId")
        if isinstance(oid, int) and oid > 0:
            nav = f"#nav/story?id={oid}"
    if nav:
        absolute = build_absolute_nav_url(nav)
        data["navLink"] = nav
        data["hyperlink"] = absolute
        data["navUrl"] = absolute
        body["navLink"] = nav
        body["hyperlink"] = absolute
        body["navUrl"] = absolute
        if meta is not None:
            name = str(meta.get("storyName") or meta.get("story_name") or "").strip()
            zone_name = _story_zone_name(meta)
            if zone_name:
                body["storyZoneName"] = zone_name
                data["storyZoneName"] = zone_name
            if name:
                body["storyTitleLink"] = f"[{name}]({nav})"
                data["storyTitleLink"] = body["storyTitleLink"]
                citation = _story_citation(body["storyTitleLink"], zone_name)
                if citation:
                    body["storyCitation"] = citation
                    data["storyCitation"] = citation
                    body["storyOpeningLine"] = citation
                    data["storyOpeningLine"] = citation
    formatted = _format_datastory_display(body)
    if formatted:
        body["formattedResponse"] = formatted
        if isinstance(data, dict):
            data["formattedResponse"] = formatted
    return body


def _q(**kwargs: object) -> dict[str, object]:
    return {k: v for k, v in kwargs.items() if v is not None}


def _blank(s: str | None) -> bool:
    return s is None or str(s).strip() == ""


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
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
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
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
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

    @mcp.tool(description=_DESC_CREATE_GLOSSARY)
    async def create_glossary_term(
        search_on: Annotated[
            str | None,
            Field(
                description=(
                    "Picker mode: oeglobaldomain | category | subcategory. "
                    "Omit when creating a term (term_name set)."
                ),
                default=None,
            ),
        ] = None,
        term_name: Annotated[
            str | None,
            Field(
                description="Term name; required for create. Omit for picker mode.",
                default=None,
            ),
        ] = None,
        domain_id: Annotated[
            int | None,
            Field(
                description="Global domain id (required for create; required for category picker).",
                default=None,
            ),
        ] = None,
        category_id: Annotated[
            int | None,
            Field(
                description=(
                    "Category id for subcategory picker or create (maps to category1Id). "
                    "Required when subcategory_id is set."
                ),
                default=None,
            ),
        ] = None,
        subcategory_id: Annotated[
            int | None,
            Field(
                description="Subcategory id for create (maps to category2Id).",
                default=None,
            ),
        ] = None,
        description: Annotated[
            str | None,
            Field(
                description="Business description (required for create; non-blank).",
                default=None,
            ),
        ] = None,
        definition: Annotated[
            str | None,
            Field(description="Optional formal definition for create.", default=None),
        ] = None,
        domain_name: Annotated[
            str | None,
            Field(
                description="Optional display name for placementPath on create.",
                default=None,
            ),
        ] = None,
        category_name: Annotated[
            str | None,
            Field(
                description="Optional display name for placementPath on create.",
                default=None,
            ),
        ] = None,
        subcategory_name: Annotated[
            str | None,
            Field(
                description="Optional display name for placementPath on create.",
                default=None,
            ),
        ] = None,
        publish: Annotated[
            bool,
            Field(description="When true, term is published; default is draft.", default=False),
        ] = False,
        skip_category: Annotated[
            bool,
            Field(
                description=(
                    "When true with category_skip_confirmed, user skipped category after "
                    "seeing the list; term goes under domain only."
                ),
                default=False,
            ),
        ] = False,
        category_skip_confirmed: Annotated[
            bool,
            Field(
                description=(
                    "Set true only after the user replied skip on the category picker. "
                    "Required with skip_category when categories exist under the domain."
                ),
                default=False,
            ),
        ] = False,
        skip_subcategory: Annotated[
            bool,
            Field(
                description=(
                    "When true, user skipped subcategory placement; term stays under category."
                ),
                default=False,
            ),
        ] = False,
        subcategory_skip_confirmed: Annotated[
            bool,
            Field(
                description=(
                    "Set true only after the user replied skip on the subcategory picker. "
                    "Required with skip_subcategory when subcategories exist."
                ),
                default=False,
            ),
        ] = False,
        size: Annotated[
            int,
            Field(
                description=(
                    f"Picker page size (default {MCP_DOMAIN_METADATA_SIZE_DEFAULT}; "
                    f"max {MCP_DOMAIN_METADATA_SIZE_MAX})."
                ),
                ge=1,
            ),
        ] = MCP_DOMAIN_METADATA_SIZE_DEFAULT,
        page: Annotated[
            int,
            Field(description="Picker page index (0-based).", ge=0),
        ] = 0,
    ) -> dict[str, Any]:
        """Create glossary term or list placement options (see MCP tool description)."""
        has_term = not _blank(term_name)
        has_search = not _blank(search_on)
        if has_term and has_search:
            return {
                "error": "Provide either search_on (picker) or term_name (create) — not both.",
                "status_code": 400,
            }
        if not has_term and not has_search:
            return {
                "error": "Provide search_on for placement picker or term_name to create a term.",
                "status_code": 400,
            }

        dom_early = domain_id or 0
        (
            effective_domain_name,
            effective_category_from_path,
            effective_subcategory_from_path,
        ) = _extract_placement_from_path(
            domain_name, category_name, subcategory_name
        )
        if effective_category_from_path and _blank(category_name):
            category_name = effective_category_from_path
        if effective_subcategory_from_path and _blank(subcategory_name):
            subcategory_name = effective_subcategory_from_path
        domain_name = effective_domain_name
        if has_term and not has_search and dom_early <= 0:
            try:
                async with OvalEdgeClient() as client:
                    body = await _fetch_domain_metadata(
                        client,
                        "oeglobaldomain",
                        page=page,
                        size=size,
                        domain_id=0,
                        category_id=0,
                    )
                    if effective_domain_name:
                        data = body.get("data") if isinstance(body.get("data"), dict) else {}
                        items = _extract_picker_items(data, "oeglobaldomain")
                        resolved_id, resolved_name, match_count = _resolve_domain_id_by_name(
                            items, effective_domain_name
                        )
                        if resolved_id:
                            dom_early = resolved_id
                            effective_domain_name = resolved_name or effective_domain_name
                        elif match_count > 1:
                            shaped = _shape_picker_response(
                                body,
                                "oeglobaldomain",
                                pending_term_name=str(term_name).strip(),
                                pending_description=(
                                    str(description).strip() if not _blank(description) else None
                                ),
                            )
                            shaped["domainNameMatch"] = "ambiguous"
                            shaped["requestedDomainName"] = effective_domain_name
                            shaped["agentInstruction"] = (
                                "Multiple domains match the provided domain_name. "
                                "Show formattedResponse and ask the user to reply with domain_id."
                            )
                            return shaped
                        else:
                            shaped = _shape_picker_response(
                                body,
                                "oeglobaldomain",
                                pending_term_name=str(term_name).strip(),
                                pending_description=(
                                    str(description).strip() if not _blank(description) else None
                                ),
                            )
                            shaped["domainNameMatch"] = "not_found"
                            shaped["requestedDomainName"] = effective_domain_name
                            shaped["agentInstruction"] = (
                                "No exact domain name match was found. "
                                "Show formattedResponse and ask the user to choose domain_id."
                            )
                            return shaped
                    if dom_early > 0:
                        domain_id = dom_early
                        domain_name = effective_domain_name
                    else:
                        pending_desc = str(description).strip() if not _blank(description) else None
                        return _shape_picker_response(
                            body,
                            "oeglobaldomain",
                            pending_term_name=str(term_name).strip(),
                            pending_description=pending_desc,
                        )
            except OvalEdgeError as e:
                return {"error": str(e), "status_code": e.status_code}

        if has_search:
            mode = str(search_on).strip().lower()
            if mode not in MCP_DOMAIN_METADATA_SEARCH_ON:
                allowed = ", ".join(sorted(MCP_DOMAIN_METADATA_SEARCH_ON))
                return {
                    "error": f"search_on must be one of: {allowed}.",
                    "status_code": 400,
                }
            dom = domain_id or 0
            cat = category_id or 0
            if mode == "category" and dom <= 0:
                return {
                    "error": "domain_id > 0 is required when search_on=category.",
                    "status_code": 400,
                }
            if mode == "subcategory" and cat <= 0:
                return {
                    "error": "category_id > 0 is required when search_on=subcategory.",
                    "status_code": 400,
                }
            try:
                async with OvalEdgeClient() as client:
                    body = await _fetch_domain_metadata(
                        client,
                        mode,
                        page=page,
                        size=size,
                        domain_id=dom,
                        category_id=cat,
                    )
                    pending_desc = (
                        str(description).strip()
                        if has_term and not _blank(description)
                        else None
                    )
                    pending = str(term_name).strip() if has_term else None
                    return _shape_picker_response(
                        body,
                        mode,
                        pending_term_name=pending,
                        pending_description=pending_desc,
                        domain_id=dom if dom > 0 else None,
                        domain_name=domain_name,
                        category_id=cat if cat > 0 else None,
                        category_name=category_name,
                    )
            except OvalEdgeError as e:
                return {"error": str(e), "status_code": e.status_code}

        dom_create = domain_id or 0
        cat_create = category_id or 0
        sub_create = subcategory_id or 0
        pending_name = str(term_name).strip()
        pending_desc = str(description).strip() if not _blank(description) else None
        effective_category_name = (
            str(category_name).strip()
            if isinstance(category_name, str) and not _blank(category_name)
            else None
        )
        effective_subcategory_name = (
            str(subcategory_name).strip()
            if isinstance(subcategory_name, str) and not _blank(subcategory_name)
            else None
        )
        no_categories_in_domain = False
        no_categories_in_skip_preview = False

        if sub_create > 0 and cat_create <= 0:
            return {
                "error": "category_id is required when subcategory_id is set.",
                "status_code": 400,
            }

        category_skip_ok = skip_category and category_skip_confirmed
        if dom_create > 0 and cat_create <= 0 and not category_skip_ok:
            try:
                async with OvalEdgeClient() as client:
                    body = await _fetch_domain_metadata(
                        client,
                        "category",
                        page=page,
                        size=size,
                        domain_id=dom_create,
                        category_id=0,
                    )
                    data = body.get("data") if isinstance(body.get("data"), dict) else {}
                    category_items = _extract_picker_items(data, "category")
                    if category_items:
                        if cat_create <= 0 and effective_category_name:
                            (
                                resolved_category_id,
                                resolved_category_name,
                                category_match_count,
                            ) = _resolve_category_id_by_name(
                                category_items, effective_category_name
                            )
                            if resolved_category_id:
                                cat_create = resolved_category_id
                                category_name = (
                                    resolved_category_name or effective_category_name
                                )
                            elif category_match_count > 1:
                                shaped = _shape_picker_response(
                                    body,
                                    "category",
                                    pending_term_name=pending_name,
                                    pending_description=pending_desc,
                                    domain_id=dom_create,
                                    domain_name=domain_name,
                                )
                                shaped["categoryNameMatch"] = "ambiguous"
                                shaped["requestedCategoryName"] = effective_category_name
                                shaped["agentInstruction"] = (
                                    "Multiple categories match the provided "
                                    "category_name. Show formattedResponse "
                                    "and ask the user to reply with "
                                    "category_id."
                                )
                                return shaped
                            else:
                                shaped = _shape_picker_response(
                                    body,
                                    "category",
                                    pending_term_name=pending_name,
                                    pending_description=pending_desc,
                                    domain_id=dom_create,
                                    domain_name=domain_name,
                                )
                                shaped["categoryNameMatch"] = "not_found"
                                shaped["requestedCategoryName"] = effective_category_name
                                shaped["agentInstruction"] = (
                                    "No exact category name match was found "
                                    "under the selected domain. Show "
                                    "formattedResponse and ask the user to "
                                    "choose category_id."
                                )
                                return shaped
                        if cat_create > 0:
                            # category_name was provided and resolved; continue to subcategory step.
                            pass
                        else:
                            return _shape_picker_response(
                                body,
                                "category",
                                pending_term_name=pending_name,
                                pending_description=pending_desc,
                                domain_id=dom_create,
                                domain_name=domain_name,
                            )
                    no_categories_in_domain = True
            except OvalEdgeError as e:
                return {"error": str(e), "status_code": e.status_code}

        if (
            dom_create > 0
            and cat_create > 0
            and not (skip_subcategory and subcategory_skip_confirmed)
            and sub_create <= 0
        ):
            try:
                async with OvalEdgeClient() as client:
                    body = await _fetch_domain_metadata(
                        client,
                        "subcategory",
                        page=page,
                        size=size,
                        domain_id=dom_create,
                        category_id=cat_create,
                    )
                    data = body.get("data") if isinstance(body.get("data"), dict) else {}
                    subcategory_items = _extract_picker_items(data, "subcategory")
                    if subcategory_items:
                        if effective_subcategory_name and sub_create <= 0:
                            # Resolve subcategory by provided name and skip picker when unique.
                            (
                                resolved_subcategory_id,
                                resolved_subcategory_name,
                                sub_match_count,
                            ) = _resolve_category_id_by_name(
                                [
                                    {
                                        "categoryId": x.get("subCategoryId"),
                                        "categoryName": x.get("subCategoryName"),
                                    }
                                    for x in subcategory_items
                                ],
                                effective_subcategory_name,
                            )
                            if resolved_subcategory_id:
                                sub_create = resolved_subcategory_id
                                subcategory_name = (
                                    resolved_subcategory_name or effective_subcategory_name
                                )
                            elif sub_match_count > 1:
                                shaped = _shape_picker_response(
                                    body,
                                    "subcategory",
                                    pending_term_name=pending_name,
                                    pending_description=pending_desc,
                                    domain_id=dom_create,
                                    domain_name=domain_name,
                                    category_id=cat_create,
                                    category_name=category_name,
                                )
                                shaped["subcategoryNameMatch"] = "ambiguous"
                                shaped["requestedSubcategoryName"] = effective_subcategory_name
                                shaped["agentInstruction"] = (
                                    "Multiple subcategories match the "
                                    "provided subcategory_name. Show "
                                    "formattedResponse and ask the user to "
                                    "reply with subcategory_id."
                                )
                                return shaped
                            else:
                                shaped = _shape_picker_response(
                                    body,
                                    "subcategory",
                                    pending_term_name=pending_name,
                                    pending_description=pending_desc,
                                    domain_id=dom_create,
                                    domain_name=domain_name,
                                    category_id=cat_create,
                                    category_name=category_name,
                                )
                                shaped["subcategoryNameMatch"] = "not_found"
                                shaped["requestedSubcategoryName"] = effective_subcategory_name
                                shaped["agentInstruction"] = (
                                    "No exact subcategory name match was "
                                    "found under the selected category. Show "
                                    "formattedResponse and ask the user to "
                                    "choose subcategory_id."
                                )
                                return shaped
                        if sub_create > 0:
                            pass
                        else:
                            return _shape_picker_response(
                                body,
                                "subcategory",
                                pending_term_name=pending_name,
                                pending_description=pending_desc,
                                domain_id=dom_create,
                                domain_name=domain_name,
                                category_id=cat_create,
                                category_name=category_name,
                            )
            except OvalEdgeError as e:
                return {"error": str(e), "status_code": e.status_code}

        skip_category_preview_items: list[dict[str, Any]] = []
        skip_subcategory_preview_items: list[dict[str, Any]] = []

        if _blank(description):
            if category_skip_ok and dom_create > 0 and cat_create <= 0:
                try:
                    async with OvalEdgeClient() as client:
                        body = await _fetch_domain_metadata(
                            client,
                            "category",
                            page=page,
                            size=size,
                            domain_id=dom_create,
                            category_id=0,
                        )
                        data = body.get("data") if isinstance(body.get("data"), dict) else {}
                        skip_category_preview_items = _extract_picker_items(data, "category")
                        if not skip_category_preview_items:
                            no_categories_in_skip_preview = True
                except OvalEdgeError as e:
                    return {"error": str(e), "status_code": e.status_code}

            if (
                dom_create > 0
                and cat_create > 0
                and (skip_subcategory and subcategory_skip_confirmed)
                and sub_create <= 0
            ):
                try:
                    async with OvalEdgeClient() as client:
                        body = await _fetch_domain_metadata(
                            client,
                            "subcategory",
                            page=page,
                            size=size,
                            domain_id=dom_create,
                            category_id=cat_create,
                        )
                        data = body.get("data") if isinstance(body.get("data"), dict) else {}
                        skip_subcategory_preview_items = _extract_picker_items(
                            data, "subcategory"
                        )
                except OvalEdgeError as e:
                    return {"error": str(e), "status_code": e.status_code}

            dom_label = domain_name or f"domain_id {dom_create}"
            placement = dom_label
            if cat_create > 0:
                cat_label = category_name or f"category_id {cat_create}"
                placement = f"{placement} > {cat_label}"
            if sub_create > 0:
                sub_label = subcategory_name or f"subcategory_id {sub_create}"
                placement = f"{placement} > {sub_label}"

            cat_preview = (
                "Available categories under this domain (you requested to skip):\n"
                f"{_format_placement_options('category', skip_category_preview_items)}\n\n"
                if skip_category_preview_items
                else ""
            )
            subcat_preview = (
                "Available subcategories under this category (you requested to skip):\n"
                f"{_format_placement_options('subcategory', skip_subcategory_preview_items)}\n\n"
                if skip_subcategory_preview_items
                else ""
            )

            out = {
                "ok": False,
                "awaitingUserInput": True,
                "workflowPhase": "collect_description",
                "formattedResponse": (
                    f'**Create glossary term: {pending_name}**\n\n'
                    + (
                        "No categories are available under the selected domain. "
                        "The term will be created directly under the domain.\n\n"
                        if (no_categories_in_domain or no_categories_in_skip_preview)
                        else ""
                    )
                    + (
                        "Categories are available under the selected domain.\n\n"
                        if skip_category_preview_items
                        else ""
                    )
                    + f"{cat_preview}"
                    + f"{subcat_preview}"
                    + f"Placement **{placement}** is set. A business **description** is "
                    + "required before the term can be created. Ask the user for a description, "
                    + "then call again with `term_name`, `domain_id`, `description`, and the same "
                    + "placement ids (or skip flags)."
                ),
                "pendingTermName": pending_name,
                "pendingDomainId": dom_create,
                "pendingCategoryId": cat_create if cat_create > 0 else None,
                "pendingSubcategoryId": sub_create if sub_create > 0 else None,
                "hasCategoriesInDomain": (
                    False
                    if (no_categories_in_domain or no_categories_in_skip_preview)
                    else (True if skip_category_preview_items else None)
                ),
                "categoryAvailabilityMessage": (
                    "No categories are available under the selected domain."
                    if (no_categories_in_domain or no_categories_in_skip_preview)
                    else (
                        "Categories are available under the selected domain."
                        if skip_category_preview_items
                        else None
                    )
                ),
                "agentInstruction": (
                    "Show categoryAvailabilityMessage to the user when provided. "
                    "Ask the user for a description; do not invent one. "
                    "Re-call with description and the same placement."
                ),
                "status_code": 400,
            }
            if skip_category_preview_items:
                out["placementOptions"] = skip_category_preview_items
                out["formattedPlacementOptions"] = _format_placement_options(
                    "category", skip_category_preview_items
                )
            elif skip_subcategory_preview_items:
                out["placementOptions"] = skip_subcategory_preview_items
                out["formattedPlacementOptions"] = _format_placement_options(
                    "subcategory", skip_subcategory_preview_items
                )
            return out
        post_body: dict[str, object] = {
            "termName": str(term_name).strip(),
            "domainId": dom_create,
            "description": str(description).strip(),
            "category1Id": cat_create,
            "category2Id": sub_create,
            "publish": publish,
        }
        if not _blank(definition):
            post_body["definition"] = str(definition).strip()
        try:
            async with OvalEdgeClient() as client:
                body = await client.post(MCP_PATH_GLOSSARY_TERMS, body=post_body)
                if isinstance(body, dict):
                    return _shape_create_response(
                        body,
                        term_name=str(term_name).strip(),
                        domain_id=dom_create,
                        domain_name=domain_name,
                        category_id=cat_create if cat_create > 0 else None,
                        category_name=category_name,
                        subcategory_id=sub_create if sub_create > 0 else None,
                        subcategory_name=subcategory_name,
                        placement_note=(
                            "No categories are available under this domain; "
                            "created directly under domain."
                            if no_categories_in_domain and cat_create <= 0
                            else None
                        ),
                    )
                return body
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
                    return _normalize_datastory_nav_links(body)
                return body
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
