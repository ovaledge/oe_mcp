"""Invocation logic for catalog MCP tools (extracted from register)."""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError
from server.constants import (
    MCP_CATALOG_OBJECT_TYPES,
    MCP_PATH_ASSET_DETAILS,
    MCP_PATH_ASSET_EXPLORER,
    MCP_PATH_ASSET_LINEAGE,
    MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS,
    MCP_PATH_UPDATE_ASSET_DESCRIPTIONS,
    MCP_PATH_UPDATE_CDE_ASSOCIATIONS,
    MCP_SEARCH_CATALOG_MAX_LIMIT,
    MCP_SEARCH_CATEGORY_ID_PARAM,
    MCP_SEARCH_CATEGORY_NAME_PARAM,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_DOMAIN_ID_PARAM,
    MCP_SEARCH_DOMAIN_NAME_PARAM,
    MCP_SEARCH_SERVER_TYPE_PARAM,
    MCP_SEARCH_SUBCATEGORY_ID_PARAM,
    MCP_SEARCH_SUBCATEGORY_NAME_PARAM,
)
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
    _enrich_asset_explorer_response,
    _enrich_catalog_details_response,
    _enrich_update_descriptions_response,
    _format_update_descriptions_confirmation_preview,
    _is_specific_table_compare,
    _normalize_search_terms,
    _resolve_server_type,
    _validate_description_inputs,
)
from server.tools.common import drop_none as _q
from server.tools.common import map_ovaledge_error, ovaledge_client, strip_or_none
from server.tools.common.confirm_gate import verify_write_confirmation
from server.tools.common.tool_logging import logged_tool_invocation


@logged_tool_invocation
async def _invoke_asset_explorer(
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
    server_type: str | None = None,
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
) -> dict[str, Any]:
    """GET asset-explorer — find related catalog assets; omit object_type unless inferred."""
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
            limit=min(max(limit, 1), MCP_SEARCH_CATALOG_MAX_LIMIT),
            connectionName=connection_name,
            **{MCP_SEARCH_SERVER_TYPE_PARAM: resolved_server_type},
            schemaName=schema_name,
            owner=owner,
            steward=steward,
            custodian=custodian,
            objectType=object_type,
            objectId=object_id if object_id is not None and object_id > 0 else None,
            name=strip_or_none(name),
            includeParent=True if include_parent else None,
            includeChildren=True if include_children else None,
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
            body = await client.get(MCP_PATH_ASSET_EXPLORER, params=params)
            if not isinstance(body, dict):
                return {"data": body}
            return _enrich_asset_explorer_response(body)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_asset_details(
    object_id: int,
    object_type: str,
) -> dict[str, Any]:
    """GET asset-details — full metadata for one chosen object_id + object_type."""
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
            body = await client.get(
                MCP_PATH_ASSET_DETAILS,
                params={"objectId": object_id, "objectType": object_type},
            )
            if not isinstance(body, dict):
                return {"data": body}
            return _enrich_catalog_details_response(body)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_asset_lineage(
    object_id: int,
    object_type: str,
    depth: int = 2,
) -> dict[str, Any]:
    """GET asset-lineage — graph for oetable/oefile only."""
    if object_type not in _TABLE_FILE_TYPES:
        return {
            "error": f"object_type must be oetable or oefile, got {object_type!r}",
            "status_code": 400,
        }
    try:
        async with ovaledge_client() as client:
            return await client.get(
                MCP_PATH_ASSET_LINEAGE,
                params={
                    "objectId": object_id,
                    "objectType": object_type,
                    "depth": depth,
                },
            )
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_update_asset_descriptions(
    object_id: int,
    object_type: str,
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
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
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
    if not is_dry and not write_confirmed_by_user:
        return _format_update_descriptions_confirmation_preview(body)
    if not is_dry:
        confirm_err = verify_write_confirmation(
            body,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )
        if confirm_err is not None:
            return confirm_err
    try:
        async with ovaledge_client() as client:
            result = await client.post(MCP_PATH_UPDATE_ASSET_DESCRIPTIONS, body)
            if isinstance(result, dict):
                return _enrich_update_descriptions_response(result)
            return result
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_update_cde_associations(
    targets: list[dict[str, Any]],
    action: str,
    cde_category: str | None = None,
    cde_justification: str | None = None,
    dry_run: bool | None = None,
    idempotency_key: str | None = None,
    prompt: str | None = None,
    reason: str | None = None,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
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
    if not is_dry and not write_confirmed_by_user:
        return format_update_cde_confirmation_preview(body)
    if not is_dry:
        confirm_err = verify_write_confirmation(
            body,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )
        if confirm_err is not None:
            return confirm_err
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


@logged_tool_invocation
async def _invoke_metadata_changes_between_crawls(
    question: str | None = None,
    connection_name: str | None = None,
    schema_names: list[str] | None = None,
    table_names: list[str] | None = None,
    from_timestamp: str | None = None,
    to_timestamp: str | None = None,
    last_n_days: int | None = None,
    last_n_weeks: int | None = None,
    from_crawl_id: int | None = None,
    to_crawl_id: int | None = None,
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
