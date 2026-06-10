"""
Catalog and related data tools (search, details, column profile, relationships, lineage).
"""

import json
import re
from typing import Any

from server.constants import (
    MCP_CATALOG_OBJECT_TYPES_DOC,
    MCP_PATH_COLUMN_PROFILE,
    MCP_PATH_ENTITY_RELATIONSHIPS,
    MCP_PATH_LINEAGE,
    MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
    MCP_PATH_OBJECT_DETAILS,
    MCP_PATH_SEARCH_CATALOG,
    MCP_PATH_UPDATE_ASSET_DESCRIPTIONS,
    MCP_SEARCH_CLASSIFICATIONS_PARAM,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_CRITICAL_DATA_ELEMENT_PARAM,
    MCP_SEARCH_CUSTOM_FIELDS_PARAM,
    MCP_SEARCH_DATA_PRODUCTS_PARAM,
    MCP_SEARCH_GLOSSARY_TERMS_PARAM,
    MCP_SEARCH_SERVER_TYPE_PARAM,
    MCP_SEARCH_TAGS_PARAM,
    MCP_SEARCH_TERMS_PARAM,
    MCP_SERVER_TYPES,
    MCP_SERVER_TYPES_BY_LOWER,
    MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES,
    MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES_DOC,
)
from server.nav_links import build_absolute_nav_url, extract_hash_nav_link

_TABLE_FILE_TYPES = frozenset({"oetable", "oefile"})

_DESC_SEARCH = (
    "Search the OvalEdge catalog (Elasticsearch hybrid / keyword search plus optional "
    "server-side vector context). Use for discovery: schemas, tables, columns, files, charts, "
    "APIs, queries, data products, glossary, tags, and stories.\n\n"
    "**Not for native DB/BI grants** — who can SELECT in Redshift/Snowflake or view a Tableau "
    "report is `source_system_access` (RDAM) only. Never use this tool as a fallback when "
    "RDAM is empty or errors.\n\n"
    f"Backend: GET {MCP_PATH_SEARCH_CATALOG}\n\n"
    "Infer parameters from the user's question before calling:\n"
    "- **Lexical dimensions** (tool args are list[str]; wire as JSON array strings): "
    f"{MCP_SEARCH_TERMS_PARAM}, {MCP_SEARCH_TAGS_PARAM}, {MCP_SEARCH_GLOSSARY_TERMS_PARAM}, "
    f"{MCP_SEARCH_CUSTOM_FIELDS_PARAM}, {MCP_SEARCH_DATA_PRODUCTS_PARAM}, "
    f"{MCP_SEARCH_CLASSIFICATIONS_PARAM}, {MCP_SEARCH_CRITICAL_DATA_ELEMENT_PARAM}.\n"
    "- **Exact filters** (tool args are str; narrow results, not full-text search): "
    "connection_name, schema_name, server_type (connectionInfo.serverType), "
    "owner, steward, custodian, object_type.\n"
    "- **Glossary placement** (domain / category / subcategory): use domain_id or "
    f"domain_name (required), plus optional category_id/category_name and "
    f"subcategory_id/subcategory_name. With object_type=\"glossary\" (or "
    "businessglossary), returns glossary terms in that placement. Without "
    "object_type, returns any catalog assets linked to terms in that placement.\n"
    "- **server_type**: Infer from the user question when they name a technology "
    f"(e.g. MySQL → mysql, Snowflake → snowflake, Tableau → tableau). Maps to API "
    f"{MCP_SEARCH_SERVER_TYPE_PARAM}. Omit when the question does not imply a "
    "connector type — do not guess.\n"
    f"- **Semantic ranking**: {MCP_SEARCH_CONTEXT_QUERY_PARAM} — pass the user's verbatim "
    "question whenever they asked in natural language.\n\n"
    "When the user asks for assets **with / tagged by / assigned** a governance tag, prefer "
    f"tags=[\"<tag name>\"] (not search_terms alone). When they ask for assets linked to a "
    f"glossary term, prefer {MCP_SEARCH_GLOSSARY_TERMS_PARAM}=[\"<term>\"]. When they ask for "
    f"assets with a sensitivity/classification label (e.g. PII), prefer "
    f'{MCP_SEARCH_CLASSIFICATIONS_PARAM}=["PII"]. Use search_terms '
    "for general keywords in names/descriptions.\n\n"
    "Examples:\n"
    '1) "Find all assets with the Operations tag" → '
    'tags=["Operations"], context_query=<verbatim question>.\n'
    '2) "Certified tables in sakila schema" → '
    'object_type="oetable", schema_name="sakila", search_terms=["certified"] (if needed).\n'
    '3) "Customer tables owned by rohit.anand" → '
    'search_terms=["customer"], object_type="oetable", owner="rohit.anand@ovaledge.com".\n'
    '3b) "Find all assets related to MySQL databases" → '
    'server_type="mysql", context_query=<verbatim question>.\n'
    '4) "Data products related to revenue" → '
    'data_products=["revenue"], context_query=<verbatim question>.\n'
    '5) "Assets with Primary Business Function Operations" → '
    'custom_fields=["Operations"] or search_terms as fallback.\n'
    '6) "Finance Domain from Data Domains" → '
    'object_type="dp_domain", search_terms=["Finance"], context_query=<verbatim question>. '
    "Do not use object_type=\"domain\" or oeglobaldomain (that is glossary Global Domain, "
    "not Data Domains).\n"
    '7) "Tables classified as PII" → '
    'classifications=["PII"], context_query=<verbatim question>.\n'
    '8) "All glossary terms under category test in PrakashDOmain" → '
    'object_type="glossary", domain_name="PrakashDOmain", category_name="test".\n'
    '9) "Tables linked to terms in Finance domain" → '
    'object_type="oetable", domain_name="Finance".\n'
    '10) "All table columns marked as CDE" → '
    'object_type="oecolumn", critical_data_element=["Yes"]; then assess_cde_dq '
    "(discover_cde_columns=true or pass objects from hits) for DQ recommendations.\n\n"
    "**Data Domains (dp_domain):** When the user says Data Domains, data domain, or dp_domain, "
    "set object_type=\"dp_domain\" (alias datadomain). These assets are loaded from the database "
    "(not the main Elasticsearch catalog index); search requires object_type=dp_domain alone — "
    "do not combine with other object types.\n\n"
    "Omit empty lists; filter-only search is valid (no lexical arrays). "
    "object_type must be one of: "
    + MCP_CATALOG_OBJECT_TYPES_DOC
    + " — or omit for all types.\n\n"
    "Each hit in items[] includes objectId and objectType (camelCase), relative navLink, "
    "plus redirectUrl (absolute, from OVALEDGE_BASE_URL). Use those values "
    "with update_asset_descriptions when the user asks to change descriptions.\n\n"
    "When results include oestory (data story), call lookup_datastory (object_id or "
    "content_query) for full narrative and storyCitation — do not answer from search "
    "snippets alone."
)
_DESC_DETAILS = (
    "Fetch one catalog document (JSON from Elasticsearch for most types; embeddings removed). "
    "Long business/technical/wiki descriptions are truncated for MCP client limits "
    "(plain text up to ~6k chars; HTML/wiki markup shorter). "
    "Use after search_catalog_assets to drill into an asset.\n\n"
    f"Backend: GET {MCP_PATH_OBJECT_DETAILS}\n\n"
    "Exactly one lookup mode: (1) fully_qualified_name alone, OR "
    "(2) object_id AND object_type together. Never mix FQN with id/type.\n\n"
    "For **dp_domain** (Data Domains), use object_id + object_type=dp_domain from search hits; "
    "FQN lookup is not supported. Details are resolved from the database and wiki when no ES "
    "document exists.\n\n"
    "object_type must be one of: "
    + MCP_CATALOG_OBJECT_TYPES_DOC
    + ".\n\n"
    "Response includes relative navLink plus redirectUrl "
    "(absolute, from OVALEDGE_BASE_URL)."
)
_DESC_COLUMN = (
    "Column-level profile statistics for one table or file asset.\n\n"
    f"Backend: GET {MCP_PATH_COLUMN_PROFILE}\n\n"
    "object_type must be oetable or oefile only."
)
_DESC_REL = (
    "Table-only: entity relationships (columns, patterns) for one oetable.\n\n"
    f"Backend: GET {MCP_PATH_ENTITY_RELATIONSHIPS}\n\n"
    "Pass the table's internal object_id (oetable)."
)
_DESC_LINEAGE = (
    "Data lineage graph from the database for a table or file.\n\n"
    f"Backend: GET {MCP_PATH_LINEAGE}\n\n"
    "object_type must be oetable or oefile. depth defaults to 2; server may clamp depth."
)
_DESC_UPDATE_DESCRIPTIONS = (
    "Update one or more description fields on a catalog asset (RBAC and governance rules "
    "apply on the server).\n\n"
    f"Backend: POST {MCP_PATH_UPDATE_ASSET_DESCRIPTIONS}\n\n"
    "**Human confirmation (same pattern as create_glossary_term / create_tag):** "
    "When ready to persist (and dry_run is not true), call without "
    "create_confirmed_by_user to receive a confirm_update preview (doNotUpdate=true). "
    "Show formattedResponse; wait for explicit user approval. Re-call with "
    "create_confirmed_by_user=true and the same object_id, object_type, description "
    "fields, and clientContext — then POST. Never set create_confirmed_by_user until "
    "the user confirms.\n\n"
    "Resolve object_id first: search_catalog_assets (catalog types), lookup_glossary_term "
    "(glossary), or lookup_tags (oetag). For **Data Domains (dp_domain)**, discover via "
    "search_catalog_assets with object_type=\"dp_domain\", then catalog_asset_details. "
    "For code/master tags use search with object_type filter or catalog_asset_details with "
    "known id. Do not guess ids.\n\n"
    "Required: object_id, object_type, and an explicit description slot.\n\n"
    "When the user says only \"description\" (not business vs technical), you MUST ask which "
    "slot applies, then call with description_field + description_text. Do NOT guess "
    "business_description or technical_description.\n\n"
    "When the user explicitly says \"technical description\" or \"business description\", pass "
    "that typed argument AND set prompt to the user's exact words (clientContext.prompt) so "
    "the API can verify the slot was named.\n\n"
    "For multi-slot object types, a lone typed field without prompt naming the slot is rejected "
    "(HTTP 400). Updating both business and technical in one call is allowed.\n\n"
    "Field applicability by object_type (server rejects unsupported combinations with 400):\n"
    "- Catalog assets (oeschema, oetable, oecolumn, oefile, oefilecolumn, oechart, chartchild, "
    "oeapi, oeapicolumn, code/oecode): business_description, technical_description only — "
    "NOT detailed_description.\n"
    "- Glossary (glossary / businessglossary): business_description, detailed_description — "
    "NOT technical_description. Terms must be in Draft state on the server.\n"
    "- Data product (dp_product): business_description, detailed_description.\n"
    "- Glossary Global Domain (oeglobaldomain): domain_description only (not Data Domains).\n"
    "- Data Domains (dp_domain): domain_description only (wiki on dp_domain_master).\n"
    "- Tag (oetag): tag_description only.\n"
    "- Master tag (mastertag): master_tag_description only.\n\n"
    "object_type must be one of: "
    + MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES_DOC
    + ".\n\n"
    "Response status may be success, partial_success (some fields blocked), or blocked. "
    "Check updatedFields, blockedFields, blockedReasons, and target.redirectUrl. "
    "Business description may be blocked when a published glossary term copies business text."
)
_DESC_METADATA_CHANGES = (
    "Compare metadata changes between crawls using transactions_details as primary source, "
    "with schema-compare fallback when needed.\n\n"
    f"Backend: POST {MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS}\n\n"
    "Supports: schema/table/column drift, datatype/length/precision/nullability hints, row-count "
    "delta indicators, and time-window or crawl-id filters.\n\n"
    "Typical prompts: "
    '"What changed in CUSTOMER schema after the latest crawl?", '
    '"Did any tables get added or deleted this week?", '
    '"Show datatype changes in CUSTOMER_ANALYTICS from last 2 crawls." '
    "When details are missing, response may recommend running ANALYSYS_TRANSACTION_JOB."
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
    "Do not set create_confirmed_by_user=true until the user confirms. "
    "Then re-call with create_confirmed_by_user=true and the same parameters."
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
    return {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_update",
        "doNotUpdate": True,
        "createConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm description update**\n\n"
            f"- **Target:** {otype} (id {oid})\n"
            f"{fields_block}\n"
            f"{dry_note}\n"
            "Ask the user to confirm. After they approve, call again with "
            "`create_confirmed_by_user=true` and the same object_id, object_type, "
            "description fields, and clientContext."
        ),
        "agentInstruction": _UPDATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingUpdate": {"target": target, "descriptions": body.get("descriptions")},
    }

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


def _apply_lexical_search_params(
    params: dict[str, object],
    *,
    search_terms: list[str] | None = None,
    tags: list[str] | None = None,
    terms: list[str] | None = None,
    custom_fields: list[str] | None = None,
    data_products: list[str] | None = None,
    classifications: list[str] | None = None,
    critical_data_element: list[str] | None = None,
) -> None:
    """Map MCP list args to API query params (each a JSON array string)."""
    for api_key, values in (
        (MCP_SEARCH_TERMS_PARAM, search_terms),
        (MCP_SEARCH_TAGS_PARAM, tags),
        (MCP_SEARCH_GLOSSARY_TERMS_PARAM, terms),
        (MCP_SEARCH_CUSTOM_FIELDS_PARAM, custom_fields),
        (MCP_SEARCH_DATA_PRODUCTS_PARAM, data_products),
        (MCP_SEARCH_CLASSIFICATIONS_PARAM, classifications),
        (MCP_SEARCH_CRITICAL_DATA_ELEMENT_PARAM, critical_data_element),
    ):
        normalized = _normalize_search_terms(values)
        if normalized is not None:
            params[api_key] = json.dumps(normalized, ensure_ascii=False)




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
    if body.get("error"):
        return body
    out = dict(body)
    items = body.get("items")
    if isinstance(items, list):
        out["items"] = [_enrich_catalog_item_nav(x) for x in items if isinstance(x, dict)]
    return out


def _enrich_catalog_details_response(body: dict[str, Any]) -> dict[str, Any]:
    if body.get("error") or body.get("ok") is False:
        return body
    out = dict(body)
    data = body.get("data")
    if isinstance(data, dict):
        out["data"] = _enrich_catalog_item_nav(data)
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


