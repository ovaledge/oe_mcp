import html
import re
import time
from html import unescape
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import (
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_TAGS,
    MCP_PATH_TAGS_CREATE_OPTIONS,
    MCP_PATH_TAGS_PARENT_OPTIONS,
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
    "OVALEDGE_TAG_AUTO_DESCRIPTION=false).\n"
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


# In-memory proof that step 1 (parent picker) ran for a tag name — not exposed to clients.
_PENDING_PARENT_PICKER_TTL_SEC = 3600
_pending_parent_picker_expiry: dict[str, float] = {}


def _register_parent_picker_shown(tag_name: str) -> None:
    key = tag_name.strip().lower()
    _pending_parent_picker_expiry[key] = time.time() + _PENDING_PARENT_PICKER_TTL_SEC


def _consume_parent_picker_shown(tag_name: str) -> bool:
    """One-time check that the parent list was shown for this tag name (MCP-internal)."""
    key = tag_name.strip().lower()
    exp = _pending_parent_picker_expiry.pop(key, None)
    if exp is None:
        return False
    return exp >= time.time()


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
    from server.config import settings

    return settings.ovaledge_tag_auto_description


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
    body = exc.body if isinstance(exc.body, dict) else {}
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    message = body.get("message") if isinstance(body.get("message"), str) else str(exc)
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

    @mcp.tool(description=_DESC_CREATE_TAG)
    async def create_tag(
        tag_name: Annotated[
            str,
            Field(description="Name of the new tag (required)."),
        ],
        description: Annotated[
            str | None,
            Field(
                description=(
                    "Optional wiki/HTML description for the tag. When omitted on the final "
                    "create call, MCP generates a short HTML description from tag_name and "
                    "master/parent names (set OVALEDGE_TAG_AUTO_DESCRIPTION=false to skip)."
                ),
                default=None,
            ),
        ] = None,
        master_tag_id: Annotated[
            int | None,
            Field(
                description=(
                    "SECURE mode only (required after step 1): masterTagId the human chose "
                    "from userSelectableMasters. Never set in OPEN mode. Omit on first call "
                    "(tag_name only)."
                ),
                default=None,
            ),
        ] = None,
        master_tag_id_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Secure mode: must be true when master_tag_id is set, and only after "
                    "the human explicitly selected that id from masterTagChoices."
                ),
                default=False,
            ),
        ] = False,
        parent_tag_id: Annotated[
            int | None,
            Field(
                description=(
                    "Optional. SECURE: parent under the chosen master (from step 2 list). "
                    "OPEN: any parent from userSelectableParents. Omit when creating "
                    "under master only (secure) or with no parent (open)."
                ),
                default=None,
            ),
        ] = None,
        parent_tag_id_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Step 3: true only after the human picked parentTagId from "
                    "userSelectableParents for the chosen master."
                ),
                default=False,
            ),
        ] = False,
        create_directly_under_master: Annotated[
            bool,
            Field(
                description=(
                    "SECURE: create as direct child of masterTagId only (no parentTagId). "
                    "OPEN: create with no parent (do not send masterTagId). Set after user "
                    "sees parent options."
                ),
                default=False,
            ),
        ] = False,
        parent_step_completed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Required on the final create call (open and secure): true only after "
                    "the human was shown userSelectableParents and chose a parent or "
                    "declined. Never set on the first call (tag_name only)."
                ),
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Create tag (see MCP tool description)."""
        name = tag_name.strip() if tag_name is not None else ""
        if not name:
            return {
                "error": "tag_name is required.",
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                secure_mode, valid_master_ids = await _fetch_tag_create_context(client)
                secure_guidance: dict[str, Any] | None = None
                if secure_mode:
                    secure_guidance = await _load_secure_create_guidance(client)
                    if master_tag_id is None or master_tag_id <= 0:
                        if secure_guidance is not None:
                            return secure_guidance
                        return {
                            "ok": False,
                            "status_code": 422,
                            "message": "Secure mode requires a human-selected master tag.",
                            "userMustSelectMasterTag": True,
                            "awaitingUserSelection": True,
                            "doNotCreateTag": True,
                        }
                    if not master_tag_id_confirmed_by_user:
                        return _block_llm_master_selection(
                            secure_guidance,
                            master_tag_id=master_tag_id,
                        )
                    if not valid_master_ids or master_tag_id not in valid_master_ids:
                        return _reject_invented_master_tag_id(
                            master_tag_id,
                            valid_master_ids,
                            secure_guidance,
                        )
                    if parent_tag_id is not None and parent_tag_id > 0:
                        if not parent_tag_id_confirmed_by_user:
                            return _block_llm_parent_selection(
                                secure_guidance,
                                parent_tag_id=parent_tag_id,
                            )
                        # Validate via parent-options API (not nested create-options
                        # parentTagChoices, which are intentionally empty in secure mode).
                        _, parents_for_validate = await _fetch_parent_choices_for_master(
                            client, master_tag_id, secure_guidance
                        )
                        allowed_parents = {
                            p["parentTagId"] for p in parents_for_validate
                        }
                        if allowed_parents and parent_tag_id not in allowed_parents:
                            return {
                                "ok": False,
                                "status_code": 422,
                                "message": (
                                    f"parent_tag_id {parent_tag_id} is not under "
                                    f"master_tag_id {master_tag_id}."
                                ),
                                "doNotCreateTag": True,
                                "formattedResponse": (
                                    f"parent_tag_id {parent_tag_id} is not listed under "
                                    f"master_tag_id {master_tag_id}. Ask the human to pick "
                                    "from userSelectableParents or decline with "
                                    "create_directly_under_master=true and "
                                    "parent_step_completed_by_user=true."
                                ),
                            }
                    if not _parent_choice_finalized(
                        secure_mode=True,
                        parent_tag_id=parent_tag_id,
                        parent_tag_id_confirmed_by_user=parent_tag_id_confirmed_by_user,
                        create_directly_under_master=create_directly_under_master,
                        parent_step_completed_by_user=parent_step_completed_by_user,
                    ):
                        master_name, parents = await _fetch_parent_choices_for_master(
                            client, master_tag_id, secure_guidance
                        )
                        return _format_parent_selection_guidance(
                            master_tag_id=master_tag_id,
                            master_tag_name=master_name,
                            parents=parents,
                            tag_name=name,
                        )
                    if not _consume_parent_picker_shown(name):
                        master_name, parents = await _fetch_parent_choices_for_master(
                            client, master_tag_id, secure_guidance
                        )
                        out = _format_parent_selection_guidance(
                            master_tag_id=master_tag_id,
                            master_tag_name=master_name,
                            parents=parents,
                            tag_name=name,
                        )
                        out["message"] = (
                            "Parent picker was not completed for this tag name. "
                            "Present userSelectableParents to the user first, then "
                            "retry with parent_step_completed_by_user=true and their choice."
                        )
                        return out

                else:
                    # OPEN mode: never run master-tag step; only optional parent list.
                    if master_tag_id is not None and master_tag_id > 0:
                        return {
                            "ok": False,
                            "status_code": 422,
                            "message": (
                                "OPEN mode does not use master_tag_id. Show "
                                "userSelectableParents only, or create without parent."
                            ),
                            "tagSecurityMode": "open",
                            "doNotCreateTag": True,
                            "formattedResponse": (
                                "OPEN mode: do not set master_tag_id. Call with tag_name only "
                                "first to see parent options, then create with optional "
                                "parent_tag_id or create_directly_under_master=true."
                            ),
                        }
                    open_parents: list[dict[str, Any]] = []
                    if parent_tag_id is not None and parent_tag_id > 0:
                        if not parent_tag_id_confirmed_by_user:
                            open_parents = await _fetch_open_parent_choices(client)
                            guidance = _format_open_parent_selection_guidance(
                                parents=open_parents,
                                tag_name=name,
                            )
                            return _block_llm_parent_selection(
                                guidance,
                                parent_tag_id=parent_tag_id,
                            )
                        open_parents = await _fetch_open_parent_choices(client)
                        allowed_open = {
                            p["parentTagId"] for p in open_parents
                        }
                        if allowed_open and parent_tag_id not in allowed_open:
                            return {
                                "ok": False,
                                "status_code": 422,
                                "message": (
                                    f"parent_tag_id {parent_tag_id} is not in "
                                    "userSelectableParents."
                                ),
                                "doNotCreateTag": True,
                                "tagSecurityMode": "open",
                                "userSelectableParents": open_parents,
                                "formattedResponse": (
                                    f"parent_tag_id {parent_tag_id} is not listed in "
                                    "userSelectableParents. Ask the human to pick from the "
                                    "suggested list or create_directly_under_master=true "
                                    "(no parent, open mode)."
                                ),
                            }
                    if not _parent_choice_finalized(
                        secure_mode=False,
                        parent_tag_id=parent_tag_id,
                        parent_tag_id_confirmed_by_user=parent_tag_id_confirmed_by_user,
                        create_directly_under_master=create_directly_under_master,
                        parent_step_completed_by_user=parent_step_completed_by_user,
                    ):
                        open_parents = await _fetch_open_parent_choices(client)
                        return _format_open_parent_selection_guidance(
                            parents=open_parents,
                            tag_name=name,
                        )
                    if not _consume_parent_picker_shown(name):
                        open_parents = await _fetch_open_parent_choices(client)
                        out = _format_open_parent_selection_guidance(
                            parents=open_parents,
                            tag_name=name,
                        )
                        out["message"] = (
                            "Parent picker was not completed for this tag name. "
                            "Present userSelectableParents to the user first, then "
                            "retry with parent_step_completed_by_user=true and their choice."
                        )
                        return out

                master_name_for_desc, parent_name_for_desc = (
                    await _resolve_tag_hierarchy_names_for_create(
                        client,
                        secure_mode=secure_mode,
                        master_tag_id=master_tag_id,
                        parent_tag_id=parent_tag_id,
                        secure_guidance=secure_guidance,
                    )
                )
                body = _q(
                    tagName=name,
                    description=_resolve_create_tag_description(
                        name,
                        description,
                        master_tag_name=master_name_for_desc,
                        parent_tag_name=parent_name_for_desc,
                    ),
                    masterTagId=(
                        master_tag_id
                        if secure_mode
                        and master_tag_id is not None
                        and master_tag_id > 0
                        else None
                    ),
                    parentTagId=(
                        parent_tag_id if parent_tag_id is not None and parent_tag_id > 0 else None
                    ),
                )
                created = await client.post(MCP_PATH_TAGS, body=body)
                if not isinstance(created, dict) or not created.get("ok"):
                    return created
                data = created.get("data")
                tag_id: int | None = None
                if isinstance(data, dict):
                    raw_id = data.get("tagId")
                    if isinstance(raw_id, int) and raw_id > 0:
                        tag_id = raw_id
                lookup_body: dict[str, Any] | None = None
                if tag_id is not None:
                    lookup_body = await _lookup_tag_after_create(client, tag_id)
                desc_val = body.get("description")
                create_desc = desc_val if isinstance(desc_val, str) else None
                return _enrich_create_tag_response(
                    created,
                    description=create_desc,
                    master_tag_id=master_tag_id,
                    parent_tag_id=parent_tag_id,
                    lookup_body=lookup_body,
                )
        except OvalEdgeError as e:
            if e.status_code == 422 and isinstance(e.body.get("data"), dict):
                guidance = _format_create_tag_input_required(e)
                if master_tag_id is not None and master_tag_id > 0:
                    valid = _master_tag_ids_from_guidance_data(e.body["data"])
                    if valid and master_tag_id not in valid:
                        return _reject_invented_master_tag_id(
                            master_tag_id, valid, guidance
                        )
                return guidance
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
