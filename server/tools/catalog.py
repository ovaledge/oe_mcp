"""
Catalog and related data tools (search, details, column profile, relationships, lineage).
"""

import json
import re
from typing import Annotated, Any
from urllib.parse import quote

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import (
    MCP_CATALOG_OBJECT_TYPES,
    MCP_CATALOG_OBJECT_TYPES_DOC,
    MCP_PATH_COLUMN_PROFILE,
    MCP_PATH_ENTITY_RELATIONSHIPS,
    MCP_PATH_LINEAGE,
    MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
    MCP_PATH_OBJECT_DETAILS,
    MCP_PATH_SEARCH_CATALOG,
    MCP_PATH_UPDATE_ASSET_DESCRIPTIONS,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_CUSTOM_FIELDS_PARAM,
    MCP_SEARCH_DATA_PRODUCTS_PARAM,
    MCP_SEARCH_GLOSSARY_TERMS_PARAM,
    MCP_SEARCH_SERVER_TYPE_PARAM,
    MCP_SEARCH_TAGS_PARAM,
    MCP_SEARCH_TERMS_PARAM,
    MCP_SERVER_TYPES,
    MCP_SERVER_TYPES_BY_LOWER,
)

_TABLE_FILE_TYPES = frozenset({"oetable", "oefile"})

_DESC_SEARCH = (
    "Search the OvalEdge catalog (Elasticsearch hybrid / keyword search plus optional "
    "server-side vector context). Use for discovery: schemas, tables, columns, files, charts, "
    "APIs, queries, data products, glossary, tags, and stories.\n\n"
    f"Backend: GET {MCP_PATH_SEARCH_CATALOG}\n\n"
    "Infer parameters from the user's question before calling:\n"
    "- **Lexical dimensions** (tool args are list[str]; wire as JSON array strings): "
    f"{MCP_SEARCH_TERMS_PARAM}, {MCP_SEARCH_TAGS_PARAM}, {MCP_SEARCH_GLOSSARY_TERMS_PARAM}, "
    f"{MCP_SEARCH_CUSTOM_FIELDS_PARAM}, {MCP_SEARCH_DATA_PRODUCTS_PARAM}.\n"
    "- **Exact filters** (tool args are str; narrow results, not full-text search): "
    "connection_name, schema_name, server_type (connectionInfo.serverType), "
    "owner, steward, custodian, object_type.\n"
    "- **server_type**: Infer from the user question when they name a technology "
    f"(e.g. MySQL → mysql, Snowflake → snowflake, Tableau → tableau). Maps to API "
    f"{MCP_SEARCH_SERVER_TYPE_PARAM}. Omit when the question does not imply a "
    "connector type — do not guess.\n"
    f"- **Semantic ranking**: {MCP_SEARCH_CONTEXT_QUERY_PARAM} — pass the user's verbatim "
    "question whenever they asked in natural language.\n\n"
    "When the user asks for assets **with / tagged by / assigned** a governance tag, prefer "
    f"tags=[\"<tag name>\"] (not search_terms alone). When they ask for assets linked to a "
    f"glossary term, prefer {MCP_SEARCH_GLOSSARY_TERMS_PARAM}=[\"<term>\"]. Use search_terms "
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
    'custom_fields=["Operations"] or search_terms as fallback.\n\n'
    "Omit empty lists; filter-only search is valid (no lexical arrays). "
    "object_type must be one of: "
    + MCP_CATALOG_OBJECT_TYPES_DOC
    + " — or omit for all types.\n\n"
    "Each hit in items[] includes objectId and objectType (camelCase). Use those values "
    "with update_asset_descriptions when the user asks to change descriptions."
)
_DESC_DETAILS = (
    "Fetch one catalog document (JSON from Elasticsearch; embeddings removed). "
    "Use after search_catalog_assets to drill into an asset.\n\n"
    f"Backend: GET {MCP_PATH_OBJECT_DETAILS}\n\n"
    "Exactly one lookup mode: (1) fully_qualified_name alone, OR "
    "(2) object_id AND object_type together. Never mix FQN with id/type.\n\n"
    "object_type must be one of: "
    + MCP_CATALOG_OBJECT_TYPES_DOC
    + "."
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
    "Workflow: call search_catalog_assets first, then pass items[].objectId as object_id "
    "and items[].objectType as object_type (API returns camelCase; this tool uses snake_case "
    "arguments). Do not guess ids.\n\n"
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
    "apiobject, apicolumn, oequery): business_description, technical_description only — "
    "NOT detailed_description.\n"
    "- Glossary (glossary / businessglossary): business_description, detailed_description — "
    "NOT technical_description.\n"
    "- Data product (dp_product): business_description, detailed_description.\n"
    "- Global domain / data domain (oeglobaldomain, dp_domain): domain_description only.\n"
    "- Tag (oetag): tag_description only.\n"
    "- Master tag (mastertag): master_tag_description only.\n\n"
    "object_type must be one of: "
    + MCP_CATALOG_OBJECT_TYPES_DOC
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


def _q(**kwargs: object) -> dict[str, object]:
    """Omit None values from query params."""
    return {k: v for k, v in kwargs.items() if v is not None}


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
    "glossary": ("business_description", "detailed_description"),
    "dp_product": ("business_description", "detailed_description"),
    "oeglobaldomain": ("domain_description",),
    "dp_domain": ("domain_description",),
    "oetag": ("tag_description",),
    "mastertag": ("master_tag_description",),
}

# Tool-facing aliases sent to the OvalEdge API as canonical objectType values.
_OBJECT_TYPE_TO_API: dict[str, str] = {
    "filecolumn": "oefilecolumn",
}


def _api_object_type(object_type: str) -> str:
    return _OBJECT_TYPE_TO_API.get(object_type, object_type)


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
    fields = _DESCRIPTION_FIELDS_BY_OBJECT_TYPE.get(object_type)
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
        allowed = _DESCRIPTION_FIELDS_BY_OBJECT_TYPE.get(object_type, ())
        if field not in allowed:
            return {
                "error": (
                    f"description_field {description_field!r} is not valid for object_type "
                    f"{object_type!r}. {_description_field_hint(object_type)}."
                ),
                "status_code": 400,
            }
    allowed = _DESCRIPTION_FIELDS_BY_OBJECT_TYPE.get(object_type, ())
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
) -> None:
    """Map MCP list args to API query params (each a JSON array string)."""
    for api_key, values in (
        (MCP_SEARCH_TERMS_PARAM, search_terms),
        (MCP_SEARCH_TAGS_PARAM, tags),
        (MCP_SEARCH_GLOSSARY_TERMS_PARAM, terms),
        (MCP_SEARCH_CUSTOM_FIELDS_PARAM, custom_fields),
        (MCP_SEARCH_DATA_PRODUCTS_PARAM, data_products),
    ):
        normalized = _normalize_search_terms(values)
        if normalized is not None:
            params[api_key] = json.dumps(normalized, ensure_ascii=False)


def _build_metadata_links(
    context_header: dict[str, Any] | None, data: dict[str, Any]
) -> dict[str, str]:
    ctx = context_header or {}
    schema_id = ctx.get("schemaId")
    analysis_id = ctx.get("analysisId")
    analysis_name = (
        ctx.get("analysisName")
        or _extract_analysis_name_from_payload(data)
        or "team"
    )
    redirect_url = data.get("redirectUrl")
    if not isinstance(redirect_url, str) or "#nav/" not in redirect_url:
        return {}
    nav_base = redirect_url.split("#nav/", 1)[0] + "#nav/"
    links: dict[str, str] = {
        "objectRedirectUrl": str(data.get("objectRedirectUrl") or redirect_url)
    }
    backend_compare_schema_url = data.get("compareSchemaUrl")
    backend_object_schema_url = data.get("objectSchemaUrl")
    backend_data_change_url = data.get("dataChangeUrl")
    backend_metadata_change_url = data.get("metadataChangeUrl")
    if isinstance(backend_compare_schema_url, str) and backend_compare_schema_url:
        links["compareSchemaUrl"] = backend_compare_schema_url
    elif analysis_id is not None:
        links["compareSchemaUrl"] = (
            f"{nav_base}analysis-advancejob?srchtab=tablesummary"
            f"&deepanalysistoolid={analysis_id}&analysisName={quote(str(analysis_name))}"
        )
    if isinstance(backend_object_schema_url, str) and backend_object_schema_url:
        links["objectSchemaUrl"] = backend_object_schema_url
    elif schema_id is not None:
        links["objectSchemaUrl"] = f"{nav_base}schema?browse=summary&id={schema_id}"
    if isinstance(backend_data_change_url, str) and backend_data_change_url:
        links["dataChangeUrl"] = backend_data_change_url
    elif schema_id is not None:
        links["dataChangeUrl"] = (
            f"{nav_base}dataandmetachanges?searchTab=datachanges&startindex=0"
            "&ftrodr=%5B%7B%22action%22%3A%5B%5D%2C%22fieldName%22%3A%22schemaname%22%7D%5D"
            f"&schemaname={schema_id}"
        )
    if isinstance(backend_metadata_change_url, str) and backend_metadata_change_url:
        links["metadataChangeUrl"] = backend_metadata_change_url
    elif schema_id is not None:
        links["metadataChangeUrl"] = (
            f"{nav_base}dataandmetachanges?searchTab=metadatachanges/table&startindex=0"
            "&ftrodr=%5B%7B%22action%22%3A%5B%5D%2C%22fieldName%22%3A%22schemaname%22%7D%5D"
            f"&schemaname={schema_id}"
        )
    return links


def _extract_analysis_name_from_payload(data: dict[str, Any]) -> str | None:
    reference = data.get("crawlComparisonReference")
    if isinstance(reference, str) and reference.strip():
        return reference.strip()
    for item in data.get("notableDeltas") or []:
        if not isinstance(item, dict):
            continue
        details = item.get("details")
        if not isinstance(details, str):
            continue
        match = re.search(r"transaction\s*:\s*'([^']+)'", details, re.IGNORECASE)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


def _format_rollup_table(rollup: dict[str, Any] | None) -> str:
    r = rollup or {}
    rows = [
        ("Total changes", r.get("totalChanges", 0)),
        ("Tables added", r.get("tablesAdded", 0)),
        ("Tables deleted", r.get("tablesDeleted", 0)),
        ("Tables modified", r.get("tablesModified", 0)),
        ("Columns added", r.get("columnsAdded", 0)),
        ("Columns deleted", r.get("columnsDeleted", 0)),
        ("Columns modified", r.get("columnsModified", 0)),
    ]
    lines = ["| Metric | Count |", "| --- | ---: |"]
    lines.extend(f"| {metric} | {count} |" for metric, count in rows)
    return "\n".join(lines)


def _format_kv_table(title_a: str, title_b: str, rows: list[tuple[str, str]]) -> str:
    lines = [f"| {title_a} | {title_b} |", "| --- | --- |"]
    lines.extend(f"| {k} | {v} |" for k, v in rows)
    return "\n".join(lines)


def _format_level_summary_table(rollup: dict[str, Any] | None) -> str:
    r = rollup or {}
    table_total = int(r.get("tablesAdded", 0)) + int(r.get("tablesModified", 0)) + int(
        r.get("tablesDeleted", 0)
    )
    schema_total = int(r.get("schemasAdded", 0)) + int(r.get("schemasModified", 0)) + int(
        r.get("schemasRemoved", 0)
    )
    rows = [
        ("Total changes", f"{int(r.get('totalChanges', 0))}"),
        ("Schema-level changes", f"{schema_total}"),
        (
            "Table-level changes",
            f"{table_total} ({int(r.get('tablesAdded', 0))} added, "
            f"{int(r.get('tablesModified', 0))} modified, "
            f"{int(r.get('tablesDeleted', 0))} deleted)",
        ),
        (
            "Column-level changes",
            f"{int(r.get('columnsModified', 0))} modified ({int(r.get('columnsAdded', 0))} added, "
            f"{int(r.get('columnsDeleted', 0))} deleted)",
        ),
    ]
    lines = ["| Metric | Value |", "| --- | --- |"]
    lines.extend(f"| {metric} | {value} |" for metric, value in rows)
    return "\n".join(lines)


def _format_top_adds_table(deltas: list[dict[str, Any]]) -> str:
    rows: list[tuple[str, str]] = []
    for d in deltas[:6]:
        table_name = str(d.get("tableName") or "-")
        delta = int(d.get("rowCountDelta", 0))
        redirect = str(d.get("redirectUrl") or "-")
        rows.append((table_name, f"+{delta:,} ({redirect})"))
    if not rows:
        rows.append(("None", "-"))
    return _format_kv_table("Table", "Row Delta / Redirect", rows)


def _format_links_table(
    links: dict[str, str],
    data: dict[str, Any],
    only_object_redirect: bool = False,
) -> str:
    def _link(label: str, url: str | None) -> str:
        if not url or url == "-":
            return "-"
        return f"[{label}]({url})"

    if only_object_redirect:
        object_redirect = links.get("objectRedirectUrl") or str(data.get("redirectUrl") or "-")
        rows = [("OvalEdge object redirect URL", _link("Open object", object_redirect))]
        return _format_kv_table("Reference", "Value", rows)

    rows = [
        ("CompareSchema", _link("CompareSchema", links.get("compareSchemaUrl"))),
        ("ObjectSchema", _link("ObjectSchema", links.get("objectSchemaUrl"))),
        ("Data change", _link("Data change", links.get("dataChangeUrl"))),
        ("Metadata change", _link("Metadata change", links.get("metadataChangeUrl"))),
        ("Crawl comparison reference", str(data.get("crawlComparisonReference", "-"))),
        ("Change summary", str(data.get("changeSummary", "-"))),
        (
            "Timestamp of analyzed crawls",
            f"{data.get('analyzedFromTimestamp', '-')} -> {data.get('analyzedToTimestamp', '-')}",
        ),
    ]
    return _format_kv_table("Reference", "Value", rows)


def _default_formatted_metadata_response(
    data: dict[str, Any],
    include_links: bool = False,
    header_title: str | None = None,
    show_object_redirect: bool = False,
) -> str:
    ctx = data.get("contextHeader", {}) or {}
    rollup = data.get("rollup", {}) or {}
    deltas = data.get("notableDeltas", []) or []
    sorted_adds = sorted(
        (
            d
            for d in deltas
            if isinstance(d, dict)
            and isinstance(d.get("rowCountDelta"), (int, float))
            and d.get("rowCountDelta", 0) > 0
        ),
        key=lambda d: d["rowCountDelta"],
        reverse=True,
    )[:6]
    links = _build_metadata_links(ctx, data)
    largest_adds = (
        ", ".join(
            f"{d.get('tableName', '-') } (+{int(d.get('rowCountDelta', 0)):,})"
            for d in sorted_adds
        )
        or "None"
    )
    summary_table = _format_level_summary_table(rollup)
    rollup_table = _format_rollup_table(rollup)
    top_adds_table = _format_top_adds_table(sorted_adds)
    links_table = (
        _format_links_table(links, data, only_object_redirect=show_object_redirect)
        if include_links
        else ""
    )
    lines = []
    if header_title:
        lines.extend([f"**{header_title.strip()}**", ""])
    lines.extend([
        "From Transactional Data Impact Analysis "
        f"(connection {ctx.get('connection') or '-'}, "
        f"catalog schema {ctx.get('catalogSchema') or '-'}, "
        f"oes schemaid {ctx.get('schemaId') or '-'}, "
        f"analysis id {ctx.get('analysisId') or '-'}, "
        f"snapshot {ctx.get('snapshotTimestamp') or data.get('analyzedToTimestamp') or '-'}, "
        f"{ctx.get('comparisonBasis') or data.get('crawlComparisonReference') or '-'})",
        "",
        "**Summary**",
        "",
        summary_table,
        "",
        f"**Rollup for {ctx.get('catalogSchema') or '-'}**",
        "",
        rollup_table,
        "",
        "**Notable deltas**",
        f"- Largest row-count adds: {largest_adds}",
        "",
        top_adds_table,
    ])
    if include_links:
        lines.extend(
            [
                "",
                "**Useful links and references**",
                links_table,
            ]
        )
    return "\n".join(lines)


def _enhance_metadata_changes_response(
    raw: dict[str, Any],
    include_links: bool = False,
    header_title: str | None = None,
    show_object_redirect: bool = False,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return raw
    data = raw.get("data")
    if not isinstance(data, dict):
        return raw
    ctx = data.get("contextHeader", {})
    data["topLargeRowCountAdds"] = sorted(
        (
            d
            for d in (data.get("notableDeltas") or [])
            if isinstance(d, dict)
            and isinstance(d.get("rowCountDelta"), (int, float))
            and d.get("rowCountDelta", 0) > 0
        ),
        key=lambda d: d["rowCountDelta"],
        reverse=True,
    )[:6]
    data["usefulLinks"] = _build_metadata_links(ctx, data)
    data["summaryTableMarkdown"] = _format_level_summary_table(data.get("rollup", {}))
    data["rollupTableMarkdown"] = _format_rollup_table(data.get("rollup", {}))
    data["topLargeRowCountAddsTableMarkdown"] = _format_top_adds_table(
        data["topLargeRowCountAdds"]
    )
    data["usefulLinksTableMarkdown"] = _format_links_table(
        data["usefulLinks"],
        data,
        only_object_redirect=show_object_redirect,
    )
    data["formattedResponse"] = _default_formatted_metadata_response(
        data,
        include_links=include_links,
        header_title=header_title,
        show_object_redirect=show_object_redirect,
    )
    # Required compact reference block for clients that need only key fields.
    redirect_url = str(
        data.get("redirectUrl") or data["usefulLinks"].get("objectRedirectUrl") or "-"
    )
    crawl_ref = str(data.get("crawlComparisonReference") or "-")
    change_summary = str(data.get("changeSummary") or "-")
    analyzed_from = str(data.get("analyzedFromTimestamp") or "-")
    analyzed_to = str(data.get("analyzedToTimestamp") or "-")
    data["requiredInfo"] = {
        "ovaledgeObjectRedirectUrl": redirect_url,
        "crawlComparisonReference": crawl_ref,
        "changeSummary": change_summary,
        "timestampOfAnalyzedCrawls": f"{analyzed_from} -> {analyzed_to}",
        "requiredInfoMarkdown": "\n".join(
            [
                "Required info",
                f"- OvalEdge object redirect URL: [{redirect_url}]({redirect_url})"
                if redirect_url.startswith("http")
                else f"- OvalEdge object redirect URL: {redirect_url}",
                f"- Crawl comparison reference: {crawl_ref}",
                f"- Change summary: {change_summary}",
                f"- Timestamp of analyzed crawls: {analyzed_from} -> {analyzed_to}",
            ]
        ),
    }
    # Mirror key at top-level for clients that do not traverse data.formattedResponse.
    raw["formattedResponse"] = data["formattedResponse"]
    raw["summaryTableMarkdown"] = data["summaryTableMarkdown"]
    raw["requiredInfo"] = data["requiredInfo"]
    return raw


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


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_SEARCH)
    async def search_catalog_assets(
        search_terms: Annotated[
            list[str] | None,
            Field(
                description=(
                    "General lexical keywords (names, descriptions, metadata text). JSON array "
                    f"on the wire as {MCP_SEARCH_TERMS_PARAM}. "
                    'e.g. ["customer","revenue"]. Not for governance tag names — use tags instead.'
                ),
                default=None,
            ),
        ] = None,
        tags: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Governance tag names to match (OETAG assignments). JSON array on the wire "
                    f"as {MCP_SEARCH_TAGS_PARAM}. "
                    'Use when the user asks for assets "with tag X" or "tagged X". '
                    'e.g. ["Operations","PII"].'
                ),
                default=None,
            ),
        ] = None,
        terms: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Glossary term names for lexical search. JSON array on the wire as "
                    f"{MCP_SEARCH_GLOSSARY_TERMS_PARAM}. "
                    'Use when the user asks for assets linked to glossary/business terms. '
                    'e.g. ["Revenue","Customer"].'
                ),
                default=None,
            ),
        ] = None,
        custom_fields: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Custom field values or labels to match. JSON array on the wire as "
                    f"{MCP_SEARCH_CUSTOM_FIELDS_PARAM}. "
                    'e.g. ["Confidential","Operations"].'
                ),
                default=None,
            ),
        ] = None,
        data_products: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Data product names/keywords. JSON array on the wire as "
                    f"{MCP_SEARCH_DATA_PRODUCTS_PARAM}. "
                    'e.g. ["Customer 360"].'
                ),
                default=None,
            ),
        ] = None,
        context_query: Annotated[
            str | None,
            Field(
                description=(
                    "Full user question or contextual NL string for the server (maps to "
                    f"API {MCP_SEARCH_CONTEXT_QUERY_PARAM}). Use for vector / semantic search "
                    "or hybrid ranking alongside lexical params. Prefer verbatim user wording."
                ),
                default=None,
            ),
        ] = None,
        page: Annotated[
            int,
            Field(description="1-based page index (default 1).", ge=1),
        ] = 1,
        limit: Annotated[
            int,
            Field(description="Page size (default 20; capped at 100 for this client).", ge=1),
        ] = 20,
        connection_name: Annotated[
            str | None,
            Field(
                description=(
                    "Filter: exact connection name (API connectionName). "
                    'Infer when user names a source, e.g. "ovaledgedb" or "Snowflake PROD".'
                ),
                default=None,
            ),
        ] = None,
        server_type: Annotated[
            str | None,
            Field(
                description=(
                    "Filter: connection technology (API serverType → connectionInfo.serverType). "
                    "Use a canonical connector id when the user names a platform, e.g. mysql, "
                    "snowflake, postgres, redshift, bigquery, tableau, oracle, sqlserver. "
                    "Omit when the question does not clearly imply one connector — do not guess. "
                    "Case-insensitive match to the platform allowlist."
                ),
                default=None,
            ),
        ] = None,
        schema_name: Annotated[
            str | None,
            Field(
                description=(
                    "Filter: exact schema name (API schemaName). "
                    'Infer when user names a schema/database context, e.g. "sakila".'
                ),
                default=None,
            ),
        ] = None,
        owner: Annotated[
            str | None,
            Field(
                description=(
                    "Filter: asset owner login or display name (API owner). "
                    "Infer when user asks for assets owned by someone."
                ),
                default=None,
            ),
        ] = None,
        steward: Annotated[
            str | None,
            Field(
                description=(
                    "Filter: steward login or display name (API steward). "
                    "Infer when user asks for stewarded assets."
                ),
                default=None,
            ),
        ] = None,
        custodian: Annotated[
            str | None,
            Field(
                description=(
                    "Filter: custodian login or display name (API custodian). "
                    "Infer when user asks for custodian-assigned assets."
                ),
                default=None,
            ),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                description=(
                    "Filter: restrict to one catalog object type (API objectType): "
                    + MCP_CATALOG_OBJECT_TYPES_DOC
                    + '. Infer when user asks for "tables", "reports/charts", "tags", etc. '
                    "(e.g. tables → oetable, reports → oechart). Omit for all types."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """OvalEdge catalog search (see MCP tool description)."""
        if object_type is not None and object_type not in MCP_CATALOG_OBJECT_TYPES:
            return {
                "error": (
                    f"object_type must be one of {sorted(MCP_CATALOG_OBJECT_TYPES)}, "
                    f"got {object_type!r}"
                ),
                "status_code": 400,
            }
        resolved_server_type = _resolve_server_type(server_type)
        if server_type is not None and str(server_type).strip() and resolved_server_type is None:
            return {
                "error": (
                    f"server_type must be a known connector type, got {server_type!r}. "
                    "Omit server_type when the user question does not specify a platform."
                ),
                "status_code": 400,
            }
        try:
            params: dict[str, object] = _q(
                **{MCP_SEARCH_CONTEXT_QUERY_PARAM: context_query},
                page=max(page, 1),
                limit=min(max(limit, 1), 100),
                connectionName=connection_name,
                **{MCP_SEARCH_SERVER_TYPE_PARAM: resolved_server_type},
                schemaName=schema_name,
                owner=owner,
                steward=steward,
                custodian=custodian,
                objectType=object_type,
            )
            _apply_lexical_search_params(
                params,
                search_terms=search_terms,
                tags=tags,
                terms=terms,
                custom_fields=custom_fields,
                data_products=data_products,
            )
            async with OvalEdgeClient() as client:
                return await client.get(MCP_PATH_SEARCH_CATALOG, params=params)
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_DETAILS)
    async def catalog_asset_details(
        object_id: Annotated[
            int | None,
            Field(
                description="Internal catalog id; must be used with object_type (not with FQN).",
                default=None,
            ),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                description=(
                    "One of: "
                    + MCP_CATALOG_OBJECT_TYPES_DOC
                    + "; pair with object_id."
                ),
                default=None,
            ),
        ] = None,
        fully_qualified_name: Annotated[
            str | None,
            Field(
                description="Fully qualified name alone; do not pass object_id/object_type.",
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Single catalog document (see MCP tool description)."""
        has_fqn = fully_qualified_name is not None and str(fully_qualified_name).strip() != ""
        has_pair = object_id is not None and object_type is not None
        if has_fqn and (object_id is not None or object_type is not None):
            return {
                "error": (
                    "Use either fully_qualified_name alone, or object_id + object_type "
                    "— not both."
                ),
                "status_code": 400,
            }
        if not has_fqn and not has_pair:
            return {
                "error": "Provide fully_qualified_name, or both object_id and object_type.",
                "status_code": 400,
            }
        if has_pair:
            if object_id is None or object_type is None:
                return {
                    "error": "object_id and object_type must be provided together.",
                    "status_code": 400,
                }
            if object_type not in MCP_CATALOG_OBJECT_TYPES:
                return {
                    "error": (
                        f"object_type must be one of {sorted(MCP_CATALOG_OBJECT_TYPES)}, "
                        f"got {object_type!r}"
                    ),
                    "status_code": 400,
                }
        try:
            async with OvalEdgeClient() as client:
                if has_fqn:
                    od_params: dict[str, object] = _q(
                        fullyQualifiedName=fully_qualified_name,
                    )
                else:
                    od_params = _q(objectId=object_id, objectType=object_type)
                return await client.get(MCP_PATH_OBJECT_DETAILS, params=od_params)
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_COLUMN)
    async def column_profile_statistics(
        object_id: Annotated[int, Field(description="Table or file internal object id.")],
        object_type: Annotated[
            str,
            Field(description="Must be oetable or oefile."),
        ],
    ) -> dict[str, Any]:
        """Column profile stats (see MCP tool description)."""
        if object_type not in _TABLE_FILE_TYPES:
            return {
                "error": f"object_type must be oetable or oefile, got {object_type!r}",
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_COLUMN_PROFILE,
                    params={"objectId": object_id, "objectType": object_type},
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_REL)
    async def table_entity_relationships(
        object_id: Annotated[int, Field(description="oetable internal object id.")],
    ) -> dict[str, Any]:
        """Table entity relationships (see MCP tool description)."""
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_ENTITY_RELATIONSHIPS,
                    params={"objectId": object_id},
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_LINEAGE)
    async def asset_lineage(
        object_id: Annotated[int, Field(description="Table or file internal object id.")],
        object_type: Annotated[
            str,
            Field(description="oetable or oefile."),
        ],
        depth: Annotated[
            int,
            Field(description="Lineage depth (default 2); server may clamp.", ge=0),
        ] = 2,
    ) -> dict[str, Any]:
        """Asset lineage graph (see MCP tool description)."""
        if object_type not in _TABLE_FILE_TYPES:
            return {
                "error": f"object_type must be oetable or oefile, got {object_type!r}",
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                return await client.get(
                    MCP_PATH_LINEAGE,
                    params={
                        "objectId": object_id,
                        "objectType": object_type,
                        "depth": depth,
                    },
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_UPDATE_DESCRIPTIONS)
    async def update_asset_descriptions(
        object_id: Annotated[
            int,
            Field(
                description="Internal catalog id from search_catalog_assets items[].objectId.",
                ge=1,
            ),
        ],
        object_type: Annotated[
            str,
            Field(
                description=(
                    "OvalEdge object type from search (e.g. oetable, oecolumn, glossary): "
                    + MCP_CATALOG_OBJECT_TYPES_DOC
                ),
            ),
        ],
        business_description: Annotated[
            str | None,
            Field(description="Business / wiki description (wikitext).", default=None),
        ] = None,
        technical_description: Annotated[
            str | None,
            Field(
                description="Technical Description (wiki techtext; not Source Description).",
                default=None,
            ),
        ] = None,
        detailed_description: Annotated[
            str | None,
            Field(description="Detailed / tech wiki description.", default=None),
        ] = None,
        domain_description: Annotated[
            str | None,
            Field(description="Domain description (domain assets).", default=None),
        ] = None,
        tag_description: Annotated[
            str | None,
            Field(description="Tag description (oetag assets).", default=None),
        ] = None,
        master_tag_description: Annotated[
            str | None,
            Field(description="Master tag description.", default=None),
        ] = None,
        description_field: Annotated[
            str | None,
            Field(
                description=(
                    "Which description slot to update (snake_case): business_description, "
                    "technical_description, detailed_description, domain_description, "
                    "tag_description, or master_tag_description. REQUIRED with "
                    "description_text when the user did not specify business vs technical."
                ),
                default=None,
            ),
        ] = None,
        description_text: Annotated[
            str | None,
            Field(
                description=(
                    "Description text to write. Pair with description_field when the user "
                    "says 'description' without naming the slot."
                ),
                default=None,
            ),
        ] = None,
        dry_run: Annotated[
            bool | None,
            Field(description="If true, validate only; do not persist.", default=None),
        ] = None,
        fail_on_blocked_field: Annotated[
            bool | None,
            Field(
                description="If true, treat any blocked field as a full request failure.",
                default=None,
            ),
        ] = None,
        idempotency_key: Annotated[
            str | None,
            Field(description="Optional client key to dedupe retries.", default=None),
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
    ) -> dict[str, Any]:
        """Update asset descriptions (see MCP tool description)."""
        if object_type not in MCP_CATALOG_OBJECT_TYPES:
            return {
                "error": (
                    f"object_type must be one of {sorted(MCP_CATALOG_OBJECT_TYPES)}, "
                    f"got {object_type!r}"
                ),
                "status_code": 400,
            }
        validation_error = _validate_description_inputs(
            object_type,
            description_field=description_field,
            description_text=description_text,
            business_description=business_description,
            technical_description=technical_description,
            detailed_description=detailed_description,
            domain_description=domain_description,
            tag_description=tag_description,
            master_tag_description=master_tag_description,
            prompt=prompt,
        )
        if validation_error:
            return validation_error
        body = _build_update_descriptions_body(
            object_id,
            object_type,
            business_description=business_description,
            technical_description=technical_description,
            detailed_description=detailed_description,
            domain_description=domain_description,
            tag_description=tag_description,
            master_tag_description=master_tag_description,
            description_field=description_field,
            description_text=description_text,
            dry_run=dry_run,
            fail_on_blocked_field=fail_on_blocked_field,
            idempotency_key=idempotency_key,
            prompt=prompt,
            reason=reason,
        )
        if not body.get("descriptions"):
            return {
                "error": (
                    "Provide description_field + description_text, or one typed description "
                    f"field. For {object_type}: {_description_field_hint(object_type)}."
                ),
                "status_code": 400,
            }
        try:
            async with OvalEdgeClient() as client:
                result = await client.post(MCP_PATH_UPDATE_ASSET_DESCRIPTIONS, body)
                if isinstance(result, dict):
                    return _enrich_update_descriptions_response(result)
                return result
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}

    @mcp.tool(description=_DESC_METADATA_CHANGES)
    async def get_metadata_changes_between_crawls(
        question: Annotated[
            str | None,
            Field(description="Optional natural-language question from user.", default=None),
        ] = None,
        connection_name: Annotated[
            str | None,
            Field(description="Filter by connection name.", default=None),
        ] = None,
        schema_names: Annotated[
            list[str] | None,
            Field(description="Optional schema names filter.", default=None),
        ] = None,
        table_names: Annotated[
            list[str] | None,
            Field(description="Optional table names filter.", default=None),
        ] = None,
        from_timestamp: Annotated[
            str | None,
            Field(description="ISO timestamp start boundary.", default=None),
        ] = None,
        to_timestamp: Annotated[
            str | None,
            Field(description="ISO timestamp end boundary.", default=None),
        ] = None,
        last_n_days: Annotated[
            int | None,
            Field(description="Analyze last N days.", ge=1, default=None),
        ] = None,
        last_n_weeks: Annotated[
            int | None,
            Field(description="Analyze last N weeks.", ge=1, default=None),
        ] = None,
        from_crawl_id: Annotated[
            int | None,
            Field(description="Lower crawl/timeline boundary.", ge=1, default=None),
        ] = None,
        to_crawl_id: Annotated[
            int | None,
            Field(description="Upper crawl/timeline boundary.", ge=1, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """Metadata drift between crawls (schema/table/column)."""
        if last_n_days is not None and last_n_weeks is not None:
            return {
                "error": "Provide either last_n_days or last_n_weeks, not both.",
                "status_code": 400,
            }
        if (
            from_crawl_id is not None
            and to_crawl_id is not None
            and from_crawl_id > to_crawl_id
        ):
            return {
                "error": "from_crawl_id must be <= to_crawl_id.",
                "status_code": 400,
            }
        body = _q(
            question=question,
            connectionName=connection_name,
            schemaNames=_normalize_search_terms(schema_names),
            tableNames=_normalize_search_terms(table_names),
            fromTimestamp=from_timestamp,
            toTimestamp=to_timestamp,
            lastNDays=last_n_days,
            lastNWeeks=last_n_weeks,
            fromCrawlId=from_crawl_id,
            toCrawlId=to_crawl_id,
        )
        try:
            async with OvalEdgeClient() as client:
                raw = await client.post(
                    MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
                    body=body,
                )
                # Keep one consistent user-facing format for all metadata-change queries.
                return _enhance_metadata_changes_response(
                    raw,
                    include_links=True,
                    header_title=question,
                    show_object_redirect=_is_specific_table_compare(
                        question, _normalize_search_terms(table_names)
                    ),
                )
        except OvalEdgeError as e:
            return {"error": str(e), "status_code": e.status_code}
