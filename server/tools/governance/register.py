"""MCP tool registration for governance workflows."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.constants import (
    MCP_CUSTOM_FIELD_OBJECT_TYPES,
    MCP_DOMAIN_METADATA_SIZE_DEFAULT,
    MCP_DOMAIN_METADATA_SIZE_MAX,
    TOOL_UPDATE_CUSTOM_FIELD_VALUE,
)
from server.tools.common.confirm_gate import CONFIRMATION_TOKEN_PARAM_DESCRIPTION
from server.tools.governance.helpers import (
    _DESC_CREATE_GLOSSARY,
    _DESC_CREATE_TAG,
    _DESC_UPDATE_CUSTOM_FIELD_VALUE,
    _DESC_UPDATE_GOVERNANCE_ROLES,
)
from server.tools.governance.invocations import (
    _invoke_create_glossary_term,
    _invoke_create_tag,
    _invoke_update_custom_field_value,
    _invoke_update_governance_roles,
)


def register(mcp: FastMCP) -> None:

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
        write_confirmed_by_user: Annotated[
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
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """create glossary term (see MCP tool description)."""
        return await _invoke_create_glossary_term(
            search_on=search_on,
            term_name=term_name,
            domain_id=domain_id,
            category_id=category_id,
            subcategory_id=subcategory_id,
            description=description,
            definition=definition,
            domain_name=domain_name,
            category_name=category_name,
            subcategory_name=subcategory_name,
            publish=publish,
            skip_category=skip_category,
            category_skip_confirmed=category_skip_confirmed,
            skip_subcategory=skip_subcategory,
            subcategory_skip_confirmed=subcategory_skip_confirmed,
            size=size,
            page=page,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
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
        write_confirmed_by_user: Annotated[
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
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """create tag (see MCP tool description)."""
        return await _invoke_create_tag(
            tag_name=tag_name,
            description=description,
            master_tag_id=master_tag_id,
            master_tag_id_confirmed_by_user=master_tag_id_confirmed_by_user,
            parent_tag_id=parent_tag_id,
            parent_tag_id_confirmed_by_user=parent_tag_id_confirmed_by_user,
            browse_parent_tag_id=browse_parent_tag_id,
            create_directly_under_master=create_directly_under_master,
            parent_step_completed_by_user=parent_step_completed_by_user,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )

    @mcp.tool(description=_DESC_UPDATE_GOVERNANCE_ROLES)
    async def update_governance_roles(
        object_id: Annotated[
            int,
            Field(
                description=(
                    "Internal object id from asset_explorer or lookup_dq_rule."
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
                    "Use lookup_dq_rule for dqrule — not asset_explorer."
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
        write_confirmed_by_user: Annotated[
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
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """update governance roles (see MCP tool description)."""
        return await _invoke_update_governance_roles(
            object_id=object_id,
            object_type=object_type,
            role_updates=role_updates,
            prompt=prompt,
            reason=reason,
            dry_run=dry_run,
            idempotency_key=idempotency_key,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )

    @mcp.tool(description=_DESC_UPDATE_CUSTOM_FIELD_VALUE, name=TOOL_UPDATE_CUSTOM_FIELD_VALUE)
    async def update_custom_field_value(
        object_id: Annotated[
            int,
            Field(
                description=(
                    "Internal object id from asset_explorer or governance lookups."
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
        write_confirmed_by_user: Annotated[
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
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """update custom field value (see MCP tool description)."""
        return await _invoke_update_custom_field_value(
            object_id=object_id,
            object_type=object_type,
            field_updates=field_updates,
            prompt=prompt,
            reason=reason,
            dry_run=dry_run,
            fail_on_blocked_field=fail_on_blocked_field,
            idempotency_key=idempotency_key,
            time_zone=time_zone,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
            code_update_mode=code_update_mode,
        )
