"""
Catalog MCP helpers: tool descriptions, search params, description updates.
"""

import re
from typing import Any

from server.constants import (
    MCP_ACCESS_DISAMBIGUATION_SEARCH_GUARD_DOC,
    MCP_ASSET_EXPLORER_FILTER_KEYS,
    MCP_ASSET_EXPLORER_SORT_DEFAULT_DIRECTION,
    MCP_ASSET_EXPLORER_SORT_DIRECTIONS,
    MCP_ASSET_EXPLORER_SORT_FIELDS,
    MCP_ASSET_EXPLORER_SORT_FIELDS_DOC,
    MCP_CATALOG_OBJECT_TYPES_DOC,
    MCP_PATH_ASSET_DETAILS,
    MCP_PATH_ASSET_EXPLORER,
    MCP_PATH_ASSET_LINEAGE,
    MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
    MCP_PATH_UPDATE_ASSET_DESCRIPTIONS,
    MCP_SEARCH_CATALOG_MAX_LIMIT,
    MCP_SEARCH_CLASSIFICATIONS_PARAM,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_CRITICAL_DATA_ELEMENT_PARAM,
    MCP_SEARCH_CUSTOM_FIELDS_PARAM,
    MCP_SEARCH_DATA_PRODUCTS_PARAM,
    MCP_SEARCH_GLOSSARY_TERMS_PARAM,
    MCP_SEARCH_TAGS_PARAM,
    MCP_SEARCH_TERMS_PARAM,
    MCP_SERVER_TYPES,
    MCP_SERVER_TYPES_BY_LOWER,
    MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES,
    MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES_DOC,
)
from server.nav_links import build_absolute_nav_url, extract_hash_nav_link
from server.tools.common import drop_none, error_payload, strip_or_none
from server.tools.common.confirm_gate import attach_confirmation_token
from server.tools.common.descriptions import classify_tool_desc

_TABLE_FILE_TYPES = frozenset({"oetable", "oefile"})

_DESC_ASSET_EXPLORER = classify_tool_desc(
    MCP_ACCESS_DISAMBIGUATION_SEARCH_GUARD_DOC
    + "**Find data assets** (`asset_explorer`) — search the catalog for tables, files, "
    "columns, reports, glossary terms, tags, and other governed objects related to a "
    "business question.\n\n"
    "How to call: pass keywords in search_terms and the user's full question in "
    "context_query. Omit object_type, tags, and terms (leave them unset) unless the user "
    "clearly asks for one kind of asset (e.g. \"tables only\", \"tagged Payments\", a named "
    "glossary term). Do not default to tables-only. After you shortlist hits, call "
    "asset_details for full metadata.\n\n"
    f"Backend: POST {MCP_PATH_ASSET_EXPLORER}\n\n"
    "Keyword lists are JSON arrays: "
    f"{MCP_SEARCH_TERMS_PARAM}, {MCP_SEARCH_TAGS_PARAM}, {MCP_SEARCH_GLOSSARY_TERMS_PARAM}, "
    f"{MCP_SEARCH_CUSTOM_FIELDS_PARAM}, {MCP_SEARCH_DATA_PRODUCTS_PARAM}, "
    f"{MCP_SEARCH_CLASSIFICATIONS_PARAM}, {MCP_SEARCH_CRITICAL_DATA_ELEMENT_PARAM}. "
    "Exact filters: connection_name, schema_name, server_type, owner, steward, custodian, "
    "object_type. tags/terms match exact governance names (not loose synonyms). "
    "Extra facets (tableType, certification, ranges) go in filters; open-ended ranges "
    "use min or max only (do not invent the other bound); exact metric uses eq; more "
    "than N uses min just above N; top-level args win if both set; filter-only "
    "sort={field,direction} (omit with keywords) — matrix: "
    "docs://ovaledge/mcp_workflows. "
    f"Semantic ranking: {MCP_SEARCH_CONTEXT_QUERY_PARAM}. "
    "Look up one term/tag: name + object_type=glossary|oetag "
    "(include_parent/children for tags). "
    "Glossary placement: domain_id|domain_name + optional category/subcategory.\n\n"
    "Examples: "
    '"What tables can I see/access?" → this tool (not access_explorer); '
    'search_terms=["payment"] + context_query="Find assets related to payment"; '
    'tables only → object_type="oetable"; '
    'glossary name="Revenue" object_type="glossary".\n\n'
    "Types: docs://ovaledge/asset_types. Playbooks: docs://ovaledge/mcp_workflows. "
    "Policies and how-tos: knowledge_search — not search snippets alone."
)
_DESC_ASSET_DETAILS = classify_tool_desc(
    "**View asset details** (`asset_details`) — full catalog metadata for one chosen asset "
    "(object_id + object_type; no fully qualified name). Includes profile stats for tables/"
    "files and entity relationships for tables when available. Use after asset_explorer "
    "shortlist — not for open-ended discovery.\n\n"
    f"Backend: GET {MCP_PATH_ASSET_DETAILS}\n\n"
    "object_type one of: "
    + MCP_CATALOG_OBJECT_TYPES_DOC
    + ". Response: details; optional profile and relationships; navLink/redirectUrl when "
    "present. Playbooks: docs://ovaledge/mcp_workflows."
)
_DESC_ASSET_LINEAGE = classify_tool_desc(
    "**Trace data lineage** (`asset_lineage`) — show where a table or file comes from and "
    "what depends on it (upstream/downstream). Resolve the asset id with asset_explorer "
    "first when the user only gives a name.\n\n"
    f"Backend: GET {MCP_PATH_ASSET_LINEAGE}\n\n"
    "Requires object_id + object_type (oetable or oefile only). depth defaults to 2 "
    "(server may clamp). Playbooks: docs://ovaledge/mcp_workflows; prompt trace_data_lineage."
)
_DESC_UPDATE_DESCRIPTIONS = classify_tool_desc(
    "Update description field(s) on a catalog or governance asset (RBAC on server).\n\n"
    f"Backend: POST {MCP_PATH_UPDATE_ASSET_DESCRIPTIONS}\n\n"
    "**Confirm gate:** confirm_update preview first; POST only with write_confirmed_by_user=true "
    "(same pattern as create_glossary_term / create_tag). Never confirm until user approves.\n\n"
    "Resolve object_id via asset_explorer — do not guess ids. Required: object_id, object_type, "
    "and an explicit description slot.\n\n"
    "If the user says only \"description\", ask which slot applies — do not guess business vs "
    "technical vs domain/tag fields. Multi-slot types need clientContext.prompt when using "
    "typed fields.\n\n"
    "Field rules by object_type: docs://ovaledge/mcp_workflows (Update asset descriptions). "
    "Workflow prompt: `document_asset_descriptions`."
)
_DESC_METADATA_CHANGES = classify_tool_desc(
    "Compare metadata changes between crawls using transactions_details as primary source, "
    "with schema-compare fallback when needed.\n\n"
    f"Backend: POST {MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS}\n\n"
    "Supports: schema/table/column drift, datatype/length/precision/nullability hints, row-count "
    "delta indicators, and time-window or crawl-id filters.\n\n"
    "Typical prompts: "
    '"What changed in CUSTOMER schema after the latest crawl?", '
    '"Did any tables get added or deleted this week?", '
    '"Show datatype changes in CUSTOMER_ANALYTICS from last 2 crawls." '
    "When details are missing, response may recommend running ANALYSIS_TRANSACTION_JOB."
)


def _normalize_search_terms(terms: list[str] | None) -> list[str] | None:
    if not terms:
        return None
    out = [t.strip() for t in terms if t and str(t).strip()]
    return out or None


_DESCRIPTION_API_KEYS: tuple[tuple[str, str], ...] = (
    ("business_description", "businessDescription"),
    ("technical_description", "technicalDescription"),
    ("detailed_description", "detailedDescription"),
    ("domain_description", "domainDescription"),
    ("tag_description", "tagDescription"),
    ("master_tag_description", "masterTagDescription"),
)

_SNAKE_TO_API_FIELD: dict[str, str] = dict(_DESCRIPTION_API_KEYS)

# Supported description_field values per object_type (snake_case tool args).
_DESCRIPTION_FIELDS_BY_OBJECT_TYPE: dict[str, tuple[str, ...]] = {
    "oeschema": ("business_description", "technical_description"),
    "oetable": ("business_description", "technical_description"),
    "oecolumn": ("business_description", "technical_description"),
    "oefile": ("business_description", "technical_description"),
    "oefilecolumn": ("business_description", "technical_description"),
    "oechart": ("business_description", "technical_description"),
    "chartchild": ("business_description", "technical_description"),
    "oeapi": ("business_description", "technical_description"),
    "oeapicolumn": ("business_description", "technical_description"),
    "oequery": ("business_description", "technical_description"),
    "code": ("business_description", "technical_description"),
    "glossary": ("business_description", "detailed_description"),
    "businessglossary": ("business_description", "detailed_description"),
    "dp_product": ("business_description", "detailed_description"),
    "oeglobaldomain": ("domain_description",),
    "dp_domain": ("domain_description",),
    "oetag": ("tag_description",),
    "mastertag": ("master_tag_description",),
}

# Normalize tool argument object_type to canonical key for field rules / allow-list.
_OBJECT_TYPE_CANONICAL_KEY: dict[str, str] = {
    "filecolumn": "oefilecolumn",
    "oecode": "code",
    "businessglossary": "glossary",
}

# Tool-facing aliases sent to the OvalEdge API as canonical objectType values.
_OBJECT_TYPE_TO_API: dict[str, str] = {
    "filecolumn": "oefilecolumn",
    "oecode": "code",
    "businessglossary": "glossary",
}


def _normalize_object_type_key(object_type: str) -> str:
    key = str(object_type).strip().lower().replace("-", "_")
    return _OBJECT_TYPE_CANONICAL_KEY.get(key, key)


def _api_object_type(object_type: str) -> str:
    return _OBJECT_TYPE_TO_API.get(
        str(object_type).strip().lower().replace("-", "_"),
        _normalize_object_type_key(object_type),
    )


_PROMPT_SLOT_PHRASES: dict[str, tuple[str, ...]] = {
    "business_description": ("business description", "business desc"),
    "technical_description": ("technical description", "technical desc"),
    "detailed_description": ("detailed description", "detailed desc"),
    "domain_description": ("domain description", "domain desc"),
    "tag_description": ("tag description", "tag desc"),
    "master_tag_description": ("master tag description", "master tag desc"),
}


def _prompt_names_slot(user_prompt: str | None, slot: str) -> bool:
    if not user_prompt or not str(user_prompt).strip():
        return False
    p = user_prompt.lower()
    for phrase in _PROMPT_SLOT_PHRASES.get(slot, ()):
        if phrase in p:
            return True
    return False


def _description_field_hint(object_type: str) -> str:
    fields = _DESCRIPTION_FIELDS_BY_OBJECT_TYPE.get(_normalize_object_type_key(object_type))
    if not fields:
        return "See tool description for supported object types."
    if len(fields) == 1:
        return f"use description_field={fields[0]!r} with description_text"
    return "use description_field as one of: " + ", ".join(fields)


def _validate_description_inputs(
    object_type: str,
    *,
    description_field: str | None,
    description_text: str | None,
    business_description: str | None,
    technical_description: str | None,
    detailed_description: str | None,
    domain_description: str | None,
    tag_description: str | None,
    master_tag_description: str | None,
    prompt: str | None = None,
) -> dict[str, Any] | None:
    """Return a client-side 400 payload when description arguments are ambiguous."""
    otype_key = _normalize_object_type_key(object_type)
    if otype_key not in MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES:
        return {
            "error": (
                f"object_type {object_type!r} is not supported for update_asset_descriptions. "
                f"Use one of: {MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES_DOC}."
            ),
            "status_code": 400,
        }
    typed_set = [
        name
        for name, value in (
            ("business_description", business_description),
            ("technical_description", technical_description),
            ("detailed_description", detailed_description),
            ("domain_description", domain_description),
            ("tag_description", tag_description),
            ("master_tag_description", master_tag_description),
        )
        if value is not None
    ]
    has_generic = description_text is not None
    field = (description_field or "").strip().lower().replace("-", "_")

    if has_generic and not field:
        return {
            "error": (
                "description_field is required with description_text when the user did not "
                f"name business vs technical. For {object_type}: "
                f"{_description_field_hint(object_type)}."
            ),
            "status_code": 400,
        }
    if field and not has_generic:
        return {
            "error": "description_text is required when description_field is provided.",
            "status_code": 400,
        }
    if field and typed_set:
        return {
            "error": (
                "Use either description_field + description_text, or one typed description "
                "argument, not both."
            ),
            "status_code": 400,
        }
    if field:
        allowed = _DESCRIPTION_FIELDS_BY_OBJECT_TYPE.get(otype_key, ())
        if field not in allowed:
            return {
                "error": (
                    f"description_field {description_field!r} is not valid for object_type "
                    f"{object_type!r}. {_description_field_hint(object_type)}."
                ),
                "status_code": 400,
            }
    allowed = _DESCRIPTION_FIELDS_BY_OBJECT_TYPE.get(otype_key, ())
    if len(allowed) > 1 and len(typed_set) == 1 and not (has_generic and field):
        only_slot = typed_set[0]
        if not _prompt_names_slot(prompt, only_slot):
            return {
                "error": (
                    f"object_type {object_type!r} has multiple description slots and the "
                    "request did not name which to update. Ask the user (business vs technical, "
                    "etc.), or pass prompt with explicit wording like 'technical description'. "
                    f"{_description_field_hint(object_type)}."
                ),
                "status_code": 400,
            }
    return None


def _build_update_descriptions_body(
    object_id: int,
    object_type: str,
    *,
    business_description: str | None = None,
    technical_description: str | None = None,
    detailed_description: str | None = None,
    domain_description: str | None = None,
    tag_description: str | None = None,
    master_tag_description: str | None = None,
    description_field: str | None = None,
    description_text: str | None = None,
    dry_run: bool | None = None,
    fail_on_blocked_field: bool | None = None,
    idempotency_key: str | None = None,
    prompt: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    descriptions: dict[str, str] = {}
    field = (description_field or "").strip().lower().replace("-", "_")
    if description_text is not None and field:
        descriptions["description"] = description_text
        descriptions["descriptionField"] = _SNAKE_TO_API_FIELD[field]
    for arg_name, api_key in _DESCRIPTION_API_KEYS:
        value = locals()[arg_name]
        if value is not None:
            descriptions[api_key] = value
    body: dict[str, Any] = {
        "target": {"objectId": object_id, "objectType": _api_object_type(object_type)},
        "descriptions": descriptions,
    }
    options: dict[str, Any] = {}
    if dry_run is not None:
        options["dryRun"] = dry_run
    if fail_on_blocked_field is not None:
        options["failOnBlockedField"] = fail_on_blocked_field
    if idempotency_key is not None and str(idempotency_key).strip():
        options["idempotencyKey"] = idempotency_key.strip()
    if options:
        body["options"] = options
    client_context: dict[str, str] = {}
    if prompt is not None and str(prompt).strip():
        client_context["prompt"] = str(prompt).strip()
    if reason is not None and str(reason).strip():
        client_context["reason"] = str(reason).strip()
    if client_context:
        body["clientContext"] = client_context
    return body


def _format_update_descriptions_response(body: dict[str, Any]) -> str:
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
    updated = body.get("updatedFields")
    requested = body.get("requestedFields")
    if isinstance(updated, list) and updated:
        lines.append(f"**Updated fields:** {', '.join(str(f) for f in updated)}")
    elif isinstance(requested, list) and requested:
        lines.append("**No changes:** description(s) already match the current value.")
    blocked = body.get("blockedFields")
    if isinstance(blocked, list) and blocked:
        lines.append(f"**Blocked fields:** {', '.join(str(f) for f in blocked)}")
    reasons = body.get("blockedReasons")
    if isinstance(reasons, list):
        for item in reasons:
            if not isinstance(item, dict):
                continue
            field = item.get("field")
            code = item.get("code")
            message = item.get("message")
            parts = (
                str(field or "").strip(),
                str(code or "").strip(),
                str(message or "").strip(),
            )
            detail = " — ".join(p for p in parts if p)
            if detail:
                lines.append(f"- {detail}")
    return "\n".join(lines).strip()


def _enrich_update_descriptions_response(body: dict[str, Any]) -> dict[str, Any]:
    formatted = _format_update_descriptions_response(body)
    if formatted:
        body["formattedResponse"] = formatted
    return body


_UPDATE_CONFIRM_AGENT_INSTRUCTION = (
    "Show formattedResponse and wait for explicit user approval. "
    "Do not set write_confirmed_by_user=true until the user confirms. "
    "Then re-call with write_confirmed_by_user=true, confirmation_token from the "
    "preview, and the same parameters."
)


def _summarize_description_updates(body: dict[str, Any]) -> list[str]:
    descriptions = body.get("descriptions")
    if not isinstance(descriptions, dict):
        return []
    lines: list[str] = []
    for api_key, value in descriptions.items():
        if value is None:
            continue
        text = str(value).strip()
        preview = text if len(text) <= 120 else text[:117] + "..."
        lines.append(f"- **{api_key}:** {preview}")
    return lines


def _format_update_descriptions_confirmation_preview(
    body: dict[str, Any],
) -> dict[str, Any]:
    target = body.get("target")
    oid = otype = None
    if isinstance(target, dict):
        oid = target.get("objectId")
        otype = target.get("objectType")
    field_lines = _summarize_description_updates(body)
    fields_block = "\n".join(field_lines) if field_lines else "- (no description fields in request)"
    dry = body.get("options", {})
    dry_note = ""
    if isinstance(dry, dict) and dry.get("dryRun"):
        dry_note = "\n- **Note:** dry_run=true — preview only; no persist on confirm.\n"
    preview = {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_update",
        "doNotUpdate": True,
        "writeConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm description update**\n\n"
            f"- **Target:** {otype} (id {oid})\n"
            f"{fields_block}\n"
            f"{dry_note}\n"
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same object_id, object_type, description fields, and clientContext."
        ),
        "agentInstruction": _UPDATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingUpdate": {"target": target, "descriptions": body.get("descriptions")},
    }
    return attach_confirmation_token(preview, body)

def _resolve_server_type(raw: str | None) -> str | None:
    """Return canonical serverType for API, or None when unset (no filter)."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value in MCP_SERVER_TYPES:
        return value
    return MCP_SERVER_TYPES_BY_LOWER.get(value.lower())


def _filter_api_key(key: str) -> str:
    """Map snake_case extra filter keys to the POST JSON camelCase field names."""
    if "_" not in key:
        return key
    parts = [p for p in key.split("_") if p]
    if not parts:
        return key
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _clean_filter_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, list):
        cleaned: list[Any] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    cleaned.append(stripped)
            else:
                cleaned.append(item)
        return cleaned or None
    if isinstance(value, dict):
        nested = {
            k: cleaned
            for k, raw in value.items()
            if (cleaned := _clean_filter_value(raw)) is not None
        }
        return nested or None
    return value


_SORT_FIELD_BY_COMPACT: dict[str, str] = {
    token.replace("_", ""): token for token in MCP_ASSET_EXPLORER_SORT_FIELDS
}


def _canonical_sort_field(raw: str) -> str | None:
    token = raw.strip().lower()
    if not token:
        return None
    if token in MCP_ASSET_EXPLORER_SORT_FIELDS:
        return token
    return _SORT_FIELD_BY_COMPACT.get(token.replace("_", ""))


def _normalize_explorer_sort(sort: Any) -> dict[str, str] | None:
    """Return search.sort {field, direction} or None when sort is omitted."""
    if sort is None:
        return None
    dump = getattr(sort, "model_dump", None)
    raw = dump(exclude_none=True) if callable(dump) else sort
    if not isinstance(raw, dict) or not raw:
        return None
    field_raw = raw.get("field")
    if not isinstance(field_raw, str) or not field_raw.strip():
        return None
    field = _canonical_sort_field(field_raw)
    if field is None:
        return None
    direction_raw = raw.get("direction")
    direction = MCP_ASSET_EXPLORER_SORT_DEFAULT_DIRECTION
    if isinstance(direction_raw, str) and direction_raw.strip():
        direction = direction_raw.strip().lower()
    return {"field": field, "direction": direction}


def _validate_explorer_sort(sort: Any) -> dict[str, Any] | None:
    """Return error_payload when sort is present but invalid; None when ok or omitted."""
    if sort is None:
        return None
    dump = getattr(sort, "model_dump", None)
    raw = dump(exclude_none=True) if callable(dump) else sort
    if not isinstance(raw, dict):
        return error_payload("sort must be an object {field, direction}.")
    if not raw:
        return None
    field_raw = raw.get("field")
    if not isinstance(field_raw, str) or not field_raw.strip():
        return error_payload(
            "sort.field is required when sort is set. One of: "
            + MCP_ASSET_EXPLORER_SORT_FIELDS_DOC
            + "."
        )
    if _canonical_sort_field(field_raw) is None:
        return error_payload(
            f"sort.field must be one of {MCP_ASSET_EXPLORER_SORT_FIELDS_DOC}, "
            f"got {field_raw!r}."
        )
    direction_raw = raw.get("direction")
    if direction_raw is None or (isinstance(direction_raw, str) and not direction_raw.strip()):
        return None
    if not isinstance(direction_raw, str):
        return error_payload("sort.direction must be 'asc' or 'desc'.")
    if direction_raw.strip().lower() not in MCP_ASSET_EXPLORER_SORT_DIRECTIONS:
        return error_payload(
            f"sort.direction must be one of {sorted(MCP_ASSET_EXPLORER_SORT_DIRECTIONS)}, "
            f"got {direction_raw!r}."
        )
    return None


def _filters_from_extra(filters: Any) -> dict[str, Any]:
    if filters is None:
        return {}
    dump = getattr(filters, "model_dump", None)
    raw = dump(exclude_none=True) if callable(dump) else filters
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in raw.items():
        api_key = _filter_api_key(str(key))
        if api_key not in MCP_ASSET_EXPLORER_FILTER_KEYS:
            continue
        cleaned = _clean_filter_value(value)
        if cleaned is not None:
            out[api_key] = cleaned
    return out


def _build_asset_explorer_body(
    *,
    search_terms: list[str] | None = None,
    tags: list[str] | None = None,
    terms: list[str] | None = None,
    custom_fields: list[str] | None = None,
    data_products: list[str] | None = None,
    classifications: list[str] | None = None,
    critical_data_element: list[str] | None = None,
    context_query: str | None = None,
    page: int = 1,
    limit: int = 20,
    connection_name: str | None = None,
    resolved_server_type: str | None = None,
    schema_name: str | None = None,
    owner: str | None = None,
    steward: str | None = None,
    custodian: str | None = None,
    object_type: str | None = None,
    domain_id: int | None = None,
    domain_name: str | None = None,
    category_id: int | None = None,
    category_name: str | None = None,
    subcategory_id: int | None = None,
    subcategory_name: str | None = None,
    object_id: int | None = None,
    name: str | None = None,
    include_parent: bool = False,
    include_children: bool = False,
    filters: Any = None,
    sort: Any = None,
) -> dict[str, Any]:
    """Build POST /asset-explorer JSON. Top-level tool args win over nested filters."""
    body: dict[str, Any] = drop_none(
        objectId=object_id if object_id is not None and object_id > 0 else None,
        objectType=object_type,
        name=strip_or_none(name),
        includeParent=True if include_parent else None,
        includeChildren=True if include_children else None,
    )
    search = drop_none(
        searchTerms=_normalize_search_terms(search_terms),
        contextQuery=strip_or_none(context_query),
        page=max(page, 1),
        limit=min(max(limit, 1), MCP_SEARCH_CATALOG_MAX_LIMIT),
        sort=_normalize_explorer_sort(sort),
    )
    if search:
        body["search"] = search
    placement = drop_none(
        domainId=domain_id if domain_id is not None and domain_id > 0 else None,
        domainName=strip_or_none(domain_name),
        categoryId=category_id if category_id is not None and category_id > 0 else None,
        categoryName=strip_or_none(category_name),
        subcategoryId=subcategory_id
        if subcategory_id is not None and subcategory_id > 0
        else None,
        subcategoryName=strip_or_none(subcategory_name),
    )
    if placement:
        body["glossaryPlacement"] = placement
    top_filters = drop_none(
        connectionName=strip_or_none(connection_name),
        serverType=resolved_server_type,
        schemaName=strip_or_none(schema_name),
        owner=strip_or_none(owner),
        steward=strip_or_none(steward),
        custodian=strip_or_none(custodian),
        tags=_normalize_search_terms(tags),
        terms=_normalize_search_terms(terms),
        customFields=_normalize_search_terms(custom_fields),
        dataProducts=_normalize_search_terms(data_products),
        classifications=_normalize_search_terms(classifications),
        criticalDataElement=_normalize_search_terms(critical_data_element),
    )
    merged_filters = {**_filters_from_extra(filters), **top_filters}
    if merged_filters:
        body["filters"] = merged_filters
    return body


def _enrich_catalog_item_nav(item: dict[str, Any]) -> dict[str, Any]:
    """Add absolute redirectUrl from relative navLink (search/detail hits)."""
    out = dict(item)
    nav = extract_hash_nav_link(str(out.get("navLink") or ""))
    if not nav:
        nav = extract_hash_nav_link(str(out.get("hyperlink") or ""))
    if not nav:
        return out
    out["navLink"] = nav
    out["redirectUrl"] = build_absolute_nav_url(nav)
    return out


def _enrich_catalog_search_response(body: dict[str, Any]) -> dict[str, Any]:
    """Enrich catalog hit nav links (flat or McpApiResult-wrapped explorer payload)."""
    if body.get("error"):
        return body
    out = dict(body)
    items = body.get("items")
    data = body.get("data")
    if isinstance(items, list):
        out["items"] = [_enrich_catalog_item_nav(x) for x in items if isinstance(x, dict)]
    elif isinstance(data, dict):
        data_out = dict(data)
        nested_items = data.get("items")
        if isinstance(nested_items, list):
            data_out["items"] = [
                _enrich_catalog_item_nav(x) for x in nested_items if isinstance(x, dict)
            ]
        out["data"] = data_out
    return out


def _enrich_asset_explorer_response(body: dict[str, Any]) -> dict[str, Any]:
    """Enrich explorer response: catalog items + glossary/tag sections when present."""
    from server.tools.governance.glossary_helpers import _enrich_glossary_lookup_response
    from server.tools.governance.tag_helpers import _enrich_tag_lookup_response

    if body.get("error") or body.get("ok") is False:
        return body
    out = _enrich_catalog_search_response(body)
    data = out.get("data")
    if not isinstance(data, dict):
        return out
    data_out = dict(data)
    glossary = data.get("glossaryTerms")
    if glossary is not None:
        enriched = _enrich_glossary_lookup_response({"ok": True, "data": glossary})
        data_out["glossaryTerms"] = enriched.get("data", glossary)
        if enriched.get("formattedResponse"):
            out["formattedResponse"] = enriched["formattedResponse"]
    tags = data.get("tags")
    if tags is not None:
        enriched = _enrich_tag_lookup_response({"ok": True, "data": tags})
        data_out["tags"] = enriched.get("data", tags)
        if enriched.get("formattedResponse"):
            out["formattedResponse"] = enriched["formattedResponse"]
    out["data"] = data_out
    return out


def _enrich_catalog_details_response(body: dict[str, Any]) -> dict[str, Any]:
    """Enrich composite asset-details (details + optional profile/relationships)."""
    if body.get("error") or body.get("ok") is False:
        return body
    out = dict(body)
    data = body.get("data")
    if not isinstance(data, dict):
        return out
    data_out = dict(data)
    details = data.get("details")
    if isinstance(details, dict):
        data_out["details"] = _enrich_catalog_item_nav(details)
    elif details is None and (
        "objectId" in data or "objectType" in data or "navLink" in data
    ):
        # Flat metadata fallback
        data_out = _enrich_catalog_item_nav(data_out)
    out["data"] = data_out
    return out


def _is_specific_table_compare(
    question: str | None,
    table_names: list[str] | None,
) -> bool:
    if table_names:
        return True
    if not question or not question.strip():
        return False
    q = question.strip().lower()
    if re.search(r"\bat\s+[a-z0-9_]{3,}\b", q):
        return True
    if re.search(r"\b(table|tbl)\s+[a-z0-9_]{3,}\b", q):
        return True
    if re.search(r"\bfrom\s+[a-z0-9_]{3,}\s+table", q):
        return True
    return False


