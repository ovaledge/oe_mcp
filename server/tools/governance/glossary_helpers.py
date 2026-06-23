"""Glossary lookup and create-term helpers."""

from __future__ import annotations

import re
from typing import Any

from server.client import OvalEdgeClient
from server.constants import (
    MCP_DOMAIN_METADATA_SIZE_MAX,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_PATH_DOMAIN_METADATA,
    MCP_PATH_GLOSSARY_TERMS,
)
from server.nav_links import build_absolute_nav_url, extract_hash_nav_link
from server.tools.common import as_dict as _as_dict
from server.tools.common import blank as _blank
from server.tools.governance._shared import _CREATE_CONFIRM_AGENT_INSTRUCTION, _cell

_DESC_GLOSSARY = (
    "Look up business glossary term(s) by id, name, or glossary placement "
    "(domain / category / subcategory). Server object type is always glossary.\n\n"
    f"Backend: GET {MCP_PATH_GLOSSARY_TERMS}. Use exactly one lookup mode:\n"
    "1. **object_id** — single term by id.\n"
    "2. **term_name** — name search (may return multiple hits).\n"
    "3. **Placement** — list terms under domain, category, or subcategory using "
    "domain_id or domain_name (required), plus optional category_id/category_name and "
    "subcategory_id/subcategory_name. Domain-only returns all terms in the domain; "
    "category returns terms directly under that category; subcategory returns terms "
    "in that subcategory.\n\n"
    f"Optional limit (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT}; capped at "
    f"{MCP_GLOSSARY_TAGS_LIMIT_MAX}).\n\n"
    "Do not combine object_id, term_name, and placement filters in one call.\n\n"
    "Each hit includes relative navLink plus redirectUrl (absolute, from OVALEDGE_BASE_URL)."
)
_DESC_CREATE_GLOSSARY = (
    "Create a business glossary term (guided pickers) or list domain/category/subcategory "
    "options.\n\n"
    f"Backend picker: GET {MCP_PATH_DOMAIN_METADATA}. "
    f"Backend create: POST {MCP_PATH_GLOSSARY_TERMS}.\n\n"
    "**User-facing:** Present formattedResponse from every picker/confirm step; never guess "
    "domain_id, category_id, subcategory_id, or description.\n\n"
    "Flow: term_name → domain (or domain_name on first call) → optional category/subcategory "
    "pickers → required description → confirm_create preview → POST only after "
    "create_confirmed_by_user=true.\n\n"
    "Full step-by-step: docs://ovaledge/glossary_guide and workflow prompt "
    "`create_business_glossary_term`."
)
def _glossary_nav_from_item(item: dict[str, Any]) -> str:
    """Resolve glossary nav hash from navLink, legacy string termDetails, or object id."""
    nav = extract_hash_nav_link(str(item.get("navLink") or ""))
    if nav:
        return nav
    term_details = item.get("termDetails")
    if isinstance(term_details, str):
        nav = extract_hash_nav_link(term_details)
        if nav:
            return nav
    oid = item.get("objectId")
    if oid is None:
        oid = item.get("businessGlossaryId")
    if isinstance(oid, int) and oid > 0:
        return f"#nav/glossary?browse=summary&id={oid}"
    return ""


def _enrich_glossary_term_nav(item: dict[str, Any]) -> dict[str, Any]:
    """Add absolute redirectUrl from relative navLink (lookup hits)."""
    out = dict(item)
    nav = _glossary_nav_from_item(out)
    if not nav:
        return out
    out["navLink"] = nav
    out["redirectUrl"] = build_absolute_nav_url(nav)
    return out


def _enrich_glossary_lookup_response(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize nav links on glossary-terms GET responses (data only, no top-level mirror)."""
    if not body.get("ok"):
        return body
    out = dict(body)
    data = body.get("data")
    if isinstance(data, list):
        out["data"] = [_enrich_glossary_term_nav(x) for x in data if isinstance(x, dict)]
        return out
    if isinstance(data, dict):
        out["data"] = _enrich_glossary_term_nav(data)
    return out


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
    nav = _glossary_nav_from_item(data)
    if nav:
        absolute = build_absolute_nav_url(nav)
        out["redirectUrl"] = absolute
        out["navLink"] = nav
        out["navUrl"] = absolute
        if isinstance(data, dict):
            data = dict(data)
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

