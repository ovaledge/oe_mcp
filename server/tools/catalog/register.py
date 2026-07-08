"""MCP tool registration for catalog workflows."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.constants import (
    MCP_CATALOG_OBJECT_TYPES_DOC,
    MCP_SEARCH_CLASSIFICATIONS_PARAM,
    MCP_SEARCH_CONTEXT_QUERY_PARAM,
    MCP_SEARCH_CUSTOM_FIELDS_PARAM,
    MCP_SEARCH_DATA_PRODUCTS_PARAM,
    MCP_SEARCH_GLOSSARY_TERMS_PARAM,
    MCP_SEARCH_TAGS_PARAM,
    MCP_SEARCH_TERMS_PARAM,
)
from server.tools.catalog.cde_helpers import _DESC_UPDATE_CDE
from server.tools.catalog.helpers import (
    _DESC_COLUMN,
    _DESC_DETAILS,
    _DESC_LINEAGE,
    _DESC_METADATA_CHANGES,
    _DESC_REL,
    _DESC_SEARCH,
    _DESC_UPDATE_DESCRIPTIONS,
)
from server.tools.catalog.invocations import (
    _invoke_asset_lineage,
    _invoke_catalog_asset_details,
    _invoke_column_profile_statistics,
    _invoke_metadata_changes_between_crawls,
    _invoke_search_catalog_assets,
    _invoke_table_entity_relationships,
    _invoke_update_asset_descriptions,
    _invoke_update_cde_associations,
)
from server.tools.common.confirm_gate import CONFIRMATION_TOKEN_PARAM_DESCRIPTION


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_SEARCH)
    async def search_catalog_assets(
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
            Field(description="Page size (default 20; capped at 50 for this client).", ge=1),
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
        """search catalog assets (see MCP tool description)."""
        return await _invoke_search_catalog_assets(
            search_terms=search_terms,
            tags=tags,
            terms=terms,
            custom_fields=custom_fields,
            data_products=data_products,
            classifications=classifications,
            critical_data_element=critical_data_element,
            context_query=context_query,
            page=page,
            limit=limit,
            connection_name=connection_name,
            server_type=server_type,
            schema_name=schema_name,
            owner=owner,
            steward=steward,
            custodian=custodian,
            object_type=object_type,
            domain_id=domain_id,
            domain_name=domain_name,
            category_id=category_id,
            category_name=category_name,
            subcategory_id=subcategory_id,
            subcategory_name=subcategory_name,
        )

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
        """catalog asset details (see MCP tool description)."""
        return await _invoke_catalog_asset_details(
            object_id=object_id,
            object_type=object_type,
            fully_qualified_name=fully_qualified_name,
        )

    @mcp.tool(description=_DESC_COLUMN)
    async def column_profile_statistics(
        object_id: Annotated[int, Field(description="Table or file internal object id.")],
        object_type: Annotated[
            str,
            Field(description="Must be oetable or oefile."),
        ],
    ) -> dict[str, Any]:
        """column profile statistics (see MCP tool description)."""
        return await _invoke_column_profile_statistics(
            object_id=object_id,
            object_type=object_type,
        )

    @mcp.tool(description=_DESC_REL)
    async def table_entity_relationships(
        object_id: Annotated[int, Field(description="oetable internal object id.")],
    ) -> dict[str, Any]:
        """table entity relationships (see MCP tool description)."""
        return await _invoke_table_entity_relationships(object_id=object_id)

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
        """asset lineage (see MCP tool description)."""
        return await _invoke_asset_lineage(
            object_id=object_id,
            object_type=object_type,
            depth=depth,
        )

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
        write_confirmed_by_user: Annotated[
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
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """update asset descriptions (see MCP tool description)."""
        return await _invoke_update_asset_descriptions(
            object_id=object_id,
            object_type=object_type,
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
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )

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
        write_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Set true only after the user explicitly confirms the pending CDE update."
                ),
                default=False,
            ),
        ] = False,
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """update cde associations (see MCP tool description)."""
        return await _invoke_update_cde_associations(
            targets=targets,
            action=action,
            cde_category=cde_category,
            cde_justification=cde_justification,
            dry_run=dry_run,
            idempotency_key=idempotency_key,
            prompt=prompt,
            reason=reason,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )

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
        """metadata changes between crawls (see MCP tool description)."""
        return await _invoke_metadata_changes_between_crawls(
            question=question,
            connection_name=connection_name,
            schema_names=schema_names,
            table_names=table_names,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            last_n_days=last_n_days,
            last_n_weeks=last_n_weeks,
            from_crawl_id=from_crawl_id,
            to_crawl_id=to_crawl_id,
        )
