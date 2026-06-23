"""Tag lookup and create-tag helpers."""

from __future__ import annotations

import html
import time
from typing import Any

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import (
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
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
from server.tools.common import as_dict as _as_dict
from server.tools.common import blank as _blank
from server.tools.common.descriptions import classify_tool_desc
from server.tools.governance._shared import (
    _CREATE_CONFIRM_AGENT_INSTRUCTION,
    _positive_int,
)

_DESC_TAGS = classify_tool_desc(
    "Look up OETAG (tag) document(s) by id or name from Elasticsearch; name search "
    "may return multiple hits.\n\n"
    f"Backend: GET {MCP_PATH_TAGS} (objectId OR tagName — mutually exclusive).\n"
    f"Optional query param limit (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT} on server; "
    f"this client caps at {MCP_GLOSSARY_TAGS_LIMIT_MAX}).\n\n"
    "Provide either tag_name or object_id, never both.\n\n"
    "Hierarchy: set include_parent=true when the user asks for the parent tag; "
    "include_children=true when they ask for child tags (or both). The API enriches "
    "each hit with parentTag and/or childTags from tagrelationship.\n\n"
    "Each hit includes relative navLink plus redirectUrl (absolute, from OVALEDGE_BASE_URL). "
    "When hierarchy flags are set, formattedResponse summarizes tag, parent, and children."
)
_DESC_CREATE_TAG = classify_tool_desc(
    "Create a new OETAG (guided pickers). Flow depends on tagSecurityMode from create-options.\n\n"
    f"Backend: GET {MCP_PATH_TAGS_CREATE_OPTIONS}, GET {MCP_PATH_TAGS_PARENT_OPTIONS}, "
    f"POST {MCP_PATH_TAGS}.\n\n"
    "**User-facing:** Present formattedResponse; never guess master_tag_id or parent_tag_id. "
    "SECURE: master required, parent optional. OPEN: parent optional, no master step.\n\n"
    "Complete placement steps → confirm_create preview → POST only after "
    "create_confirmed_by_user=true.\n\n"
    "Full OPEN/SECURE steps: docs://ovaledge/tags_guide and workflow prompt "
    "`create_governance_tag`."
)
def _tag_nav_from_item(item: dict[str, Any]) -> str:
    """Resolve tag summary nav hash from navLink or tag metadata."""
    nav = extract_hash_nav_link(str(item.get("navLink") or item.get("hyperlink") or ""))
    if nav and "objecttype=" in nav.lower():
        return nav
    oid = item.get("objectId")
    if not isinstance(oid, int) or oid <= 0:
        return nav
    parent_id = _positive_int(item.get("parentObjectId"))
    master_id: int | None = None
    tag_details = item.get("tagDetails")
    if isinstance(tag_details, list):
        for td in tag_details:
            if not isinstance(td, dict) or not td.get("isDirectTag"):
                continue
            master_id = _positive_int(td.get("masterTagId"))
            break
    hierarchies = item.get("parentHierarchies")
    if master_id is None and isinstance(hierarchies, list) and hierarchies:
        first = hierarchies[0]
        if isinstance(first, dict):
            master_id = _positive_int(first.get("id"))
    return _tag_summary_page_nav(
        oid,
        catalog=item,
        master_tag_id=master_id,
        parent_tag_id=parent_id,
    )


def _enrich_tag_hierarchy_nav(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize nav links on parent/child hierarchy items."""
    out = dict(item)
    nav = item.get("navLink")
    if isinstance(nav, str) and nav.strip():
        out["navLink"] = nav.strip()
        out["redirectUrl"] = build_absolute_nav_url(nav.strip())
    elif isinstance(item.get("redirectUrl"), str) and item["redirectUrl"].strip():
        out["redirectUrl"] = item["redirectUrl"].strip()
    return out


def _enrich_tag_nav(item: dict[str, Any]) -> dict[str, Any]:
    """Add absolute redirectUrl from relative navLink (lookup hits)."""
    out = dict(item)
    nav = _tag_nav_from_item(out)
    if nav:
        out["navLink"] = nav
        out["redirectUrl"] = build_absolute_nav_url(nav)
    parent = item.get("parentTag")
    if isinstance(parent, dict):
        out["parentTag"] = _enrich_tag_hierarchy_nav(parent)
    elif "parentTag" in item:
        out["parentTag"] = parent
    children = item.get("childTags")
    if isinstance(children, list):
        out["childTags"] = [
            _enrich_tag_hierarchy_nav(c) for c in children if isinstance(c, dict)
        ]
    elif "childTags" in item:
        out["childTags"] = children
    return out


def _tag_has_hierarchy_fields(item: dict[str, Any]) -> bool:
    return "parentTag" in item or "childTags" in item


def _format_tag_hierarchy_line(item: dict[str, Any]) -> str:
    name = str(item.get("objectName") or "?")
    oid = item.get("objectId", "?")
    line = f"- {name} (id {oid})"
    if item.get("hasChildren"):
        line += " [has children]"
    url = item.get("redirectUrl") or item.get("navLink")
    if isinstance(url, str) and url.strip():
        line += f" — {markdown_link('Open', url.strip())}"
    return line


def _format_tag_lookup_display(hit: dict[str, Any]) -> str:
    lines: list[str] = []
    name = str(hit.get("objectName") or "?")
    oid = hit.get("objectId", "?")
    lines.append(f"**Tag:** {name} (id {oid})")
    url = hit.get("redirectUrl") or hit.get("navLink")
    if isinstance(url, str) and url.strip():
        lines.append(markdown_link("Open tag", url.strip()))
    if "parentTag" in hit:
        parent = hit.get("parentTag")
        if isinstance(parent, dict):
            pname = parent.get("objectName") or "?"
            pid = parent.get("objectId", "?")
            lines.append(f"**Parent tag:** {pname} (id {pid})")
            purl = parent.get("redirectUrl") or parent.get("navLink")
            if isinstance(purl, str) and purl.strip():
                lines.append(markdown_link("Open parent", purl.strip()))
        else:
            lines.append("**Parent tag:** none")
    if "childTags" in hit:
        children = hit.get("childTags")
        if isinstance(children, list) and children:
            lines.append(f"**Child tags ({len(children)}):**")
            lines.extend(
                _format_tag_hierarchy_line(c) for c in children if isinstance(c, dict)
            )
        else:
            lines.append("**Child tags:** none")
    return "\n".join(lines)


def _enrich_tag_lookup_response(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize nav links on tags GET responses (data only, no top-level mirror)."""
    if not body.get("ok"):
        return body
    out = dict(body)
    data = body.get("data")
    formatted_parts: list[str] = []
    if isinstance(data, list):
        enriched_list = [_enrich_tag_nav(x) for x in data if isinstance(x, dict)]
        out["data"] = enriched_list
        if any(_tag_has_hierarchy_fields(h) for h in enriched_list):
            formatted_parts = [_format_tag_lookup_display(h) for h in enriched_list]
    elif isinstance(data, dict):
        enriched_hit = _enrich_tag_nav(data)
        out["data"] = enriched_hit
        if _tag_has_hierarchy_fields(enriched_hit):
            formatted_parts = [_format_tag_lookup_display(enriched_hit)]
    if formatted_parts:
        formatted = "\n\n".join(formatted_parts)
        out["formattedResponse"] = formatted
        if isinstance(out["data"], dict):
            out["data"]["formattedResponse"] = formatted
    return out


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
    # Common UI/app synonyms (case-insensitive) for agent/user convenience.
    "governancerole4": "governance_role_4",
    "governancerole5": "governance_role_5",
    "governancerole6": "governance_role_6",
    "govrole4": "governance_role_4",
    "govrole5": "governance_role_5",
    "govrole6": "governance_role_6",
    "gov_role_4": "governance_role_4",
    "gov_role_5": "governance_role_5",
    "gov_role_6": "governance_role_6",
}


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
    if catalog_nav and "objecttype=" in catalog_nav.lower():
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
        if row.get("hasChildren") is True:
            entry["hasChildren"] = True
        items.append(entry)
    items.sort(key=lambda p: (str(p.get("tagName") or "").lower(), p["parentTagId"]))
    return items


def _parent_choice_label(p: dict[str, Any]) -> str:
    pid = p["parentTagId"]
    pname = p.get("tagName") or "(unnamed)"
    suffix = ""
    if p.get("hasChildren"):
        suffix = f" (has children — browse with browse_parent_tag_id={pid})"
    elif p.get("rootTag"):
        suffix = " (root/master — use parent_tag_id; backend sets master)"
    return f"  - parentTagId={pid}: {pname}{suffix}"


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
        lines.append(_parent_choice_label(p))
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
    *,
    browse_meta: dict[str, Any] | None = None,
) -> str:
    label = master_tag_name or f"master {master_tag_id}"
    lines = [
        "SECURE mode — Step 2 of 2 (parent selection under the chosen master).",
        f"Master tag selected: {label} (masterTagId={master_tag_id}) — required step done.",
    ]
    if browse_meta and browse_meta.get("browseParentTagId"):
        browse_id = browse_meta["browseParentTagId"]
        browse_name = browse_meta.get("browseParentTagName") or f"tag {browse_id}"
        lines.append(
            f"Browsing children of **{browse_name}** (browseParentTagId={browse_id})."
        )
    lines.extend([
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
        "  - **Browse deeper** (when a row shows has children): call create_tag again with "
        "browse_parent_tag_id=<that parentTagId> (same master_tag_id + confirmations).",
        "",
    ])
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
        lines.append(_parent_choice_label(p))
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
        master_name, parents, _ = await _fetch_parent_choices_for_master(
            client, master_tag_id, secure_guidance
        )
        parent_name = _tag_name_from_parent_list(parents, parent_tag_id)
        if (
            parent_name is None
            and parent_tag_id is not None
            and parent_tag_id > 0
        ):
            nested_row = await _find_parent_choice_under_master(
                client, master_tag_id, parent_tag_id, secure_guidance
            )
            if nested_row is not None:
                parent_name = nested_row.get("tagName")
                if isinstance(parent_name, str):
                    parent_name = parent_name.strip() or None
        if parent_name is None and parent_tag_id is not None and parent_tag_id > 0:
            parent_name = await _lookup_tag_name_by_id(client, parent_tag_id)
    elif parent_tag_id is not None and parent_tag_id > 0:
        open_parents = await _fetch_open_parent_choices(client)
        parent_name = _tag_name_from_parent_list(open_parents, parent_tag_id)
        if parent_name is None:
            parent_name = await _lookup_tag_name_by_id(client, parent_tag_id)
    return master_name, parent_name


async def _lookup_tag_name_by_id(client: OvalEdgeClient, object_id: int) -> str | None:
    try:
        result = await client.get(MCP_PATH_TAGS, params={"objectId": object_id})
    except OvalEdgeError:
        return None
    if not isinstance(result, dict) or not result.get("ok"):
        return None
    data = result.get("data")
    if isinstance(data, dict):
        name = data.get("objectName") or data.get("tagName") or data.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


async def _fetch_open_parent_choices(
    client: OvalEdgeClient,
    *,
    browse_parent_tag_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Open mode parent list — same sources as Create Tag UI (tag/list / create-options).

    Prefer GET /mcp/tags/create-options parentTagChoices, then parent-options.
    """
    if browse_parent_tag_id is not None and browse_parent_tag_id > 0:
        try:
            result = await client.get(
                MCP_PATH_TAGS_PARENT_OPTIONS,
                params={"browseParentTagId": browse_parent_tag_id},
            )
            if isinstance(result, dict) and result.get("ok"):
                data = result.get("data")
                if isinstance(data, dict):
                    return _build_user_selectable_parents(data.get("parentTagChoices"))
        except OvalEdgeError:
            pass
        return []
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
    browse_parent_tag_id: int | None = None,
) -> dict[str, Any]:
    lines = [
        "STOP — do not create the tag yet.",
        f"Tag name: {tag_name}",
    ]
    if browse_parent_tag_id is not None and browse_parent_tag_id > 0:
        lines.append(
            f"Browsing children of browseParentTagId={browse_parent_tag_id}."
        )
    lines.extend([
        _format_open_parent_list_for_user(parents),
        "",
        "Ask the human: use a parent from the list, browse deeper with "
        "browse_parent_tag_id when hasChildren=true, or no parent.",
        "Next create_tag call: parent_step_completed_by_user=true plus their choice.",
    ])
    extra: dict[str, Any] = {
        "tagSecurityMode": "open",
        "masterTagRequired": False,
        "parentTagRequired": False,
    }
    if browse_parent_tag_id is not None and browse_parent_tag_id > 0:
        extra["browseParentTagId"] = browse_parent_tag_id
    return _parent_picker_guidance_payload(
        tag_name=tag_name,
        parents=parents,
        formatted_response="\n".join(lines),
        extra=extra,
    )


async def _fetch_parent_choices_for_master(
    client: OvalEdgeClient,
    master_tag_id: int,
    secure_guidance: dict[str, Any] | None,
    *,
    browse_parent_tag_id: int | None = None,
) -> tuple[str | None, list[dict[str, Any]], dict[str, Any]]:
    master_name = _master_label_from_guidance(secure_guidance, master_tag_id)
    browse_meta: dict[str, Any] = {}
    params: dict[str, Any] = {"masterTagId": master_tag_id}
    if browse_parent_tag_id is not None and browse_parent_tag_id > 0:
        params["browseParentTagId"] = browse_parent_tag_id
    try:
        result = await client.get(MCP_PATH_TAGS_PARENT_OPTIONS, params=params)
        if isinstance(result, dict) and result.get("ok"):
            data = result.get("data")
            if isinstance(data, dict):
                if not master_name and isinstance(data.get("masterTagName"), str):
                    master_name = data["masterTagName"]
                browse_id = data.get("browseParentTagId")
                if isinstance(browse_id, int) and browse_id > 0:
                    browse_meta["browseParentTagId"] = browse_id
                    browse_name = data.get("browseParentTagName")
                    if isinstance(browse_name, str) and browse_name.strip():
                        browse_meta["browseParentTagName"] = browse_name.strip()
                return (
                    master_name,
                    _build_user_selectable_parents(data.get("parentTagChoices")),
                    browse_meta,
                )
    except OvalEdgeError:
        pass
    if (
        browse_parent_tag_id is None or browse_parent_tag_id <= 0
    ) and secure_guidance and isinstance(secure_guidance.get("masterTagChoices"), list):
        parents_raw: list[dict[str, Any]] = []
        for item in _iter_master_choice_dicts(secure_guidance["masterTagChoices"]):
            if item.get("masterTagId") != master_tag_id:
                continue
            raw = item.get("parentTagChoices")
            if isinstance(raw, list):
                parents_raw = [p for p in raw if isinstance(p, dict)]
            break
        return master_name, _build_user_selectable_parents(parents_raw), browse_meta
    return master_name, [], browse_meta


_PARENT_BROWSE_MAX_DEPTH = 12


async def _find_parent_choice_under_master(
    client: OvalEdgeClient,
    master_tag_id: int,
    parent_tag_id: int,
    secure_guidance: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return parent choice row when parent_tag_id is under master (top or nested browse)."""
    if parent_tag_id <= 0:
        return None
    _, top_parents, _ = await _fetch_parent_choices_for_master(
        client, master_tag_id, secure_guidance
    )
    for row in top_parents:
        if row.get("parentTagId") == parent_tag_id:
            return row
    queue = [p["parentTagId"] for p in top_parents if p.get("hasChildren")]
    seen: set[int] = set()
    depth = 0
    while queue and depth < _PARENT_BROWSE_MAX_DEPTH:
        depth += 1
        browse_id = queue.pop(0)
        if browse_id in seen:
            continue
        seen.add(browse_id)
        _, nested, _ = await _fetch_parent_choices_for_master(
            client,
            master_tag_id,
            secure_guidance,
            browse_parent_tag_id=browse_id,
        )
        for row in nested:
            if row.get("parentTagId") == parent_tag_id:
                return row
        for p in nested:
            if p.get("hasChildren"):
                queue.append(p["parentTagId"])
    return None


async def _parent_tag_is_allowed_under_master(
    client: OvalEdgeClient,
    master_tag_id: int,
    parent_tag_id: int,
    secure_guidance: dict[str, Any] | None,
) -> bool:
    """True when parent_tag_id appears in top-level or nested parent-options under master."""
    found = await _find_parent_choice_under_master(
        client, master_tag_id, parent_tag_id, secure_guidance
    )
    return found is not None


def _format_parent_selection_guidance(
    *,
    master_tag_id: int,
    master_tag_name: str | None,
    parents: list[dict[str, Any]],
    tag_name: str,
    browse_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lines = [
        "STOP — do not create the tag yet.",
        f"Tag name: {tag_name}",
        _format_parent_list_for_user(
            master_tag_id, master_tag_name, parents, browse_meta=browse_meta
        ),
    ]
    extra: dict[str, Any] = {
        "tagSecurityMode": "secure",
        "masterTagRequired": True,
        "parentTagRequired": False,
        "masterTagId": master_tag_id,
        "masterTagName": master_tag_name,
        "createUnderMasterOnlyOption": _create_under_master_option(
            master_tag_id, master_tag_name
        ),
    }
    if browse_meta:
        extra.update(browse_meta)
    return _parent_picker_guidance_payload(
        tag_name=tag_name,
        parents=parents,
        formatted_response="\n".join(lines),
        extra=extra,
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

