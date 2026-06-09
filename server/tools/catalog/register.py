"""MCP tool registration for catalog workflows."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
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
    MCP_PATH_UPDATE_CDE_ASSOCIATIONS,
    MCP_SEARCH_CLASSIFICATIONS_PARAM,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_CUSTOM_FIELDS_PARAM,
    MCP_SEARCH_DATA_PRODUCTS_PARAM,
    MCP_SEARCH_GLOSSARY_TERMS_PARAM,
    MCP_SEARCH_SERVER_TYPE_PARAM,
    MCP_SEARCH_TAGS_PARAM,
    MCP_SEARCH_TERMS_PARAM,
)
from server.tools.catalog.formatters import _enhance_metadata_changes_response
from server.tools.catalog.helpers import (
    _DESC_COLUMN,
    _DESC_DETAILS,
    _DESC_LINEAGE,
    _DESC_METADATA_CHANGES,
    _DESC_REL,
    _DESC_SEARCH,
    _DESC_UPDATE_DESCRIPTIONS,
    _TABLE_FILE_TYPES,
    _apply_lexical_search_params,
    _build_update_descriptions_body,
    _description_field_hint,
    _enrich_update_descriptions_response,
    _format_update_descriptions_confirmation_preview,
    _is_specific_table_compare,
    _normalize_search_terms,
    _resolve_server_type,
    _validate_description_inputs,
)
from server.tools.cde_helpers import (
    _DESC_UPDATE_CDE,
    build_update_cde_body,
    enrich_update_cde_response,
    format_update_cde_confirmation_preview,
    validate_cde_inputs,
)
from server.tools.common import drop_none as _q
from server.tools.common import map_ovaledge_error, ovaledge_client


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
        classifications: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Governance classification labels to match (e.g. PII, Sensitive). "
                    "JSON array on the wire as "
                    f"{MCP_SEARCH_CLASSIFICATIONS_PARAM}. "
                    'Use when the user asks for assets "classified as X" or with a '
                    'sensitivity label. e.g. ["PII","Financial"].'
                ),
                default=None,
            ),
        ] = None,
        critical_data_element: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Critical Data Element flag values (exact match). JSON array on the wire "
                    'as criticalDataElement. e.g. ["Yes"] for marked CDE columns.'
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
                classifications=classifications,
                critical_data_element=critical_data_element,
            )
            async with ovaledge_client() as client:
                return await client.get(MCP_PATH_SEARCH_CATALOG, params=params)
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

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
            async with ovaledge_client() as client:
                if has_fqn:
                    od_params: dict[str, object] = _q(
                        fullyQualifiedName=fully_qualified_name,
                    )
                else:
                    od_params = _q(objectId=object_id, objectType=object_type)
                return await client.get(MCP_PATH_OBJECT_DETAILS, params=od_params)
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

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
            async with ovaledge_client() as client:
                return await client.get(
                    MCP_PATH_COLUMN_PROFILE,
                    params={"objectId": object_id, "objectType": object_type},
                )
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

    @mcp.tool(description=_DESC_REL)
    async def table_entity_relationships(
        object_id: Annotated[int, Field(description="oetable internal object id.")],
    ) -> dict[str, Any]:
        """Table entity relationships (see MCP tool description)."""
        try:
            async with ovaledge_client() as client:
                return await client.get(
                    MCP_PATH_ENTITY_RELATIONSHIPS,
                    params={"objectId": object_id},
                )
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

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
            async with ovaledge_client() as client:
                return await client.get(
                    MCP_PATH_LINEAGE,
                    params={
                        "objectId": object_id,
                        "objectType": object_type,
                        "depth": depth,
                    },
                )
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

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
        create_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final update gate: true only after the user explicitly approved "
                    "the confirm_update preview. Re-call with the same object_id, "
                    "object_type, description fields, and clientContext."
                ),
                default=False,
            ),
        ] = False,
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
        is_dry = dry_run is True
        if not is_dry and not create_confirmed_by_user:
            return _format_update_descriptions_confirmation_preview(body)
        try:
            async with ovaledge_client() as client:
                result = await client.post(MCP_PATH_UPDATE_ASSET_DESCRIPTIONS, body)
                if isinstance(result, dict):
                    return _enrich_update_descriptions_response(result)
                return result
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

    @mcp.tool(description=_DESC_UPDATE_CDE)
    async def update_cde_associations(
        targets: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Assets to update. Each item: {object_id, object_type}. "
                    "Supported CDE types: oeschema, oetable, oecolumn, oefile, oefilecolumn, "
                    "oechart, chartchild, oeapi, oeapicolumn, oequery."
                ),
            ),
        ],
        action: Annotated[
            str,
            Field(description='CDE action: "Yes", "No", or "None".'),
        ],
        cde_category: Annotated[
            str | None,
            Field(description="Optional category/level when action is Yes or No.", default=None),
        ] = None,
        cde_justification: Annotated[
            str | None,
            Field(description="Optional justification (max 5000 chars).", default=None),
        ] = None,
        dry_run: Annotated[
            bool | None,
            Field(description="If true, validate only; skips confirm gate.", default=None),
        ] = None,
        idempotency_key: Annotated[
            str | None,
            Field(description="Optional idempotency key for retries.", default=None),
        ] = None,
        prompt: Annotated[
            str | None,
            Field(description="Original user prompt for audit context.", default=None),
        ] = None,
        reason: Annotated[
            str | None,
            Field(description="Short reason for the CDE change.", default=None),
        ] = None,
        create_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Set true only after the user explicitly confirms the pending CDE update."
                ),
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Update CDE status on catalog assets (see MCP tool description)."""
        validation_error = validate_cde_inputs(targets, action)
        if validation_error:
            return validation_error
        body = build_update_cde_body(
            targets,
            action,
            cde_category=cde_category,
            cde_justification=cde_justification,
            dry_run=dry_run,
            idempotency_key=idempotency_key,
            prompt=prompt,
            reason=reason,
        )
        is_dry = dry_run is True
        if not is_dry and not create_confirmed_by_user:
            return format_update_cde_confirmation_preview(body)
        try:
            async with ovaledge_client() as client:
                result = await client.post(MCP_PATH_UPDATE_CDE_ASSOCIATIONS, body)
            if isinstance(result, dict) and result.get("ok") is True:
                data = result.get("data")
                if isinstance(data, dict):
                    return enrich_update_cde_response(data)
            if isinstance(result, dict) and result.get("ok") is False:
                out: dict[str, Any] = {
                    "error": result.get("message") or "CDE update failed",
                    "status_code": 400,
                }
                data = result.get("data")
                if isinstance(data, dict):
                    out.update(enrich_update_cde_response(data))
                return out
            if isinstance(result, dict):
                return enrich_update_cde_response(result)
            return {"data": result}
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

    @mcp.tool(description=_DESC_METADATA_CHANGES)
    async def metadata_changes_between_crawls(
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
            async with ovaledge_client() as client:
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
            return map_ovaledge_error(e)
