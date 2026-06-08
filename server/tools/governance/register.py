"""MCP tool registration for governance workflows."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_DOMAIN_METADATA_SEARCH_ON,
    MCP_DOMAIN_METADATA_SIZE_DEFAULT,
    MCP_DOMAIN_METADATA_SIZE_MAX,
    MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC,
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    MCP_DQ_ASSESS_LIMIT_MAX,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES,
    MCP_PATH_ASSESS_CDE_DQ,
    MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS,
    MCP_PATH_CREATE_DQ_RULES,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_LOOKUP_DATASTORY,
    MCP_PATH_LOOKUP_DQ_RULES,
    MCP_PATH_TAGS,
    MCP_PATH_UPDATE_GOVERNANCE_ROLES,
)
from server.tools.common import (
    as_dict as _as_dict,
)
from server.tools.common import (
    blank as _blank,
)
from server.tools.common import (
    drop_none as _q,
)
from server.tools.common import (
    map_ovaledge_error,
    ovaledge_client,
    strip_or_none,
)
from server.tools.governance.helpers import (
    _DESC_ASSESS_CDE_DQ,
    _DESC_ASSOCIATE_DQ_RULE_OBJECTS,
    _DESC_CREATE_DQ_RULES,
    _DESC_CREATE_GLOSSARY,
    _DESC_CREATE_TAG,
    _DESC_DATASTORY,
    _DESC_GLOSSARY,
    _DESC_LOOKUP_DQ_RULE,
    _DESC_TAGS,
    _DESC_UPDATE_GOVERNANCE_ROLES,
    _block_llm_master_selection,
    _block_llm_parent_selection,
    _consume_parent_picker_shown,
    _enrich_create_tag_response,
    _enrich_datastory_response,
    _enrich_update_governance_roles_response,
    _extract_picker_items,
    _extract_placement_from_path,
    _fetch_domain_metadata,
    _fetch_open_parent_choices,
    _fetch_parent_choices_for_master,
    _fetch_tag_create_context,
    _format_create_tag_input_required,
    _format_glossary_create_confirmation_preview,
    _format_open_parent_selection_guidance,
    _format_parent_selection_guidance,
    _format_placement_options,
    _format_tag_create_confirmation_preview,
    _format_update_governance_roles_confirmation_preview,
    _load_secure_create_guidance,
    _lookup_tag_after_create,
    _master_tag_ids_from_guidance_data,
    _normalize_role_updates,
    _parent_choice_finalized,
    _parent_picker_was_shown,
    _reject_invented_master_tag_id,
    _resolve_category_id_by_name,
    _resolve_create_tag_description,
    _resolve_domain_id_by_name,
    _resolve_tag_hierarchy_names_for_create,
    _shape_create_response,
    _shape_picker_response,
    build_assess_cde_dq_payload,
    build_associate_dq_rule_objects_payload,
    build_create_dq_rules_payload,
    format_associate_dq_rule_objects_response,
    validate_assess_cde_dq_args,
    validate_associate_dq_rule_objects_args,
    validate_create_dq_rules_args,
)


def register(mcp: FastMCP) -> None:

    @mcp.tool(description=_DESC_GLOSSARY)
    async def lookup_glossary_term(
        object_id: Annotated[
            int | None,
            Field(description="Glossary term internal id; omit if using term_name.", default=None),
        ] = None,
        term_name: Annotated[
            str | None,
            Field(
                description="Term name / label to look up; omit if using object_id.",
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
        """Glossary lookup (see MCP tool description)."""
        has_id = object_id is not None
        has_name = term_name is not None and str(term_name).strip() != ""
        if has_id and has_name:
            return {
                "error": "Provide either object_id or term_name — not both.",
                "status_code": 400,
            }
        if not has_id and not has_name:
            return {
                "error": "Provide object_id or term_name.",
                "status_code": 400,
            }
        lim = min(max(limit, 1), MCP_GLOSSARY_TAGS_LIMIT_MAX)
        try:
            async with ovaledge_client() as client:
                return await client.get(
                    MCP_PATH_GLOSSARY_TERMS,
                    params=_q(objectId=object_id, termName=term_name, limit=lim),
                )
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

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
        """Create glossary term or list placement options (see MCP tool description)."""
        has_term = not _blank(term_name)
        has_search = not _blank(search_on)
        if has_term and has_search:
            return {
                "error": "Provide either search_on (picker) or term_name (create) — not both.",
                "status_code": 400,
            }
        if not has_term and not has_search:
            return {
                "error": "Provide search_on for placement picker or term_name to create a term.",
                "status_code": 400,
            }

        dom_early = domain_id or 0
        (
            effective_domain_name,
            effective_category_from_path,
            effective_subcategory_from_path,
        ) = _extract_placement_from_path(
            domain_name, category_name, subcategory_name
        )
        if effective_category_from_path and _blank(category_name):
            category_name = effective_category_from_path
        if effective_subcategory_from_path and _blank(subcategory_name):
            subcategory_name = effective_subcategory_from_path
        domain_name = effective_domain_name
        if has_term and not has_search and dom_early <= 0:
            try:
                async with ovaledge_client() as client:
                    body = await _fetch_domain_metadata(
                        client,
                        "oeglobaldomain",
                        page=page,
                        size=size,
                        domain_id=0,
                        category_id=0,
                    )
                    if effective_domain_name:
                        data = _as_dict(body.get("data"))
                        items = _extract_picker_items(data, "oeglobaldomain")
                        resolved_id, resolved_name, match_count = _resolve_domain_id_by_name(
                            items, effective_domain_name
                        )
                        if resolved_id:
                            dom_early = resolved_id
                            effective_domain_name = resolved_name or effective_domain_name
                        elif match_count > 1:
                            shaped = _shape_picker_response(
                                body,
                                "oeglobaldomain",
                                pending_term_name=str(term_name).strip(),
                                pending_description=(
                                    str(description).strip() if not _blank(description) else None
                                ),
                            )
                            shaped["domainNameMatch"] = "ambiguous"
                            shaped["requestedDomainName"] = effective_domain_name
                            shaped["agentInstruction"] = (
                                "Multiple domains match the provided domain_name. "
                                "Show formattedResponse and ask the user to reply with domain_id."
                            )
                            return shaped
                        else:
                            shaped = _shape_picker_response(
                                body,
                                "oeglobaldomain",
                                pending_term_name=str(term_name).strip(),
                                pending_description=(
                                    str(description).strip() if not _blank(description) else None
                                ),
                            )
                            shaped["domainNameMatch"] = "not_found"
                            shaped["requestedDomainName"] = effective_domain_name
                            shaped["agentInstruction"] = (
                                "No exact domain name match was found. "
                                "Show formattedResponse and ask the user to choose domain_id."
                            )
                            return shaped
                    if dom_early > 0:
                        domain_id = dom_early
                        domain_name = effective_domain_name
                    else:
                        pending_desc = str(description).strip() if not _blank(description) else None
                        return _shape_picker_response(
                            body,
                            "oeglobaldomain",
                            pending_term_name=str(term_name).strip(),
                            pending_description=pending_desc,
                        )
            except OvalEdgeError as e:
                return map_ovaledge_error(e)

        if has_search:
            mode = str(search_on).strip().lower()
            if mode not in MCP_DOMAIN_METADATA_SEARCH_ON:
                allowed = ", ".join(sorted(MCP_DOMAIN_METADATA_SEARCH_ON))
                return {
                    "error": f"search_on must be one of: {allowed}.",
                    "status_code": 400,
                }
            dom = domain_id or 0
            cat = category_id or 0
            if mode == "category" and dom <= 0:
                return {
                    "error": "domain_id > 0 is required when search_on=category.",
                    "status_code": 400,
                }
            if mode == "subcategory" and cat <= 0:
                return {
                    "error": "category_id > 0 is required when search_on=subcategory.",
                    "status_code": 400,
                }
            try:
                async with ovaledge_client() as client:
                    body = await _fetch_domain_metadata(
                        client,
                        mode,
                        page=page,
                        size=size,
                        domain_id=dom,
                        category_id=cat,
                    )
                    pending_desc = (
                        str(description).strip()
                        if has_term and not _blank(description)
                        else None
                    )
                    pending = str(term_name).strip() if has_term else None
                    return _shape_picker_response(
                        body,
                        mode,
                        pending_term_name=pending,
                        pending_description=pending_desc,
                        domain_id=dom if dom > 0 else None,
                        domain_name=domain_name,
                        category_id=cat if cat > 0 else None,
                        category_name=category_name,
                    )
            except OvalEdgeError as e:
                return map_ovaledge_error(e)

        dom_create = domain_id or 0
        cat_create = category_id or 0
        sub_create = subcategory_id or 0
        pending_name = str(term_name).strip()
        pending_desc = str(description).strip() if not _blank(description) else None
        effective_category_name = (
            str(category_name).strip()
            if isinstance(category_name, str) and not _blank(category_name)
            else None
        )
        effective_subcategory_name = (
            str(subcategory_name).strip()
            if isinstance(subcategory_name, str) and not _blank(subcategory_name)
            else None
        )
        no_categories_in_domain = False
        no_categories_in_skip_preview = False

        if sub_create > 0 and cat_create <= 0:
            return {
                "error": "category_id is required when subcategory_id is set.",
                "status_code": 400,
            }

        category_skip_ok = skip_category and category_skip_confirmed
        if dom_create > 0 and cat_create <= 0 and not category_skip_ok:
            try:
                async with ovaledge_client() as client:
                    body = await _fetch_domain_metadata(
                        client,
                        "category",
                        page=page,
                        size=size,
                        domain_id=dom_create,
                        category_id=0,
                    )
                    data = _as_dict(body.get("data"))
                    category_items = _extract_picker_items(data, "category")
                    if category_items:
                        if cat_create <= 0 and effective_category_name:
                            (
                                resolved_category_id,
                                resolved_category_name,
                                category_match_count,
                            ) = _resolve_category_id_by_name(
                                category_items, effective_category_name
                            )
                            if resolved_category_id:
                                cat_create = resolved_category_id
                                category_name = (
                                    resolved_category_name or effective_category_name
                                )
                            elif category_match_count > 1:
                                shaped = _shape_picker_response(
                                    body,
                                    "category",
                                    pending_term_name=pending_name,
                                    pending_description=pending_desc,
                                    domain_id=dom_create,
                                    domain_name=domain_name,
                                )
                                shaped["categoryNameMatch"] = "ambiguous"
                                shaped["requestedCategoryName"] = effective_category_name
                                shaped["agentInstruction"] = (
                                    "Multiple categories match the provided "
                                    "category_name. Show formattedResponse "
                                    "and ask the user to reply with "
                                    "category_id."
                                )
                                return shaped
                            else:
                                shaped = _shape_picker_response(
                                    body,
                                    "category",
                                    pending_term_name=pending_name,
                                    pending_description=pending_desc,
                                    domain_id=dom_create,
                                    domain_name=domain_name,
                                )
                                shaped["categoryNameMatch"] = "not_found"
                                shaped["requestedCategoryName"] = effective_category_name
                                shaped["agentInstruction"] = (
                                    "No exact category name match was found "
                                    "under the selected domain. Show "
                                    "formattedResponse and ask the user to "
                                    "choose category_id."
                                )
                                return shaped
                        if cat_create > 0:
                            # category_name was provided and resolved; continue to subcategory step.
                            pass
                        else:
                            return _shape_picker_response(
                                body,
                                "category",
                                pending_term_name=pending_name,
                                pending_description=pending_desc,
                                domain_id=dom_create,
                                domain_name=domain_name,
                            )
                    no_categories_in_domain = True
            except OvalEdgeError as e:
                return map_ovaledge_error(e)

        if (
            dom_create > 0
            and cat_create > 0
            and not (skip_subcategory and subcategory_skip_confirmed)
            and sub_create <= 0
        ):
            try:
                async with ovaledge_client() as client:
                    body = await _fetch_domain_metadata(
                        client,
                        "subcategory",
                        page=page,
                        size=size,
                        domain_id=dom_create,
                        category_id=cat_create,
                    )
                    data = _as_dict(body.get("data"))
                    subcategory_items = _extract_picker_items(data, "subcategory")
                    if subcategory_items:
                        if effective_subcategory_name and sub_create <= 0:
                            # Resolve subcategory by provided name and skip picker when unique.
                            (
                                resolved_subcategory_id,
                                resolved_subcategory_name,
                                sub_match_count,
                            ) = _resolve_category_id_by_name(
                                [
                                    {
                                        "categoryId": x.get("subCategoryId"),
                                        "categoryName": x.get("subCategoryName"),
                                    }
                                    for x in subcategory_items
                                ],
                                effective_subcategory_name,
                            )
                            if resolved_subcategory_id:
                                sub_create = resolved_subcategory_id
                                subcategory_name = (
                                    resolved_subcategory_name or effective_subcategory_name
                                )
                            elif sub_match_count > 1:
                                shaped = _shape_picker_response(
                                    body,
                                    "subcategory",
                                    pending_term_name=pending_name,
                                    pending_description=pending_desc,
                                    domain_id=dom_create,
                                    domain_name=domain_name,
                                    category_id=cat_create,
                                    category_name=category_name,
                                )
                                shaped["subcategoryNameMatch"] = "ambiguous"
                                shaped["requestedSubcategoryName"] = effective_subcategory_name
                                shaped["agentInstruction"] = (
                                    "Multiple subcategories match the "
                                    "provided subcategory_name. Show "
                                    "formattedResponse and ask the user to "
                                    "reply with subcategory_id."
                                )
                                return shaped
                            else:
                                shaped = _shape_picker_response(
                                    body,
                                    "subcategory",
                                    pending_term_name=pending_name,
                                    pending_description=pending_desc,
                                    domain_id=dom_create,
                                    domain_name=domain_name,
                                    category_id=cat_create,
                                    category_name=category_name,
                                )
                                shaped["subcategoryNameMatch"] = "not_found"
                                shaped["requestedSubcategoryName"] = effective_subcategory_name
                                shaped["agentInstruction"] = (
                                    "No exact subcategory name match was "
                                    "found under the selected category. Show "
                                    "formattedResponse and ask the user to "
                                    "choose subcategory_id."
                                )
                                return shaped
                        if sub_create > 0:
                            pass
                        else:
                            return _shape_picker_response(
                                body,
                                "subcategory",
                                pending_term_name=pending_name,
                                pending_description=pending_desc,
                                domain_id=dom_create,
                                domain_name=domain_name,
                                category_id=cat_create,
                                category_name=category_name,
                            )
            except OvalEdgeError as e:
                return map_ovaledge_error(e)

        skip_category_preview_items: list[dict[str, Any]] = []
        skip_subcategory_preview_items: list[dict[str, Any]] = []

        if _blank(description):
            if category_skip_ok and dom_create > 0 and cat_create <= 0:
                try:
                    async with ovaledge_client() as client:
                        body = await _fetch_domain_metadata(
                            client,
                            "category",
                            page=page,
                            size=size,
                            domain_id=dom_create,
                            category_id=0,
                        )
                        data = _as_dict(body.get("data"))
                        skip_category_preview_items = _extract_picker_items(data, "category")
                        if not skip_category_preview_items:
                            no_categories_in_skip_preview = True
                except OvalEdgeError as e:
                    return map_ovaledge_error(e)

            if (
                dom_create > 0
                and cat_create > 0
                and (skip_subcategory and subcategory_skip_confirmed)
                and sub_create <= 0
            ):
                try:
                    async with ovaledge_client() as client:
                        body = await _fetch_domain_metadata(
                            client,
                            "subcategory",
                            page=page,
                            size=size,
                            domain_id=dom_create,
                            category_id=cat_create,
                        )
                        data = _as_dict(body.get("data"))
                        skip_subcategory_preview_items = _extract_picker_items(
                            data, "subcategory"
                        )
                except OvalEdgeError as e:
                    return map_ovaledge_error(e)

            dom_label = domain_name or f"domain_id {dom_create}"
            placement = dom_label
            if cat_create > 0:
                cat_label = category_name or f"category_id {cat_create}"
                placement = f"{placement} > {cat_label}"
            if sub_create > 0:
                sub_label = subcategory_name or f"subcategory_id {sub_create}"
                placement = f"{placement} > {sub_label}"

            cat_preview = (
                "Available categories under this domain (you requested to skip):\n"
                f"{_format_placement_options('category', skip_category_preview_items)}\n\n"
                if skip_category_preview_items
                else ""
            )
            subcat_preview = (
                "Available subcategories under this category (you requested to skip):\n"
                f"{_format_placement_options('subcategory', skip_subcategory_preview_items)}\n\n"
                if skip_subcategory_preview_items
                else ""
            )

            out = {
                "ok": False,
                "awaitingUserInput": True,
                "workflowPhase": "collect_description",
                "formattedResponse": (
                    f'**Create glossary term: {pending_name}**\n\n'
                    + (
                        "No categories are available under the selected domain. "
                        "The term will be created directly under the domain.\n\n"
                        if (no_categories_in_domain or no_categories_in_skip_preview)
                        else ""
                    )
                    + (
                        "Categories are available under the selected domain.\n\n"
                        if skip_category_preview_items
                        else ""
                    )
                    + f"{cat_preview}"
                    + f"{subcat_preview}"
                    + f"Placement **{placement}** is set. A business **description** is "
                    + "required before the term can be created. Ask the user for a description, "
                    + "then call again with `term_name`, `domain_id`, `description`, and the same "
                    + "placement ids (or skip flags)."
                ),
                "pendingTermName": pending_name,
                "pendingDomainId": dom_create,
                "pendingCategoryId": cat_create if cat_create > 0 else None,
                "pendingSubcategoryId": sub_create if sub_create > 0 else None,
                "hasCategoriesInDomain": (
                    False
                    if (no_categories_in_domain or no_categories_in_skip_preview)
                    else (True if skip_category_preview_items else None)
                ),
                "categoryAvailabilityMessage": (
                    "No categories are available under the selected domain."
                    if (no_categories_in_domain or no_categories_in_skip_preview)
                    else (
                        "Categories are available under the selected domain."
                        if skip_category_preview_items
                        else None
                    )
                ),
                "agentInstruction": (
                    "Show categoryAvailabilityMessage to the user when provided. "
                    "Ask the user for a description; do not invent one. "
                    "Re-call with description and the same placement."
                ),
                "status_code": 400,
            }
            if skip_category_preview_items:
                out["placementOptions"] = skip_category_preview_items
                out["formattedPlacementOptions"] = _format_placement_options(
                    "category", skip_category_preview_items
                )
            elif skip_subcategory_preview_items:
                out["placementOptions"] = skip_subcategory_preview_items
                out["formattedPlacementOptions"] = _format_placement_options(
                    "subcategory", skip_subcategory_preview_items
                )
            return out
        glossary_placement_note = (
            "No categories are available under this domain; "
            "created directly under domain."
            if no_categories_in_domain and cat_create <= 0
            else None
        )
        if not create_confirmed_by_user:
            return _format_glossary_create_confirmation_preview(
                term_name=pending_name,
                domain_id=dom_create,
                domain_name=domain_name,
                category_id=cat_create if cat_create > 0 else None,
                category_name=category_name,
                subcategory_id=sub_create if sub_create > 0 else None,
                subcategory_name=subcategory_name,
                description=str(description).strip(),
                definition=definition,
                publish=publish,
                placement_note=glossary_placement_note,
            )
        post_body: dict[str, object] = {
            "termName": str(term_name).strip(),
            "domainId": dom_create,
            "description": str(description).strip(),
            "category1Id": cat_create,
            "category2Id": sub_create,
            "publish": publish,
        }
        if not _blank(definition):
            post_body["definition"] = str(definition).strip()
        try:
            async with ovaledge_client() as client:
                body = await client.post(MCP_PATH_GLOSSARY_TERMS, body=post_body)
                if isinstance(body, dict):
                    return _shape_create_response(
                        body,
                        term_name=str(term_name).strip(),
                        domain_id=dom_create,
                        domain_name=domain_name,
                        category_id=cat_create if cat_create > 0 else None,
                        category_name=category_name,
                        subcategory_id=sub_create if sub_create > 0 else None,
                        subcategory_name=subcategory_name,
                        placement_note=glossary_placement_note,
                    )
                return body
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

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
    ) -> dict[str, Any]:
        """Tag lookup (see MCP tool description)."""
        has_id = object_id is not None
        has_name = tag_name is not None and str(tag_name).strip() != ""
        if has_id and has_name:
            return {
                "error": "Provide either object_id or tag_name — not both.",
                "status_code": 400,
            }
        if not has_id and not has_name:
            return {
                "error": "Provide object_id or tag_name.",
                "status_code": 400,
            }
        lim = min(max(limit, 1), MCP_GLOSSARY_TAGS_LIMIT_MAX)
        try:
            async with ovaledge_client() as client:
                return await client.get(
                    MCP_PATH_TAGS,
                    params=_q(objectId=object_id, tagName=tag_name, limit=lim),
                )
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

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
        """Create tag (see MCP tool description)."""
        name = tag_name.strip() if tag_name is not None else ""
        if not name:
            return {
                "error": "tag_name is required.",
                "status_code": 400,
            }
        try:
            async with ovaledge_client() as client:
                secure_mode, valid_master_ids = await _fetch_tag_create_context(client)
                secure_guidance: dict[str, Any] | None = None
                if secure_mode:
                    secure_guidance = await _load_secure_create_guidance(client)
                    if master_tag_id is None or master_tag_id <= 0:
                        if secure_guidance is not None:
                            return secure_guidance
                        return {
                            "ok": False,
                            "status_code": 422,
                            "message": "Secure mode requires a human-selected master tag.",
                            "userMustSelectMasterTag": True,
                            "awaitingUserSelection": True,
                            "doNotCreateTag": True,
                        }
                    if not master_tag_id_confirmed_by_user:
                        return _block_llm_master_selection(
                            secure_guidance,
                            master_tag_id=master_tag_id,
                        )
                    if not valid_master_ids or master_tag_id not in valid_master_ids:
                        return _reject_invented_master_tag_id(
                            master_tag_id,
                            valid_master_ids,
                            secure_guidance,
                        )
                    if parent_tag_id is not None and parent_tag_id > 0:
                        if not parent_tag_id_confirmed_by_user:
                            return _block_llm_parent_selection(
                                secure_guidance,
                                parent_tag_id=parent_tag_id,
                            )
                        # Validate via parent-options API (not nested create-options
                        # parentTagChoices, which are intentionally empty in secure mode).
                        _, parents_for_validate = await _fetch_parent_choices_for_master(
                            client, master_tag_id, secure_guidance
                        )
                        allowed_parents = {
                            p["parentTagId"] for p in parents_for_validate
                        }
                        if allowed_parents and parent_tag_id not in allowed_parents:
                            return {
                                "ok": False,
                                "status_code": 422,
                                "message": (
                                    f"parent_tag_id {parent_tag_id} is not under "
                                    f"master_tag_id {master_tag_id}."
                                ),
                                "doNotCreateTag": True,
                                "formattedResponse": (
                                    f"parent_tag_id {parent_tag_id} is not listed under "
                                    f"master_tag_id {master_tag_id}. Ask the human to pick "
                                    "from userSelectableParents or decline with "
                                    "create_directly_under_master=true and "
                                    "parent_step_completed_by_user=true."
                                ),
                            }
                    if not _parent_choice_finalized(
                        secure_mode=True,
                        parent_tag_id=parent_tag_id,
                        parent_tag_id_confirmed_by_user=parent_tag_id_confirmed_by_user,
                        create_directly_under_master=create_directly_under_master,
                        parent_step_completed_by_user=parent_step_completed_by_user,
                    ):
                        master_name, parents = await _fetch_parent_choices_for_master(
                            client, master_tag_id, secure_guidance
                        )
                        return _format_parent_selection_guidance(
                            master_tag_id=master_tag_id,
                            master_tag_name=master_name,
                            parents=parents,
                            tag_name=name,
                        )
                    if not _parent_picker_was_shown(name):
                        master_name, parents = await _fetch_parent_choices_for_master(
                            client, master_tag_id, secure_guidance
                        )
                        out = _format_parent_selection_guidance(
                            master_tag_id=master_tag_id,
                            master_tag_name=master_name,
                            parents=parents,
                            tag_name=name,
                        )
                        out["message"] = (
                            "Parent picker was not completed for this tag name. "
                            "Present userSelectableParents to the user first, then "
                            "retry with parent_step_completed_by_user=true and their choice."
                        )
                        return out

                else:
                    # OPEN mode: never run master-tag step; only optional parent list.
                    if master_tag_id is not None and master_tag_id > 0:
                        return {
                            "ok": False,
                            "status_code": 422,
                            "message": (
                                "OPEN mode does not use master_tag_id. Show "
                                "userSelectableParents only, or create without parent."
                            ),
                            "tagSecurityMode": "open",
                            "doNotCreateTag": True,
                            "formattedResponse": (
                                "OPEN mode: do not set master_tag_id. Call with tag_name only "
                                "first to see parent options, then create with optional "
                                "parent_tag_id or create_directly_under_master=true."
                            ),
                        }
                    open_parents: list[dict[str, Any]] = []
                    if parent_tag_id is not None and parent_tag_id > 0:
                        if not parent_tag_id_confirmed_by_user:
                            open_parents = await _fetch_open_parent_choices(client)
                            guidance = _format_open_parent_selection_guidance(
                                parents=open_parents,
                                tag_name=name,
                            )
                            return _block_llm_parent_selection(
                                guidance,
                                parent_tag_id=parent_tag_id,
                            )
                        open_parents = await _fetch_open_parent_choices(client)
                        allowed_open = {
                            p["parentTagId"] for p in open_parents
                        }
                        if allowed_open and parent_tag_id not in allowed_open:
                            return {
                                "ok": False,
                                "status_code": 422,
                                "message": (
                                    f"parent_tag_id {parent_tag_id} is not in "
                                    "userSelectableParents."
                                ),
                                "doNotCreateTag": True,
                                "tagSecurityMode": "open",
                                "userSelectableParents": open_parents,
                                "formattedResponse": (
                                    f"parent_tag_id {parent_tag_id} is not listed in "
                                    "userSelectableParents. Ask the human to pick from the "
                                    "suggested list or create_directly_under_master=true "
                                    "(no parent, open mode)."
                                ),
                            }
                    if not _parent_choice_finalized(
                        secure_mode=False,
                        parent_tag_id=parent_tag_id,
                        parent_tag_id_confirmed_by_user=parent_tag_id_confirmed_by_user,
                        create_directly_under_master=create_directly_under_master,
                        parent_step_completed_by_user=parent_step_completed_by_user,
                    ):
                        open_parents = await _fetch_open_parent_choices(client)
                        return _format_open_parent_selection_guidance(
                            parents=open_parents,
                            tag_name=name,
                        )
                    if not _parent_picker_was_shown(name):
                        open_parents = await _fetch_open_parent_choices(client)
                        out = _format_open_parent_selection_guidance(
                            parents=open_parents,
                            tag_name=name,
                        )
                        out["message"] = (
                            "Parent picker was not completed for this tag name. "
                            "Present userSelectableParents to the user first, then "
                            "retry with parent_step_completed_by_user=true and their choice."
                        )
                        return out

                master_name_for_desc, parent_name_for_desc = (
                    await _resolve_tag_hierarchy_names_for_create(
                        client,
                        secure_mode=secure_mode,
                        master_tag_id=master_tag_id,
                        parent_tag_id=parent_tag_id,
                        secure_guidance=secure_guidance,
                    )
                )
                if not create_confirmed_by_user:
                    return _format_tag_create_confirmation_preview(
                        tag_name=name,
                        description=description,
                        secure_mode=secure_mode,
                        master_tag_id=master_tag_id,
                        master_tag_name=master_name_for_desc,
                        parent_tag_id=parent_tag_id,
                        parent_tag_name=parent_name_for_desc,
                        create_directly_under_master=create_directly_under_master,
                    )
                if not _consume_parent_picker_shown(name):
                    if secure_mode:
                        if master_tag_id is None or master_tag_id <= 0:
                            return {
                                "ok": False,
                                "status_code": 422,
                                "message": (
                                    "Secure mode requires master_tag_id for parent "
                                    "picker replay."
                                ),
                                "doNotCreateTag": True,
                            }
                        resolved_master_id = master_tag_id
                        master_name, parents = await _fetch_parent_choices_for_master(
                            client, resolved_master_id, secure_guidance
                        )
                        out = _format_parent_selection_guidance(
                            master_tag_id=resolved_master_id,
                            master_tag_name=master_name,
                            parents=parents,
                            tag_name=name,
                        )
                    else:
                        open_parents = await _fetch_open_parent_choices(client)
                        out = _format_open_parent_selection_guidance(
                            parents=open_parents,
                            tag_name=name,
                        )
                    out["message"] = (
                        "Parent picker session expired or was not completed. "
                        "Present userSelectableParents again, then retry with "
                        "parent_step_completed_by_user=true and create_confirmed_by_user=true."
                    )
                    return out
                body = _q(
                    tagName=name,
                    description=_resolve_create_tag_description(
                        name,
                        description,
                        master_tag_name=master_name_for_desc,
                        parent_tag_name=parent_name_for_desc,
                    ),
                    masterTagId=(
                        master_tag_id
                        if secure_mode
                        and master_tag_id is not None
                        and master_tag_id > 0
                        else None
                    ),
                    parentTagId=(
                        parent_tag_id if parent_tag_id is not None and parent_tag_id > 0 else None
                    ),
                )
                created = await client.post(MCP_PATH_TAGS, body=body)
                if not isinstance(created, dict) or not created.get("ok"):
                    return created
                data = created.get("data")
                tag_id: int | None = None
                if isinstance(data, dict):
                    raw_id = data.get("tagId")
                    if isinstance(raw_id, int) and raw_id > 0:
                        tag_id = raw_id
                lookup_body: dict[str, Any] | None = None
                if tag_id is not None:
                    lookup_body = await _lookup_tag_after_create(client, tag_id)
                desc_val = body.get("description")
                create_desc = desc_val if isinstance(desc_val, str) else None
                return _enrich_create_tag_response(
                    created,
                    description=create_desc,
                    master_tag_id=master_tag_id,
                    parent_tag_id=parent_tag_id,
                    lookup_body=lookup_body,
                )
        except OvalEdgeError as e:
            if e.status_code == 422 and isinstance(e.body.get("data"), dict):
                guidance = _format_create_tag_input_required(e)
                if master_tag_id is not None and master_tag_id > 0:
                    valid = _master_tag_ids_from_guidance_data(e.body["data"])
                    if valid and master_tag_id not in valid:
                        return _reject_invented_master_tag_id(
                            master_tag_id, valid, guidance
                        )
                return guidance
            return map_ovaledge_error(e)

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
        """Data story lookup (see MCP tool description)."""
        has_id = object_id is not None and object_id > 0
        has_name = story_name is not None and str(story_name).strip() != ""
        has_content = content_query is not None and str(content_query).strip() != ""
        if has_id and (has_name or has_content):
            return {
                "error": "Provide object_id alone, or use story_name and/or content_query.",
                "status_code": 400,
            }
        if not has_id and not has_name and not has_content:
            return {
                "error": "Provide object_id, story_name, or content_query.",
                "status_code": 400,
            }
        zone_param = strip_or_none(story_zone_name)
        name_for_api = strip_or_none(story_name)
        content_param = strip_or_none(content_query)
        try:
            async with ovaledge_client() as client:
                body = await client.get(
                    MCP_PATH_LOOKUP_DATASTORY,
                    params=_q(
                        storyZoneName=zone_param,
                        storyName=name_for_api,
                        contentQuery=content_param,
                        objectId=object_id if has_id else None,
                    ),
                )
                if isinstance(body, dict):
                    return _enrich_datastory_response(body)
                return body
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

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
        """
        Update governance responsibilities (see MCP tool description).

        Validation of RBAC, propagated-role restrictions, approvals, and audit is handled
        by the OvalEdge backend MCP API.
        """
        if object_type is None or str(object_type).strip() == "":
            return {"error": "object_type is required.", "status_code": 400}
        normalized_updates, err = _normalize_role_updates(role_updates)
        if err:
            return {"error": err, "status_code": 400}

        otype_key = str(object_type).strip().lower()
        if otype_key in MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES and normalized_updates:
            invalid_roles = [
                role
                for role in normalized_updates
                if role != "steward"
            ]
            if invalid_roles:
                return {
                    "error": (
                        f"Only steward may be updated on {otype_key}. "
                        f"Invalid role(s): {', '.join(sorted(invalid_roles))}."
                    ),
                    "status_code": 400,
                }

        body: dict[str, Any] = {
            "target": {"objectId": object_id, "objectType": str(object_type).strip()},
            "roleUpdates": normalized_updates,
        }
        options: dict[str, Any] = {}
        if dry_run is not None:
            options["dryRun"] = dry_run
        if idempotency_key is not None and str(idempotency_key).strip():
            options["idempotencyKey"] = str(idempotency_key).strip()
        if options:
            body["options"] = options
        client_context: dict[str, str] = {}
        if prompt is not None and str(prompt).strip():
            client_context["prompt"] = str(prompt).strip()
        if reason is not None and str(reason).strip():
            client_context["reason"] = str(reason).strip()
        if client_context:
            body["clientContext"] = client_context

        is_dry = dry_run is True
        if not is_dry and not create_confirmed_by_user:
            return _format_update_governance_roles_confirmation_preview(body)

        try:
            async with ovaledge_client() as client:
                result = await client.post(MCP_PATH_UPDATE_GOVERNANCE_ROLES, body)
                if isinstance(result, dict):
                    return _enrich_update_governance_roles_response(result)
                return result
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

    @mcp.tool(description=_DESC_LOOKUP_DQ_RULE)
    async def lookup_dq_rule(
        object_id: Annotated[
            int | None,
            Field(description="DQ rule id (dqruleid); omit if using rule_name.", default=None),
        ] = None,
        rule_name: Annotated[
            str | None,
            Field(
                description="Rule name or substring (e.g. Null Data Density Check).",
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description="Max hits for name search (default 20; server max 100).",
                default=MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
                ge=1,
            ),
        ] = MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    ) -> dict[str, Any]:
        """Resolve Data Quality rules for governance updates (see MCP tool description)."""
        has_id = object_id is not None and object_id > 0
        has_name = rule_name is not None and str(rule_name).strip() != ""
        if has_id and has_name:
            return {
                "error": "Provide either rule_name or object_id for DQ rule lookup, not both.",
                "status_code": 400,
            }
        if not has_id and not has_name:
            return {"error": "Provide rule_name or object_id.", "status_code": 400}
        capped = min(limit, MCP_GLOSSARY_TAGS_LIMIT_MAX)
        try:
            async with ovaledge_client() as client:
                body = await client.get(
                    MCP_PATH_LOOKUP_DQ_RULES,
                    params=_q(
                        objectId=object_id if has_id else None,
                        ruleName=strip_or_none(rule_name) if has_name else None,
                        limit=capped,
                    ),
                )
                return body if isinstance(body, dict) else {"data": body}
        except OvalEdgeError as e:
            return map_ovaledge_error(e)

    @mcp.tool(description=_DESC_ASSESS_CDE_DQ)
    async def assess_cde_dq(
        discover_cde_columns: Annotated[
            bool,
            Field(
                description=(
                    "When true and objects is empty, discovers CDE table/file columns via "
                    "catalog search (criticalDataElement=Yes)."
                ),
                default=False,
            ),
        ] = False,
        objects: Annotated[
            list[dict[str, Any]] | None,
            Field(
                description=(
                    "Catalog objects to assess from search_catalog_assets. objectType: "
                    + MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC
                    + ". Each entry: objectId + objectType (or object_id + object_type)."
                ),
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    f"Max objects to assess (default {MCP_DQ_ASSESS_LIMIT_DEFAULT}; "
                    f"server max {MCP_DQ_ASSESS_LIMIT_MAX})."
                ),
                default=MCP_DQ_ASSESS_LIMIT_DEFAULT,
                ge=1,
            ),
        ] = MCP_DQ_ASSESS_LIMIT_DEFAULT,
    ) -> dict[str, Any]:
        """CDE / column DQ assessment (see MCP tool description)."""
        return await _invoke_assess_cde_dq(discover_cde_columns, objects, limit)

    @mcp.tool(description=_DESC_ASSOCIATE_DQ_RULE_OBJECTS)
    async def associate_dq_rule_objects(
        dqrule_id: Annotated[
            int,
            Field(description="Draft DQ rule id to link objects to."),
        ],
        objects: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Catalog objects to associate. objectType: "
                    + MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC
                ),
            ),
        ],
        skip_already_associated: Annotated[
            bool,
            Field(
                description="When true, already-linked objects are skipped (idempotent).",
                default=True,
            ),
        ] = True,
    ) -> dict[str, Any]:
        """Link catalog objects to a draft DQ rule (see MCP tool description)."""
        return await _invoke_associate_dq_rule_objects(
            dqrule_id, objects, skip_already_associated
        )

    @mcp.tool(description=_DESC_CREATE_DQ_RULES)
    async def create_dq_rules(
        discover_cde_columns: Annotated[
            bool,
            Field(
                description=(
                    "When true and objects is empty, discovers CDE columns via catalog search."
                ),
                default=False,
            ),
        ] = False,
        objects: Annotated[
            list[dict[str, Any]] | None,
            Field(
                description=(
                    "Objects to assess and create/associate rules for. objectType: "
                    + MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC
                ),
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    f"Max objects (default {MCP_DQ_ASSESS_LIMIT_DEFAULT}; "
                    f"max {MCP_DQ_ASSESS_LIMIT_MAX})."
                ),
                default=MCP_DQ_ASSESS_LIMIT_DEFAULT,
                ge=1,
            ),
        ] = MCP_DQ_ASSESS_LIMIT_DEFAULT,
        prefer_existing_rule: Annotated[
            bool,
            Field(
                description="Associate to recommended existing rule when available.",
                default=True,
            ),
        ] = True,
        skip_duplicate_function_on_object: Annotated[
            bool,
            Field(
                description="Skip when object already has a DQ rule for the same function type.",
                default=True,
            ),
        ] = True,
    ) -> dict[str, Any]:
        """Assess then create or associate DQ rules for CDE columns (see MCP tool description)."""
        return await _invoke_create_dq_rules(
            discover_cde_columns,
            objects,
            limit,
            prefer_existing_rule,
            skip_duplicate_function_on_object,
        )


async def _invoke_assess_cde_dq(
    discover_cde_columns: bool,
    objects: list[dict[str, Any]] | None,
    limit: int,
) -> dict[str, Any]:
    err = validate_assess_cde_dq_args(discover_cde_columns, objects)
    if err is not None:
        return err
    payload = build_assess_cde_dq_payload(discover_cde_columns, objects, limit)
    if "error" in payload:
        return payload
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_ASSESS_CDE_DQ, payload)
            return body if isinstance(body, dict) else {"data": body}
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


async def _invoke_associate_dq_rule_objects(
    dqrule_id: int,
    objects: list[dict[str, Any]],
    skip_already_associated: bool,
) -> dict[str, Any]:
    err = validate_associate_dq_rule_objects_args(dqrule_id, objects)
    if err is not None:
        return err
    payload = build_associate_dq_rule_objects_payload(
        dqrule_id, objects, skip_already_associated
    )
    if "error" in payload:
        return payload
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS, payload)
            out = body if isinstance(body, dict) else {"data": body}
            out["formattedResponse"] = format_associate_dq_rule_objects_response(out)
            return out
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


async def _invoke_create_dq_rules(
    discover_cde_columns: bool,
    objects: list[dict[str, Any]] | None,
    limit: int,
    prefer_existing_rule: bool,
    skip_duplicate_function_on_object: bool,
) -> dict[str, Any]:
    err = validate_create_dq_rules_args(discover_cde_columns, objects)
    if err is not None:
        return err
    payload = build_create_dq_rules_payload(
        discover_cde_columns,
        objects,
        limit,
        prefer_existing_rule,
        skip_duplicate_function_on_object,
    )
    if "error" in payload:
        return payload
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_CREATE_DQ_RULES, payload)
            return body if isinstance(body, dict) else {"data": body}
    except OvalEdgeError as e:
        return map_ovaledge_error(e)
