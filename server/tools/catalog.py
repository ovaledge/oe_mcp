"""
Catalog and related data tools (search, details, column profile, relationships, lineage).
"""

import json
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeClient, OvalEdgeError
from server.constants import (
    MCP_CATALOG_OBJECT_TYPES,
    MCP_CATALOG_OBJECT_TYPES_DOC,
    MCP_PATH_COLUMN_PROFILE,
    MCP_PATH_ENTITY_RELATIONSHIPS,
    MCP_PATH_LINEAGE,
    MCP_PATH_OBJECT_DETAILS,
    MCP_PATH_SEARCH_CATALOG,
    MCP_PATH_UPDATE_ASSET_DESCRIPTIONS,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_TERMS_PARAM,
)

_TABLE_FILE_TYPES = frozenset({"oetable", "oefile"})

_DESC_SEARCH = (
    "Search the OvalEdge catalog (Elasticsearch hybrid / keyword search plus optional "
    "server-side vector context). Use for discovery: schemas, tables, columns, files, charts, "
    "APIs, queries, data products, glossary, tags, and stories.\n\n"
    f"Backend: GET {MCP_PATH_SEARCH_CATALOG}\n"
    f"Query params include {MCP_SEARCH_TERMS_PARAM} as a URL-encoded JSON array of strings, "
    "page, limit, filters, objectType, and optionally "
    f"{MCP_SEARCH_CONTEXT_QUERY_PARAM} (full user question for embedding / semantic ranking).\n\n"
    "Pass search_terms as a JSON array of distinct keywords or short phrases (e.g. "
    '["customer","revenue","churn"]). Omit or use [] for filter-only paging.\n\n'
    "Always pass context_query with the user's verbatim question when they asked in natural "
    "language — alongside search_terms.\n\n"
    "object_type must be one of: "
    + MCP_CATALOG_OBJECT_TYPES_DOC
    + " — or omit to search all.\n\n"
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
    "Required: object_id, object_type, and at least one description field.\n\n"
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
    dry_run: bool | None = None,
    fail_on_blocked_field: bool | None = None,
    idempotency_key: str | None = None,
    prompt: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    descriptions: dict[str, str] = {}
    for arg_name, api_key in _DESCRIPTION_API_KEYS:
        value = locals()[arg_name]
        if value is not None:
            descriptions[api_key] = value
    body: dict[str, Any] = {
        "target": {"objectId": object_id, "objectType": object_type},
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
    if isinstance(updated, list) and updated:
        lines.append(f"**Updated fields:** {', '.join(str(f) for f in updated)}")
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


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_SEARCH)
    async def search_catalog_assets(
        search_terms: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Distinct keywords for lexical search; tool argument is a JSON array. "
                    f"On the wire: one query param {MCP_SEARCH_TERMS_PARAM} with a JSON array "
                    'string value, e.g. ["payroll","employee"]. Omit or [] for filters only.'
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
                    "or hybrid ranking alongside search_terms. Prefer verbatim user wording."
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
                description="Filter by data connection name (API: connectionName).",
                default=None,
            ),
        ] = None,
        schema_name: Annotated[
            str | None,
            Field(description="Filter by schema name (API: schemaName).", default=None),
        ] = None,
        owner: Annotated[
            str | None,
            Field(description="Filter by asset owner login/name.", default=None),
        ] = None,
        steward: Annotated[
            str | None,
            Field(description="Filter by steward login/name.", default=None),
        ] = None,
        custodian: Annotated[
            str | None,
            Field(description="Filter by custodian login/name.", default=None),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                description=(
                    "Restrict to one catalog object type: "
                    + MCP_CATALOG_OBJECT_TYPES_DOC
                    + ". Omit for all types."
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
        try:
            terms = _normalize_search_terms(search_terms)
            params: dict[str, object] = _q(
                **{MCP_SEARCH_CONTEXT_QUERY_PARAM: context_query},
                page=max(page, 1),
                limit=min(max(limit, 1), 100),
                connectionName=connection_name,
                schemaName=schema_name,
                owner=owner,
                steward=steward,
                custodian=custodian,
                objectType=object_type,
            )
            if terms is not None:
                params[MCP_SEARCH_TERMS_PARAM] = json.dumps(terms, ensure_ascii=False)
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
        body = _build_update_descriptions_body(
            object_id,
            object_type,
            business_description=business_description,
            technical_description=technical_description,
            detailed_description=detailed_description,
            domain_description=domain_description,
            tag_description=tag_description,
            master_tag_description=master_tag_description,
            dry_run=dry_run,
            fail_on_blocked_field=fail_on_blocked_field,
            idempotency_key=idempotency_key,
            prompt=prompt,
            reason=reason,
        )
        if not body.get("descriptions"):
            return {
                "error": (
                    "Provide at least one description field "
                    "(business_description, technical_description, detailed_description, "
                    "domain_description, tag_description, or master_tag_description)."
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
