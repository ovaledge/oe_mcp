"""MCP tool registration for Data Quality workflows."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.client import OvalEdgeError
from server.constants import (
    MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC,
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    MCP_DQ_ASSESS_LIMIT_MAX,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    MCP_GLOSSARY_TAGS_LIMIT_MAX,
    MCP_PATH_ASSESS_CDE_DQ,
    MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS,
    MCP_PATH_CREATE_DQ_RULES,
    MCP_PATH_LOOKUP_DQ_RULES,
)
from server.tools.common import drop_none as _q
from server.tools.common import map_ovaledge_error, ovaledge_client, strip_or_none
from server.tools.dataquality.helpers import (
    _DESC_ASSESS_CDE_DQ,
    _DESC_ASSOCIATE_DQ_RULE_OBJECTS,
    _DESC_CREATE_DQ_RULES,
    _DESC_LOOKUP_DQ_RULE,
    build_assess_cde_dq_payload,
    build_associate_dq_rule_objects_payload,
    build_create_dq_rules_payload,
    format_assess_cde_dq_response,
    format_associate_dq_rule_objects_response,
    validate_assess_cde_dq_args,
    validate_associate_dq_rule_objects_args,
    validate_create_dq_rules_args,
    validate_lookup_dq_rule_args,
)


def register(mcp: FastMCP) -> None:

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
        return await _invoke_lookup_dq_rule(object_id, rule_name, limit)

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
        description_custom_field_name: Annotated[
            str | None,
            Field(
                description=(
                    "Custom field label/key to use as business description only when the user "
                    "explicitly names it in the prompt. Applied after object and term "
                    "descriptions are checked."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """CDE / column DQ assessment (see MCP tool description)."""
        return await _invoke_assess_cde_dq(
            discover_cde_columns, objects, limit, description_custom_field_name
        )

    @mcp.tool(description=_DESC_ASSOCIATE_DQ_RULE_OBJECTS)
    async def associate_dq_rule_objects(
        dqrule_id: Annotated[
            int,
            Field(description="Data Quality rule id to link objects to."),
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
        """Link catalog objects to a data quality rule (see MCP tool description)."""
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
        description_custom_field_name: Annotated[
            str | None,
            Field(
                description=(
                    "Custom field label/key from the user's prompt when object and term "
                    "descriptions are empty."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Assess then create or associate DQ rules for CDE columns (see MCP tool description)."""
        return await _invoke_create_dq_rules(
            discover_cde_columns,
            objects,
            limit,
            prefer_existing_rule,
            skip_duplicate_function_on_object,
            description_custom_field_name,
        )


async def _invoke_lookup_dq_rule(
    object_id: int | None,
    rule_name: str | None,
    limit: int,
) -> dict[str, Any]:
    err = validate_lookup_dq_rule_args(object_id, rule_name)
    if err is not None:
        return err
    has_id = object_id is not None and object_id > 0
    has_name = rule_name is not None and str(rule_name).strip() != ""
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


async def _invoke_assess_cde_dq(
    discover_cde_columns: bool,
    objects: list[dict[str, Any]] | None,
    limit: int,
    description_custom_field_name: str | None = None,
) -> dict[str, Any]:
    err = validate_assess_cde_dq_args(discover_cde_columns, objects)
    if err is not None:
        return err
    payload = build_assess_cde_dq_payload(
        discover_cde_columns, objects, limit, description_custom_field_name
    )
    if "error" in payload:
        return payload
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_ASSESS_CDE_DQ, payload)
            out = body if isinstance(body, dict) else {"data": body}
            out["formattedResponse"] = format_assess_cde_dq_response(out)
            return out
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
    description_custom_field_name: str | None = None,
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
        description_custom_field_name,
    )
    if "error" in payload:
        return payload
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_CREATE_DQ_RULES, payload)
            return body if isinstance(body, dict) else {"data": body}
    except OvalEdgeError as e:
        return map_ovaledge_error(e)
