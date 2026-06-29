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
    MCP_PATH_CREATE_SQL_DQ_RULE,
    MCP_PATH_GENERATE_DQ_QUERIES,
    MCP_PATH_LOOKUP_DQ_RULES,
    MCP_PATH_VALIDATE_DQ_QUERIES,
)
from server.tools.common import drop_none as _q
from server.tools.common import map_ovaledge_error, ovaledge_client, strip_or_none
from server.tools.common.confirm_gate import (
    CONFIRMATION_TOKEN_PARAM_DESCRIPTION,
    verify_write_confirmation,
)
from server.tools.common.tool_logging import logged_tool_invocation
from server.tools.dataquality.helpers import (
    _DESC_ASSESS_CDE_DQ,
    _DESC_ASSOCIATE_DQ_RULE_OBJECTS,
    _DESC_CREATE_DQ_RULES,
    _DESC_CREATE_SQL_DQ_RULE,
    _DESC_GENERATE_DQ_QUERIES,
    _DESC_LOOKUP_DQ_RULE,
    _DESC_VALIDATE_DQ_QUERIES,
    build_assess_cde_dq_payload,
    build_associate_dq_rule_objects_payload,
    build_create_dq_rules_payload,
    build_create_sql_dq_rule_payload,
    build_generate_dq_queries_payload,
    build_validate_dq_queries_payload,
    format_assess_cde_dq_response,
    format_associate_dq_rule_confirmation_preview,
    format_associate_dq_rule_objects_response,
    format_create_dq_rules_confirmation_preview,
    format_create_dq_rules_response,
    format_create_sql_dq_rule_confirmation_preview,
    format_create_sql_dq_rule_response,
    format_generate_dq_queries_response,
    format_validate_dq_queries_confirmation_preview,
    format_validate_dq_queries_response,
    validate_assess_cde_dq_args,
    validate_associate_dq_rule_objects_args,
    validate_create_dq_rules_args,
    validate_create_sql_dq_rule_args,
    validate_generate_dq_queries_args,
    validate_lookup_dq_rule_args,
    validate_validate_dq_queries_args,
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
        return await _invoke_lookup_dq_rule(
            object_id=object_id,
            rule_name=rule_name,
            limit=limit,
        )

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
                    "explicitly names it in the prompt."
                ),
                default=None,
            ),
        ] = None,
        description_term_name: Annotated[
            str | None,
            Field(
                description=(
                    "Glossary term name to use as business description only when the user "
                    "explicitly names it in the prompt."
                ),
                default=None,
            ),
        ] = None,
    ) -> dict[str, Any]:
        """CDE / column DQ assessment (see MCP tool description)."""
        return await _invoke_assess_cde_dq(
            discover_cde_columns=discover_cde_columns,
            objects=objects,
            limit=limit,
            description_custom_field_name=description_custom_field_name,
            description_term_name=description_term_name,
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
        write_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final update gate: true only after the user explicitly approved "
                    "the confirm_update preview. Re-call with the same dqrule_id, "
                    "objects, and skip_already_associated."
                ),
                default=False,
            ),
        ] = False,
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """Link catalog objects to a data quality rule (see MCP tool description)."""
        return await _invoke_associate_dq_rule_objects(
            dqrule_id=dqrule_id,
            objects=objects,
            skip_already_associated=skip_already_associated,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
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
                    "Custom field label/key from the user's prompt when they name a field "
                    "instead of the catalog description."
                ),
                default=None,
            ),
        ] = None,
        description_term_name: Annotated[
            str | None,
            Field(
                description=(
                    "Glossary term name from the user's prompt when they name a term "
                    "instead of the catalog description."
                ),
                default=None,
            ),
        ] = None,
        supplemental_criteria_text: Annotated[
            str | None,
            Field(
                description=(
                    "Success/input criteria from the user prompt when not in catalog metadata "
                    "(e.g. 'Success criteria: equal to 300')."
                ),
                default=None,
            ),
        ] = None,
        write_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final create gate: true only after the user explicitly approved "
                    "the confirm_create preview. Re-call with the same discover_cde_columns, "
                    "objects, limit, flags, and optional description_term_name or "
                    "description_custom_field_name."
                ),
                default=False,
            ),
        ] = False,
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """Assess then create or associate DQ rules for CDE columns (see MCP tool description)."""
        return await _invoke_create_dq_rules(
            discover_cde_columns=discover_cde_columns,
            objects=objects,
            limit=limit,
            prefer_existing_rule=prefer_existing_rule,
            skip_duplicate_function_on_object=skip_duplicate_function_on_object,
            description_custom_field_name=description_custom_field_name,
            description_term_name=description_term_name,
            supplemental_criteria_text=supplemental_criteria_text,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )

    @mcp.tool(description=_DESC_GENERATE_DQ_QUERIES)
    async def generate_dq_queries(
        objects: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Catalog object to generate SQL for. objectType: "
                    + MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC
                ),
            ),
        ],
        business_rule: Annotated[
            str | None,
            Field(description="Optional business rule text override.", default=None),
        ] = None,
        business_description: Annotated[
            str | None,
            Field(description="Optional business description override.", default=None),
        ] = None,
    ) -> dict[str, Any]:
        """Generate custom SQL DQ queries for a catalog object (see MCP tool description)."""
        return await _invoke_generate_dq_queries(
            objects=objects,
            business_rule=business_rule,
            business_description=business_description,
        )

    @mcp.tool(description=_DESC_VALIDATE_DQ_QUERIES)
    async def validate_dq_queries(
        connection_id: Annotated[
            int,
            Field(description="OvalEdge connection id from generate_dq_queries context."),
        ],
        schema_id: Annotated[
            int,
            Field(description="OvalEdge schema id from generate_dq_queries context."),
        ],
        rule_query: Annotated[str, Field(description="Rule SELECT SQL.")],
        stats_query: Annotated[str, Field(description="Stats SELECT SQL.")],
        failed_values_query: Annotated[
            str, Field(description="Failed-values SELECT SQL.")
        ],
        write_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final gate: true only after the user explicitly approved "
                    "the confirm_create preview. Re-call with the same connection_id, "
                    "schema_id, and three queries."
                ),
                default=False,
            ),
        ] = False,
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """Validate DQ SQL via Query Sheet execution (see MCP tool description)."""
        return await _invoke_validate_dq_queries(
            connection_id=connection_id,
            schema_id=schema_id,
            rule_query=rule_query,
            stats_query=stats_query,
            failed_values_query=failed_values_query,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )

    @mcp.tool(description=_DESC_CREATE_SQL_DQ_RULE)
    async def create_sql_dq_rule(
        objects: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Catalog objects (first is primary). objectType: "
                    + MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC
                ),
            ),
        ],
        rule_name: Annotated[str, Field(description="Draft DQ rule name.")],
        rule_query: Annotated[
            str | None,
            Field(description="Rule SELECT SQL (omit when code_object_id is set).", default=None),
        ] = None,
        stats_query: Annotated[
            str | None,
            Field(description="Stats SELECT SQL.", default=None),
        ] = None,
        failed_values_query: Annotated[
            str | None,
            Field(description="Failed-values SELECT SQL.", default=None),
        ] = None,
        connection_id: Annotated[
            int | None,
            Field(description="Connection id from generate/validate context.", default=None),
        ] = None,
        schema_id: Annotated[
            int | None,
            Field(description="Schema id from generate/validate context.", default=None),
        ] = None,
        purpose: Annotated[
            str | None,
            Field(description="Optional DQ rule purpose.", default=None),
        ] = None,
        recommended_function: Annotated[
            str | None,
            Field(description="DQ function from assess/generate.", default=None),
        ] = None,
        code_object_id: Annotated[
            int | None,
            Field(description="Reuse existing oequery code object.", default=None),
        ] = None,
        write_confirmed_by_user: Annotated[
            bool,
            Field(
                description=(
                    "Final create gate: true only after the user explicitly approved "
                    "the confirm_create preview. Re-call with the same parameters."
                ),
                default=False,
            ),
        ] = False,
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """Create draft custom SQL DQ rule (see MCP tool description)."""
        return await _invoke_create_sql_dq_rule(
            objects=objects,
            rule_name=rule_name,
            rule_query=rule_query,
            stats_query=stats_query,
            failed_values_query=failed_values_query,
            connection_id=connection_id,
            schema_id=schema_id,
            purpose=purpose,
            recommended_function=recommended_function,
            code_object_id=code_object_id,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )


@logged_tool_invocation
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


@logged_tool_invocation
async def _invoke_assess_cde_dq(
    discover_cde_columns: bool,
    objects: list[dict[str, Any]] | None,
    limit: int,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
) -> dict[str, Any]:
    err = validate_assess_cde_dq_args(discover_cde_columns, objects)
    if err is not None:
        return err
    payload = build_assess_cde_dq_payload(
        discover_cde_columns,
        objects,
        limit,
        description_custom_field_name,
        description_term_name,
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


@logged_tool_invocation
async def _invoke_associate_dq_rule_objects(
    dqrule_id: int,
    objects: list[dict[str, Any]],
    skip_already_associated: bool,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    err = validate_associate_dq_rule_objects_args(dqrule_id, objects)
    if err is not None:
        return err
    payload = build_associate_dq_rule_objects_payload(
        dqrule_id, objects, skip_already_associated
    )
    if "error" in payload:
        return payload
    if not write_confirmed_by_user:
        return format_associate_dq_rule_confirmation_preview(payload)
    confirm_err = verify_write_confirmation(
        payload,
        write_confirmed_by_user=write_confirmed_by_user,
        confirmation_token=confirmation_token,
    )
    if confirm_err is not None:
        return confirm_err
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS, payload)
            out = body if isinstance(body, dict) else {"data": body}
            out["formattedResponse"] = format_associate_dq_rule_objects_response(out)
            return out
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_create_dq_rules(
    discover_cde_columns: bool,
    objects: list[dict[str, Any]] | None,
    limit: int,
    prefer_existing_rule: bool,
    skip_duplicate_function_on_object: bool,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
    supplemental_criteria_text: str | None = None,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
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
        description_term_name,
        supplemental_criteria_text,
    )
    if "error" in payload:
        return payload
    if not write_confirmed_by_user:
        return format_create_dq_rules_confirmation_preview(payload)
    confirm_err = verify_write_confirmation(
        payload,
        write_confirmed_by_user=write_confirmed_by_user,
        confirmation_token=confirmation_token,
    )
    if confirm_err is not None:
        return confirm_err
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_CREATE_DQ_RULES, payload)
            out = body if isinstance(body, dict) else {"data": body}
            out["formattedResponse"] = format_create_dq_rules_response(out)
            return out
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_generate_dq_queries(
    objects: list[dict[str, Any]] | None,
    business_rule: str | None,
    business_description: str | None,
) -> dict[str, Any]:
    err = validate_generate_dq_queries_args(objects)
    if err is not None:
        return err
    payload = build_generate_dq_queries_payload(objects, business_rule, business_description)
    if "error" in payload:
        return payload
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_GENERATE_DQ_QUERIES, payload)
            out = body if isinstance(body, dict) else {"data": body}
            return format_generate_dq_queries_response(out)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_validate_dq_queries(
    connection_id: int,
    schema_id: int,
    rule_query: str,
    stats_query: str,
    failed_values_query: str,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    err = validate_validate_dq_queries_args(
        connection_id, schema_id, rule_query, stats_query, failed_values_query
    )
    if err is not None:
        return err
    payload = build_validate_dq_queries_payload(
        connection_id, schema_id, rule_query, stats_query, failed_values_query
    )
    if not write_confirmed_by_user:
        return format_validate_dq_queries_confirmation_preview(payload)
    confirm_err = verify_write_confirmation(
        payload,
        write_confirmed_by_user=write_confirmed_by_user,
        confirmation_token=confirmation_token,
    )
    if confirm_err is not None:
        return confirm_err
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_VALIDATE_DQ_QUERIES, payload)
            out = body if isinstance(body, dict) else {"data": body}
            return format_validate_dq_queries_response(out)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_create_sql_dq_rule(
    objects: list[dict[str, Any]] | None,
    rule_name: str,
    rule_query: str | None,
    stats_query: str | None,
    failed_values_query: str | None,
    connection_id: int | None,
    schema_id: int | None,
    purpose: str | None,
    recommended_function: str | None,
    code_object_id: int | None,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    err = validate_create_sql_dq_rule_args(
        objects, rule_name, rule_query, stats_query, failed_values_query, code_object_id
    )
    if err is not None:
        return err
    payload = build_create_sql_dq_rule_payload(
        objects,
        rule_name,
        rule_query,
        stats_query,
        failed_values_query,
        connection_id,
        schema_id,
        purpose,
        recommended_function,
        code_object_id,
    )
    if "error" in payload:
        return payload
    if not write_confirmed_by_user:
        return format_create_sql_dq_rule_confirmation_preview(payload)
    confirm_err = verify_write_confirmation(
        payload,
        write_confirmed_by_user=write_confirmed_by_user,
        confirmation_token=confirmation_token,
    )
    if confirm_err is not None:
        return confirm_err
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_CREATE_SQL_DQ_RULE, payload)
            out = body if isinstance(body, dict) else {"data": body}
            return format_create_sql_dq_rule_response(out)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)
