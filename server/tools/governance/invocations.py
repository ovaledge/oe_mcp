"""Invocation logic for governance MCP tools (extracted from register)."""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError
from server.config import resolve_client_timezone
from server.constants import (
    MCP_CATALOG_OBJECT_TYPES,
    MCP_CUSTOM_FIELD_OBJECT_TYPES,
    MCP_DOMAIN_METADATA_SEARCH_ON,
    MCP_DOMAIN_METADATA_SIZE_DEFAULT,
    MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES,
    MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES_DOC,
    MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES,
    MCP_PATH_GLOSSARY_TERMS,
    MCP_PATH_TAGS,
    MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES,
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
)
from server.tools.common.confirm_gate import verify_write_confirmation
from server.tools.common.tool_logging import logged_tool_invocation
from server.tools.governance.helpers import (
    _apply_code_field_update_policies,
    _block_llm_master_selection,
    _block_llm_parent_selection,
    _consume_parent_picker_shown,
    _enrich_create_tag_response,
    _enrich_update_custom_field_value_response,
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
    _format_update_custom_field_value_confirmation_preview,
    _format_update_governance_roles_confirmation_preview,
    _load_secure_create_guidance,
    _lookup_tag_after_create,
    _master_tag_ids_from_guidance_data,
    _normalize_field_updates,
    _normalize_role_updates,
    _parent_choice_finalized,
    _parent_picker_was_shown,
    _parent_tag_is_allowed_under_master,
    _reject_invented_master_tag_id,
    _resolve_category_id_by_name,
    _resolve_create_tag_description,
    _resolve_domain_id_by_name,
    _resolve_tag_hierarchy_names_for_create,
    _shape_create_response,
    _shape_picker_response,
)


@logged_tool_invocation
async def _invoke_create_glossary_term(
    search_on: str | None = None,
    term_name: str | None = None,
    domain_id: int | None = None,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    description: str | None = None,
    definition: str | None = None,
    domain_name: str | None = None,
    category_name: str | None = None,
    subcategory_name: str | None = None,
    publish: bool = False,
    skip_category: bool = False,
    category_skip_confirmed: bool = False,
    skip_subcategory: bool = False,
    subcategory_skip_confirmed: bool = False,
    size: int = MCP_DOMAIN_METADATA_SIZE_DEFAULT,
    page: int = 0,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
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
    if not write_confirmed_by_user:
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
            post_body=post_body,
        )
    confirm_err = verify_write_confirmation(
        post_body,
        write_confirmed_by_user=write_confirmed_by_user,
        confirmation_token=confirmation_token,
    )
    if confirm_err is not None:
        return confirm_err
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


@logged_tool_invocation
async def _invoke_create_tag(
    tag_name: str,
    description: str | None = None,
    master_tag_id: int | None = None,
    master_tag_id_confirmed_by_user: bool = False,
    parent_tag_id: int | None = None,
    parent_tag_id_confirmed_by_user: bool = False,
    browse_parent_tag_id: int | None = None,
    create_directly_under_master: bool = False,
    parent_step_completed_by_user: bool = False,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
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
                    allowed = await _parent_tag_is_allowed_under_master(
                        client,
                        master_tag_id,
                        parent_tag_id,
                        secure_guidance,
                    )
                    if not allowed:
                        _, parents_hint, _ = await _fetch_parent_choices_for_master(
                            client, master_tag_id, secure_guidance
                        )
                        return {
                            "ok": False,
                            "status_code": 422,
                            "message": (
                                f"parent_tag_id {parent_tag_id} is not under "
                                f"master_tag_id {master_tag_id}."
                            ),
                            "doNotCreateTag": True,
                            "userSelectableParents": parents_hint,
                            "formattedResponse": (
                                f"parent_tag_id {parent_tag_id} is not listed under "
                                f"master_tag_id {master_tag_id}. Ask the human to pick "
                                "from userSelectableParents, browse deeper with "
                                "browse_parent_tag_id when hasChildren=true, or decline "
                                "with create_directly_under_master=true and "
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
                    master_name, parents, browse_meta = (
                        await _fetch_parent_choices_for_master(
                            client,
                            master_tag_id,
                            secure_guidance,
                            browse_parent_tag_id=browse_parent_tag_id,
                        )
                    )
                    return _format_parent_selection_guidance(
                        master_tag_id=master_tag_id,
                        master_tag_name=master_name,
                        parents=parents,
                        tag_name=name,
                        browse_meta=browse_meta,
                    )
                if not _parent_picker_was_shown(name):
                    master_name, parents, browse_meta = (
                        await _fetch_parent_choices_for_master(
                            client,
                            master_tag_id,
                            secure_guidance,
                            browse_parent_tag_id=browse_parent_tag_id,
                        )
                    )
                    out = _format_parent_selection_guidance(
                        master_tag_id=master_tag_id,
                        master_tag_name=master_name,
                        parents=parents,
                        tag_name=name,
                        browse_meta=browse_meta,
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
                        open_parents = await _fetch_open_parent_choices(
                            client, browse_parent_tag_id=browse_parent_tag_id
                        )
                        guidance = _format_open_parent_selection_guidance(
                            parents=open_parents,
                            tag_name=name,
                            browse_parent_tag_id=browse_parent_tag_id,
                        )
                        return _block_llm_parent_selection(
                            guidance,
                            parent_tag_id=parent_tag_id,
                        )
                    open_parents = await _fetch_open_parent_choices(
                        client, browse_parent_tag_id=browse_parent_tag_id
                    )
                    allowed_open = {p["parentTagId"] for p in open_parents}
                    if allowed_open and parent_tag_id not in allowed_open:
                        if browse_parent_tag_id is None or browse_parent_tag_id <= 0:
                            for p in open_parents:
                                if not p.get("hasChildren"):
                                    continue
                                nested = await _fetch_open_parent_choices(
                                    client,
                                    browse_parent_tag_id=p["parentTagId"],
                                )
                                allowed_open.update(
                                    n["parentTagId"] for n in nested
                                )
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
                    open_parents = await _fetch_open_parent_choices(
                        client, browse_parent_tag_id=browse_parent_tag_id
                    )
                    return _format_open_parent_selection_guidance(
                        parents=open_parents,
                        tag_name=name,
                        browse_parent_tag_id=browse_parent_tag_id,
                    )
                if not _parent_picker_was_shown(name):
                    open_parents = await _fetch_open_parent_choices(
                        client, browse_parent_tag_id=browse_parent_tag_id
                    )
                    out = _format_open_parent_selection_guidance(
                        parents=open_parents,
                        tag_name=name,
                        browse_parent_tag_id=browse_parent_tag_id,
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
            if not write_confirmed_by_user:
                wire_body = _q(
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
                return _format_tag_create_confirmation_preview(
                    tag_name=name,
                    description=description,
                    secure_mode=secure_mode,
                    master_tag_id=master_tag_id,
                    master_tag_name=master_name_for_desc,
                    parent_tag_id=parent_tag_id,
                    parent_tag_name=parent_name_for_desc,
                    create_directly_under_master=create_directly_under_master,
                    wire_body=wire_body,
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
                    master_name, parents, browse_meta = (
                        await _fetch_parent_choices_for_master(
                            client,
                            resolved_master_id,
                            secure_guidance,
                            browse_parent_tag_id=browse_parent_tag_id,
                        )
                    )
                    out = _format_parent_selection_guidance(
                        master_tag_id=resolved_master_id,
                        master_tag_name=master_name,
                        parents=parents,
                        tag_name=name,
                        browse_meta=browse_meta,
                    )
                else:
                    open_parents = await _fetch_open_parent_choices(
                        client, browse_parent_tag_id=browse_parent_tag_id
                    )
                    out = _format_open_parent_selection_guidance(
                        parents=open_parents,
                        tag_name=name,
                        browse_parent_tag_id=browse_parent_tag_id,
                    )
                out["message"] = (
                    "Parent picker session expired or was not completed. "
                    "Present userSelectableParents again, then retry with "
                    "parent_step_completed_by_user=true and write_confirmed_by_user=true."
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
            confirm_err = verify_write_confirmation(
                body,
                write_confirmed_by_user=write_confirmed_by_user,
                confirmation_token=confirmation_token,
            )
            if confirm_err is not None:
                return confirm_err
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


@logged_tool_invocation
async def _invoke_update_governance_roles(
    object_id: int,
    object_type: str,
    role_updates: dict[str, str | None] | None = None,
    prompt: str | None = None,
    reason: str | None = None,
    dry_run: bool | None = None,
    idempotency_key: str | None = None,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
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
    if (
        otype_key not in MCP_CATALOG_OBJECT_TYPES
        and otype_key not in MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES
    ):
        return {
            "error": (
                f"Unsupported object_type {object_type!r}. Use a catalog objectType from "
                "asset_explorer, or one of: "
                f"{MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES_DOC}."
            ),
            "status_code": 400,
        }
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
    if not is_dry and not write_confirmed_by_user:
        return _format_update_governance_roles_confirmation_preview(body)
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
            result = await client.post(MCP_PATH_UPDATE_GOVERNANCE_ROLES, body)
            if isinstance(result, dict):
                return _enrich_update_governance_roles_response(result)
            return result
    except OvalEdgeError as e:
        msg = str(e)
        prefix = f"OvalEdge API error {e.status_code}: "
        if msg.startswith(prefix):
            msg = msg[len(prefix) :].strip()
        lower = msg.lower()
        if "governance role is not enabled" in lower and "role" in lower:
            return {
                "error": msg,
                "status_code": e.status_code,
                "reason_code": "GOVERNANCE_ROLE_NOT_ENABLED",
            }
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_update_custom_field_value(
    object_id: int,
    object_type: str,
    field_updates: list[dict[str, Any]],
    prompt: str | None = None,
    reason: str | None = None,
    dry_run: bool | None = None,
    fail_on_blocked_field: bool | None = None,
    idempotency_key: str | None = None,
    time_zone: str | None = None,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
    code_update_mode: str | None = None,
) -> dict[str, Any]:
    """Update custom field values (see MCP tool description)."""
    if object_type is None or str(object_type).strip() == "":
        return {"error": "object_type is required.", "status_code": 400}
    otype_key = str(object_type).strip().lower()
    if otype_key not in MCP_CUSTOM_FIELD_OBJECT_TYPES:
        return {
            "error": (
                f"object_type must be one of {sorted(MCP_CUSTOM_FIELD_OBJECT_TYPES)}, "
                f"got {object_type!r}"
            ),
            "status_code": 400,
        }
    normalized_updates, err = _normalize_field_updates(field_updates)
    if err or normalized_updates is None:
        return {"error": err or "field_updates is required.", "status_code": 400}

    body: dict[str, Any] = {
        "target": {"objectId": object_id, "objectType": str(object_type).strip()},
        "fieldUpdates": normalized_updates,
    }
    resolved_tz = (
        str(time_zone).strip()
        if time_zone is not None and str(time_zone).strip()
        else resolve_client_timezone()
    )
    if resolved_tz:
        body["timeZone"] = resolved_tz
    options: dict[str, Any] = {}
    if dry_run is not None:
        options["dryRun"] = dry_run
    if fail_on_blocked_field is not None:
        options["failOnBlockedField"] = fail_on_blocked_field
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
    # Resolve code-field values for both preview and confirmed POST (confirm re-sends
    # the same field_updates, so resolution must run before preview as well).
    if not is_dry:
        try:
            async with ovaledge_client() as client:
                policy_result = await _apply_code_field_update_policies(
                    client,
                    object_id,
                    str(object_type).strip(),
                    normalized_updates,
                    code_update_mode,
                )
        except OvalEdgeError as e:
            return map_ovaledge_error(e)
        if policy_result.get("workflowPhase"):
            return policy_result
        if policy_result.get("error"):
            return policy_result
        normalized_updates = policy_result.get("fieldUpdates") or normalized_updates
        body["fieldUpdates"] = normalized_updates

    if not is_dry and not write_confirmed_by_user:
        return _format_update_custom_field_value_confirmation_preview(body)
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
            result = await client.post(MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES, body)
            if isinstance(result, dict):
                return _enrich_update_custom_field_value_response(result)
            return result
    except OvalEdgeError as e:
        return map_ovaledge_error(e)
