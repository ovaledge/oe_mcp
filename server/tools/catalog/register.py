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
    _DESC_ASSET_DETAILS,
    _DESC_ASSET_EXPLORER,
    _DESC_ASSET_LINEAGE,
    _DESC_METADATA_CHANGES,
    _DESC_UPDATE_DESCRIPTIONS,
)
from server.tools.catalog.invocations import (
    _invoke_asset_details,
    _invoke_asset_explorer,
    _invoke_asset_lineage,
    _invoke_metadata_changes_between_crawls,
    _invoke_update_asset_descriptions,
    _invoke_update_cde_associations,
)
from server.tools.common.annotations import GOVERNED_UPDATE, READ_ONLY
from server.tools.common.confirm_gate import CONFIRMATION_TOKEN_PARAM_DESCRIPTION


def register(mcp: FastMCP) -> None:

    @mcp.tool(title="Find data assets", description=_DESC_ASSET_EXPLORER, annotations=READ_ONLY)
    async def asset_explorer(
        search_terms: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Business keywords to search (e.g. payment, customer). "
                    f"Wire: {MCP_SEARCH_TERMS_PARAM}. Not for exact tag names."
                ),
                default=None,
            ),
        ] = None,
        tags: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Exact tag names already defined in OvalEdge "
                    f"(wire: {MCP_SEARCH_TAGS_PARAM}); case-insensitive."
                ),
                default=None,
            ),
        ] = None,
        terms: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Exact glossary term names "
                    f"(wire: {MCP_SEARCH_GLOSSARY_TERMS_PARAM}); case-insensitive."
                ),
                default=None,
            ),
        ] = None,
        custom_fields: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Custom field values to match "
                    f"(wire: {MCP_SEARCH_CUSTOM_FIELDS_PARAM})."
                ),
                default=None,
            ),
        ] = None,
        data_products: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Data product names "
                    f"(wire: {MCP_SEARCH_DATA_PRODUCTS_PARAM})."
                ),
                default=None,
            ),
        ] = None,
        classifications: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Classification labels (e.g. PII) "
                    f"(wire: {MCP_SEARCH_CLASSIFICATIONS_PARAM})."
                ),
                default=None,
            ),
        ] = None,
        critical_data_element: Annotated[
            list[str] | None,
            Field(
                description='Critical Data Element flags, e.g. ["Yes"].',
                default=None,
            ),
        ] = None,
        context_query: Annotated[
            str | None,
            Field(
                description=(
                    "User's full question in plain language (improves ranking) "
                    f"(wire: {MCP_SEARCH_CONTEXT_QUERY_PARAM})."
                ),
                default=None,
            ),
        ] = None,
        page: Annotated[
            int,
            Field(description="Results page number (starts at 1).", ge=1),
        ] = 1,
        limit: Annotated[
            int,
            Field(description="How many results per page (default 20; max 50).", ge=1),
        ] = 20,
        connection_name: Annotated[
            str | None,
            Field(description="Limit to one connection/source name.", default=None),
        ] = None,
        server_type: Annotated[
            str | None,
            Field(
                description="Limit to a connector technology (e.g. snowflake); omit if unknown.",
                default=None,
            ),
        ] = None,
        schema_name: Annotated[
            str | None,
            Field(description="Limit to one schema name.", default=None),
        ] = None,
        owner: Annotated[
            str | None,
            Field(description="Filter by owner login or display name.", default=None),
        ] = None,
        steward: Annotated[
            str | None,
            Field(description="Filter by steward login or display name.", default=None),
        ] = None,
        custodian: Annotated[
            str | None,
            Field(description="Filter by custodian login or display name.", default=None),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(
                description=(
                    "Leave empty to search all asset types. Set only when the user asks "
                    "for one kind (table, column, glossary, tag, …). "
                    "See docs://ovaledge/asset_types."
                ),
                default=None,
            ),
        ] = None,
        domain_id: Annotated[
            int | None,
            Field(
                description=(
                    "Glossary domain id when filtering or looking up terms by placement."
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
            Field(description="Glossary subcategory id.", default=None),
        ] = None,
        subcategory_name: Annotated[
            str | None,
            Field(
                description="Glossary subcategory name when subcategory_id is unknown.",
                default=None,
            ),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(
                description=(
                    "Known glossary or tag id; pair with object_type=glossary or oetag."
                ),
                default=None,
            ),
        ] = None,
        name: Annotated[
            str | None,
            Field(
                description=(
                    "Exact glossary term or tag name; pair with object_type=glossary or oetag."
                ),
                default=None,
            ),
        ] = None,
        include_parent: Annotated[
            bool,
            Field(
                description="When looking up a tag, also return its parent tag.",
                default=False,
            ),
        ] = False,
        include_children: Annotated[
            bool,
            Field(
                description="When looking up a tag, also return child tags.",
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Find data assets related to a business question (catalog search)."""
        return await _invoke_asset_explorer(
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
            object_id=object_id,
            name=name,
            include_parent=include_parent,
            include_children=include_children,
        )

    @mcp.tool(title="View asset details", description=_DESC_ASSET_DETAILS, annotations=READ_ONLY)
    async def asset_details(
        object_id: Annotated[
            int,
            Field(
                description=(
                    "Asset id from Find data assets (asset_explorer); required with object_type."
                ),
            ),
        ],
        object_type: Annotated[
            str,
            Field(
                description=(
                    "Asset type from search results. One of: "
                    + MCP_CATALOG_OBJECT_TYPES_DOC
                    + "."
                ),
            ),
        ],
    ) -> dict[str, Any]:
        """View full metadata for one chosen catalog asset."""
        return await _invoke_asset_details(
            object_id=object_id,
            object_type=object_type,
        )

    @mcp.tool(title="Trace data lineage", description=_DESC_ASSET_LINEAGE, annotations=READ_ONLY)
    async def asset_lineage(
        object_id: Annotated[
            int,
            Field(description="Table or file id from Find data assets."),
        ],
        object_type: Annotated[
            str,
            Field(description="Must be oetable (table) or oefile (file)."),
        ],
        depth: Annotated[
            int,
            Field(description="How many hops to include (default 2).", ge=0),
        ] = 2,
    ) -> dict[str, Any]:
        """Trace where a table or file comes from and what uses it."""
        return await _invoke_asset_lineage(
            object_id=object_id,
            object_type=object_type,
            depth=depth,
        )

    @mcp.tool(
        title="Update asset descriptions",
        description=_DESC_UPDATE_DESCRIPTIONS,
        annotations=GOVERNED_UPDATE,
    )
    async def update_asset_descriptions(
        object_id: Annotated[
            int,
            Field(
                description="Internal catalog id from asset_explorer items[].objectId.",
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

    @mcp.tool(
        title="Mark critical data elements",
        description=_DESC_UPDATE_CDE,
        annotations=GOVERNED_UPDATE,
    )
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

    @mcp.tool(
        title="Compare metadata changes",
        description=_DESC_METADATA_CHANGES,
        annotations=READ_ONLY,
    )
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
