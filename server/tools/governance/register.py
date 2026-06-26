"""MCP tool registration for governance workflows."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.constants import (
    MCP_CUSTOM_FIELD_OBJECT_TYPES,
    MCP_DOMAIN_METADATA_SIZE_DEFAULT,
    MCP_DOMAIN_METADATA_SIZE_MAX,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    TOOL_UPDATE_CUSTOM_FIELD_VALUE,
)
from server.tools.governance.helpers import (
    _DESC_CREATE_GLOSSARY,
    _DESC_CREATE_TAG,
    _DESC_DATASTORY,
    _DESC_GLOSSARY,
    _DESC_TAGS,
    _DESC_UPDATE_CUSTOM_FIELD_VALUE,
    _DESC_UPDATE_GOVERNANCE_ROLES,
)
from server.tools.governance.invocations import (
    _invoke_create_glossary_term,
    _invoke_create_tag,
    _invoke_lookup_datastory,
    _invoke_lookup_glossary_term,
    _invoke_lookup_tags,
    _invoke_update_custom_field_value,
    _invoke_update_governance_roles,
)


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_GLOSSARY)
    async def lookup_glossary_term(
        object_id: Annotated[
            int | None,
            Field(
                description="Glossary term internal id; omit for name or placement lookup.",
                default=None,
            ),
        ] = None,
        term_name: Annotated[
            str | None,
            Field(
                description="Term name / label to look up; omit if using object_id or placement.",
                default=None,
            ),
        ] = None,
        domain_id: Annotated[
            int | None,
            Field(
                description=(
                    "Global domain id for placement lookup; use with optional category/subcategory."
                ),
                default=None,
            ),
        ] = None,
        domain_name: Annotated[
            str | None,
            Field(
                description="Global domain name for placement lookup when domain_id is unknown.",
                default=None,
            ),
        ] = None,
        category_id: Annotated[
            int | None,
            Field(description="Category id (category1Id) for placement lookup.", default=None),
        ] = None,
        category_name: Annotated[
            str | None,
            Field(
                description="Category name for placement lookup when category_id is unknown.",
                default=None,
            ),
        ] = None,
        subcategory_id: Annotated[
            int | None,
            Field(description="Subcategory id (category2Id) for placement lookup.", default=None),
        ] = None,
        subcategory_name: Annotated[
            str | None,
            Field(
                description="Subcategory name for placement lookup when subcategory_id is unknown.",
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    f"Max hits to return (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT}; "
                    f"capped at {MCP_GLOSSARY_TAGS_LIMIT_MAX})."
                ),
                ge=1,
            ),
        ] = MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    ) -> dict[str, Any]:
        """lookup glossary term (see MCP tool description)."""
        return await _invoke_lookup_glossary_term(
            object_id,
            term_name,
            domain_id,
            domain_name,
            category_id,
            category_name,
            subcategory_id,
            subcategory_name,
            limit
        )

    @mcp.tool(description=_DESC_CREATE_GLOSSARY)
    async def create_glossary_term(
        search_on: Annotated[
            str | None,
            Field(
                description=(
                    "Picker mode: oeglobaldomain | category | subcategory. "
                    "Omit when creating a term (term_name set)."
                ),
                default=None,
            ),
        ] = None,
        term_name: Annotated[
            str | None,
            Field(
                description="Term name; required for create. Omit for picker mode.",
                default=None,
            ),
        ] = None,
        domain_id: Annotated[
            int | None,
            Field(
                description="Global domain id (required for create; required for category picker).",
                default=None,
            ),
        ] = None,
        category_id: Annotated[
            int | None,
            Field(
                description=(
                    "Category id for subcategory picker or create (maps to category1Id). "
                    "Required when subcategory_id is set."
                ),
                default=None,
            ),
        ] = None,
        subcategory_id: Annotated[
            int | None,
            Field(
                description="Subcategory id for create (maps to category2Id).",
                default=None,
            ),
        ] = None,
        description: Annotated[
            str | None,
            Field(
                description="Business description (required for create; non-blank).",
                default=None,
            ),
        ] = None,
        definition: Annotated[
            str | None,
            Field(description="Optional formal definition for create.", default=None),
        ] = None,
        domain_name: Annotated[
            str | None,
            Field(
                description="Optional display name for placementPath on create.",
                default=None,
            ),
        ] = None,
        category_name: Annotated[
            str | None,
            Field(
                description="Optional display name for placementPath on create.",
                default=None,
            ),
        ] = None,
        subcategory_name: Annotated[
            str | None,
            Field(
                description="Optional display name for placementPath on create.",
                default=None,
            ),
        ] = None,
        publish: Annotated[
            bool,
            Field(description="When true, term is published; default is draft.", default=False),
        ] = False,
        skip_category: Annotated[
            bool,
            Field(
                description=(
                    "When true with category_skip_confirmed, user skipped category after "
                    "seeing the list; term goes under domain only."
                ),
                default=False,
            ),
        ] = False,
        category_skip_confirmed: Annotated[
            bool,
            Field(
                description=(
                    "Set true only after the user replied skip on the category picker. "
                    "Required with skip_category when categories exist under the domain."
                ),
                default=False,
            ),
        ] = False,
        skip_subcategory: Annotated[
            bool,
            Field(
                description=(
                    "When true, user skipped subcategory placement; term stays under category."
                ),
                default=False,
            ),
        ] = False,
        subcategory_skip_confirmed: Annotated[
            bool,
            Field(
                description=(
                    "Set true only after the user replied skip on the subcategory picker. "
                    "Required with skip_subcategory when subcategories exist."
                ),
                default=False,
            ),
        ] = False,
        size: Annotated[
            int,
            Field(
                description=(
                    f"Picker page size (default {MCP_DOMAIN_METADATA_SIZE_DEFAULT}; "
                    f"max {MCP_DOMAIN_METADATA_SIZE_MAX})."
                ),
                ge=1,
            ),
        ] = MCP_DOMAIN_METADATA_SIZE_DEFAULT,
        page: Annotated[
            int,
            Field(description="Picker page index (0-based).", ge=0),
        ] = 0,
        create_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final create gate: true only after the user explicitly approved "
                    "the confirm_create preview. Re-call with the same term_name, "
                    "domain_id, placement, and description."
                ),
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """create glossary term (see MCP tool description)."""
        return await _invoke_create_glossary_term(
            search_on,
            term_name,
            domain_id,
            category_id,
            subcategory_id,
            description,
            definition,
            domain_name,
            category_name,
            subcategory_name,
            publish,
            skip_category,
            category_skip_confirmed,
            skip_subcategory,
            subcategory_skip_confirmed,
            size,
            page,
            create_confirmed_by_user
        )

    @mcp.tool(description=_DESC_TAGS)
    async def lookup_tags(
        object_id: Annotated[
            int | None,
            Field(description="Tag internal id; omit if using tag_name.", default=None),
        ] = None,
        tag_name: Annotated[
            str | None,
            Field(description="Tag name to look up; omit if using object_id.", default=None),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    f"Max hits to return (default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT}; "
                    f"capped at {MCP_GLOSSARY_TAGS_LIMIT_MAX})."
                ),
                ge=1,
            ),
        ] = MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
        include_parent: Annotated[
            bool,
            Field(
                description=(
                    "When true, enrich each hit with parentTag (immediate parent in "
                    "tagrelationship). Set when the user asks for parent tag details."
                ),
                default=False,
            ),
        ] = False,
        include_children: Annotated[
            bool,
            Field(
                description=(
                    "When true, enrich each hit with childTags. Set when the user asks "
                    "for child tags (e.g. 'What are the child tags of X?')."
                ),
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """lookup tags (see MCP tool description)."""
        return await _invoke_lookup_tags(
            object_id,
            tag_name,
            limit,
            include_parent,
            include_children
        )

    @mcp.tool(description=_DESC_CREATE_TAG)
    async def create_tag(
        tag_name: Annotated[
            str,
            Field(description="Name of the new tag (required)."),
        ],
        description: Annotated[
            str | None,
            Field(
                description=(
                    "Optional wiki/HTML description for the tag. When omitted on the final "
                    "create call, MCP generates a short HTML description from tag_name and "
                    "master/parent names (set OVALEDGE_TAG_AUTO_DESCRIPTION=false to skip)."
                ),
                default=None,
            ),
        ] = None,
        master_tag_id: Annotated[
            int | None,
            Field(
                description=(
                    "SECURE mode only (required after step 1): masterTagId the human chose "
                    "from userSelectableMasters. Never set in OPEN mode. Omit on first call "
                    "(tag_name only)."
                ),
                default=None,
            ),
        ] = None,
        master_tag_id_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Secure mode: must be true when master_tag_id is set, and only after "
                    "the human explicitly selected that id from masterTagChoices."
                ),
                default=False,
            ),
        ] = False,
        parent_tag_id: Annotated[
            int | None,
            Field(
                description=(
                    "Optional. SECURE: parent under the chosen master (from step 2 list). "
                    "OPEN: any parent from userSelectableParents. Omit when creating "
                    "under master only (secure) or with no parent (open)."
                ),
                default=None,
            ),
        ] = None,
        parent_tag_id_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Step 3: true only after the human picked parentTagId from "
                    "userSelectableParents for the chosen master."
                ),
                default=False,
            ),
        ] = False,
        browse_parent_tag_id: Annotated[
            int | None,
            Field(
                description=(
                    "Optional nested browse: list child tags under this parentTagId "
                    "(GET parent-options browseParentTagId). Use when a parent row has "
                    "hasChildren=true to reach deeper levels (e.g. MCPNEWcreated under "
                    "MCPCreated). Keep master_tag_id and master confirmations when set."
                ),
                default=None,
            ),
        ] = None,
        create_directly_under_master: Annotated[
            bool,
            Field(
                description=(
                    "SECURE: create as direct child of masterTagId only (no parentTagId). "
                    "OPEN: create with no parent (do not send masterTagId). Set after user "
                    "sees parent options."
                ),
                default=False,
            ),
        ] = False,
        parent_step_completed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Required on the final create call (open and secure): true only after "
                    "the human was shown userSelectableParents and chose a parent or "
                    "declined. Never set on the first call (tag_name only)."
                ),
                default=False,
            ),
        ] = False,
        create_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final create gate: true only after the user explicitly approved "
                    "the confirm_create preview. Re-call with the same tag_name, "
                    "placement parameters, and optional description."
                ),
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """create tag (see MCP tool description)."""
        return await _invoke_create_tag(
            tag_name,
            description,
            master_tag_id,
            master_tag_id_confirmed_by_user,
            parent_tag_id,
            parent_tag_id_confirmed_by_user,
            browse_parent_tag_id,
            create_directly_under_master,
            parent_step_completed_by_user,
            create_confirmed_by_user
        )

    @mcp.tool(description=_DESC_DATASTORY)
    async def lookup_datastory(
        story_zone_name: Annotated[
            str | None,
            Field(
                description=(
                    "Optional story zone (globaldomain.domain); use with story_name title lookup "
                    "or as a filter with content_query."
                ),
                default=None,
            ),
        ] = None,
        story_name: Annotated[
            str | None,
            Field(
                description=(
                    "Story title for name lookup, or optional filter when using content_query."
                ),
                default=None,
            ),
        ] = None,
        content_query: Annotated[
            str | None,
            Field(
                description=(
                    "Search story body text (narrative and indexed sections). "
                    "Optional story_zone_name and/or story_name narrow results. "
                    "Omit for object_id or title-only lookup."
                ),
                default=None,
            ),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(
                description=(
                    "Story internal object id (numeric identifier); "
                    "omit for other modes."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """lookup datastory (see MCP tool description)."""
        return await _invoke_lookup_datastory(
            story_zone_name,
            story_name,
            content_query,
            object_id
        )

    @mcp.tool(description=_DESC_UPDATE_GOVERNANCE_ROLES)
    async def update_governance_roles(
        object_id: Annotated[
            int,
            Field(
                description=(
                    "Internal object id from search_catalog_assets, lookup_dq_rule, "
                    "lookup_glossary_term, or lookup_tags."
                ),
                ge=1,
            ),
        ],
        object_type: Annotated[
            str,
            Field(
                description=(
                    "OvalEdge objectType: catalog types (oetable, oecolumn, glossary, …) or "
                    "non-catalog governance types (dqrule, dqscheme, dag, policy, …). "
                    "Use lookup_dq_rule for dqrule — not search_catalog_assets."
                ),
            ),
        ],
        role_updates: Annotated[
            dict[str, str | None] | None,
            Field(
                description=(
                    "Map of role -> user identifier. Value is a user (assign/update) or null "
                    "(remove). Keys: owner, steward, custodian, governance_role_4/5/6."
                ),
                default=None,
            ),
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
        dry_run: Annotated[
            bool | None,
            Field(description="If true, validate only; do not persist.", default=None),
        ] = None,
        idempotency_key: Annotated[
            str | None,
            Field(description="Optional client key to dedupe retries.", default=None),
        ] = None,
        create_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final update gate: true only after the user explicitly approved "
                    "the confirm_update preview. Re-call with the same object_id, "
                    "object_type, role_updates, and clientContext."
                ),
                default=False,
            ),
        ] = False,
    ) -> dict[str, Any]:
        """update governance roles (see MCP tool description)."""
        return await _invoke_update_governance_roles(
            object_id,
            object_type,
            role_updates,
            prompt,
            reason,
            dry_run,
            idempotency_key,
            create_confirmed_by_user
        )

    @mcp.tool(description=_DESC_UPDATE_CUSTOM_FIELD_VALUE, name=TOOL_UPDATE_CUSTOM_FIELD_VALUE)
    async def update_custom_field_value(
        object_id: Annotated[
            int,
            Field(
                description=(
                    "Internal object id from search_catalog_assets or governance lookups."
                ),
                ge=1,
            ),
        ],
        object_type: Annotated[
            str,
            Field(
                description=(
                    "OvalEdge objectType for custom fields "
                    f"(e.g. {', '.join(sorted(MCP_CUSTOM_FIELD_OBJECT_TYPES))})."
                ),
            ),
        ],
        field_updates: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Fields to update. Each item: {field_name, value} or "
                    "{field_key, value}. Supports multi-field in one call."
                ),
            ),
        ],
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
        time_zone: Annotated[
            str | None,
            Field(
                description=(
                    "IANA time zone for date custom fields (e.g. Asia/Kolkata). "
                    "Defaults to OVALEDGE_CLIENT_TIMEZONE or host zone so dates match the UI."
                ),
                default=None,
            ),
        ] = None,
        create_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final update gate: true only after the user explicitly approved "
                    "the confirm_update preview."
                ),
                default=False,
            ),
        ] = False,
        code_update_mode: Annotated[
            str | None,
            Field(
                description=(
                    "For multi-select code fields with multiple values: replace_all, add, "
                    "or remove. Omit for single values or until the user chooses a mode."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """update custom field value (see MCP tool description)."""
        return await _invoke_update_custom_field_value(
            object_id,
            object_type,
            field_updates,
            prompt,
            reason,
            dry_run,
            fail_on_blocked_field,
            idempotency_key,
            time_zone,
            create_confirmed_by_user,
            code_update_mode,
        )
