"""Invocation logic for catalog MCP tools (extracted from register)."""

from __future__ import annotations

from typing import Annotated, Any

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
    MCP_SEARCH_CATEGORY_ID_PARAM,
    MCP_SEARCH_CATEGORY_NAME_PARAM,
    MCP_SEARCH_CLASSIFICATIONS_PARAM,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_CUSTOM_FIELDS_PARAM,
    MCP_SEARCH_DATA_PRODUCTS_PARAM,
    MCP_SEARCH_DOMAIN_ID_PARAM,
    MCP_SEARCH_DOMAIN_NAME_PARAM,
    MCP_SEARCH_GLOSSARY_TERMS_PARAM,
    MCP_SEARCH_SERVER_TYPE_PARAM,
    MCP_SEARCH_SUBCATEGORY_ID_PARAM,
    MCP_SEARCH_SUBCATEGORY_NAME_PARAM,
    MCP_SEARCH_TAGS_PARAM,
    MCP_SEARCH_TERMS_PARAM,
)
from server.mcp_response_slim import slim_tool_response
from server.tools.catalog.cde_helpers import (
    build_update_cde_body,
    enrich_update_cde_response,
    format_update_cde_confirmation_preview,
    validate_cde_inputs,
)
from server.tools.catalog.formatters import _enhance_metadata_changes_response
from server.tools.catalog.helpers import (
    _TABLE_FILE_TYPES,
    _apply_lexical_search_params,
    _build_update_descriptions_body,
    _description_field_hint,
    _enrich_catalog_details_response,
    _enrich_catalog_search_response,
    _enrich_update_descriptions_response,
    _format_update_descriptions_confirmation_preview,
    _is_specific_table_compare,
    _normalize_search_terms,
    _resolve_server_type,
    _validate_description_inputs,
)
from server.tools.common import drop_none as _q
from server.tools.common import map_ovaledge_error, ovaledge_client, strip_or_none


async def _invoke_search_catalog_assets(
    search_terms: Annotated[
        list[str] | None,
        Field(
            description=(
                f"Lexical keywords (wire: {MCP_SEARCH_TERMS_PARAM}). Not for tag names."
            ),
            default=None,
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(
            description=f"Governance tag names (wire: {MCP_SEARCH_TAGS_PARAM}).",
            default=None,
        ),
    ] = None,
    terms: Annotated[
        list[str] | None,
        Field(
            description=f"Glossary term names (wire: {MCP_SEARCH_GLOSSARY_TERMS_PARAM}).",
            default=None,
        ),
    ] = None,
    custom_fields: Annotated[
        list[str] | None,
        Field(
            description=f"Custom field values (wire: {MCP_SEARCH_CUSTOM_FIELDS_PARAM}).",
            default=None,
        ),
    ] = None,
    data_products: Annotated[
        list[str] | None,
        Field(
            description=f"Data product names (wire: {MCP_SEARCH_DATA_PRODUCTS_PARAM}).",
            default=None,
        ),
    ] = None,
    classifications: Annotated[
        list[str] | None,
        Field(
            description=f"Classification labels (wire: {MCP_SEARCH_CLASSIFICATIONS_PARAM}).",
            default=None,
        ),
    ] = None,
    critical_data_element: Annotated[
        list[str] | None,
        Field(
            description='CDE flag values (wire: criticalDataElement), e.g. ["Yes"].',
            default=None,
        ),
    ] = None,
    context_query: Annotated[
        str | None,
        Field(
            description=(
                "Verbatim user question for semantic ranking "
                f"(wire: {MCP_SEARCH_CONTEXT_QUERY_PARAM})."
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
        Field(description="Exact connection name filter (API connectionName).", default=None),
    ] = None,
    server_type: Annotated[
        str | None,
        Field(
            description="Connector technology filter (API serverType); omit if not implied.",
            default=None,
        ),
    ] = None,
    schema_name: Annotated[
        str | None,
        Field(description="Exact schema name filter (API schemaName).", default=None),
    ] = None,
    owner: Annotated[
        str | None,
        Field(description="Owner login or display name filter.", default=None),
    ] = None,
    steward: Annotated[
        str | None,
        Field(description="Steward login or display name filter.", default=None),
    ] = None,
    custodian: Annotated[
        str | None,
        Field(description="Custodian login or display name filter.", default=None),
    ] = None,
    object_type: Annotated[
        str | None,
        Field(
            description="Catalog objectType filter; see docs://ovaledge/asset_types.",
            default=None,
        ),
    ] = None,
    domain_id: Annotated[
        int | None,
        Field(
            description=(
                "Glossary global domain id for placement filter; pair with optional "
                "category/subcategory."
            ),
            default=None,
        ),
    ] = None,
    domain_name: Annotated[
        str | None,
        Field(
            description="Glossary global domain name when domain_id is unknown.",
            default=None,
        ),
    ] = None,
    category_id: Annotated[
        int | None,
        Field(description="Glossary category id for placement filter.", default=None),
    ] = None,
    category_name: Annotated[
        str | None,
        Field(description="Glossary category name when category_id is unknown.", default=None),
    ] = None,
    subcategory_id: Annotated[
        int | None,
        Field(description="Glossary subcategory id for placement filter.", default=None),
    ] = None,
    subcategory_name: Annotated[
        str | None,
        Field(
            description="Glossary subcategory name when subcategory_id is unknown.",
            default=None,
        ),
    ] = None,
) -> dict[str, Any]:
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
            **{
                MCP_SEARCH_DOMAIN_ID_PARAM: domain_id
                if domain_id is not None and domain_id > 0
                else None,
                MCP_SEARCH_DOMAIN_NAME_PARAM: strip_or_none(domain_name),
                MCP_SEARCH_CATEGORY_ID_PARAM: category_id
                if category_id is not None and category_id > 0
                else None,
                MCP_SEARCH_CATEGORY_NAME_PARAM: strip_or_none(category_name),
                MCP_SEARCH_SUBCATEGORY_ID_PARAM: subcategory_id
                if subcategory_id is not None and subcategory_id > 0
                else None,
                MCP_SEARCH_SUBCATEGORY_NAME_PARAM: strip_or_none(subcategory_name),
            },
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
            body = await client.get(MCP_PATH_SEARCH_CATALOG, params=params)
            if not isinstance(body, dict):
                return {"data": body}
            return slim_tool_response(_enrich_catalog_search_response(body))
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


async def _invoke_catalog_asset_details(
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
            body = await client.get(MCP_PATH_OBJECT_DETAILS, params=od_params)
            if not isinstance(body, dict):
                return {"data": body}
            return slim_tool_response(_enrich_catalog_details_response(body))
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


async def _invoke_column_profile_statistics(
    object_id: Annotated[int, Field(description="Table or file internal object id.")],
    object_type: Annotated[
        str,
        Field(description="Must be oetable or oefile."),
    ],
) -> dict[str, Any]:
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


async def _invoke_table_entity_relationships(
    object_id: Annotated[int, Field(description="oetable internal object id.")],
) -> dict[str, Any]:
    try:
        async with ovaledge_client() as client:
            return await client.get(
                MCP_PATH_ENTITY_RELATIONSHIPS,
                params={"objectId": object_id},
            )
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


async def _invoke_asset_lineage(
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


async def _invoke_update_asset_descriptions(
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


async def _invoke_update_cde_associations(
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


async def _invoke_metadata_changes_between_crawls(
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
