"""MCP tool registration for Data Quality workflows."""

from __future__ import annotations

from typing import Annotated, Any, Literal

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
from server.tools.common.annotations import GOVERNED_CREATE, GOVERNED_EXECUTE
from server.tools.common.confirm_gate import (
    CONFIRMATION_TOKEN_PARAM_DESCRIPTION,
    verify_write_confirmation,
)
from server.tools.common.tool_logging import logged_tool_invocation
from server.tools.dataquality.helpers import (
    _DESC_DQ_RULE_ADVISOR,
    _DESC_DQ_RULE_MANAGER,
    _DQ_ASSESS_AGENT_INSTRUCTION,
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
    map_create_sql_dq_error,
    validate_assess_cde_dq_args,
    validate_associate_dq_rule_objects_args,
    validate_create_dq_rules_args,
    validate_create_sql_dq_rule_args,
    validate_generate_dq_queries_args,
    validate_lookup_dq_rule_args,
    validate_validate_dq_queries_args,
)

# FastMCP may pass objects as JSON list, single dict, or JSON string.
type _DqObjectsArg = list[dict[str, Any]] | dict[str, Any] | str
type _DqObjectsArgOpt = _DqObjectsArg | None


def register(mcp: FastMCP) -> None:
    """Register consolidated DQ tools (advisor read + manager write)."""

    @mcp.tool(
        title="DQ rule advisor",
        description=_DESC_DQ_RULE_ADVISOR,
        annotations=GOVERNED_EXECUTE,  # validate_query confirm gate executes SQL
    )
    async def dq_rule_advisor(
        step: Annotated[
            Literal["assess", "generate_query", "validate_query", "lookup"],
            Field(description="assess | generate_query | validate_query | lookup"),
        ],
        discover_cde_columns: Annotated[
            bool,
            Field(
                description="assess: discover CDE columns when objects empty.",
                default=False,
            ),
        ] = False,
        objects: Annotated[
            _DqObjectsArgOpt,
            Field(
                description=(
                    "Catalog objects {objectId, objectType}. objectType: "
                    + MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC
                ),
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int | None,
            Field(
                description=(
                    f"assess default {MCP_DQ_ASSESS_LIMIT_DEFAULT} "
                    f"(max {MCP_DQ_ASSESS_LIMIT_MAX}); "
                    f"lookup default {MCP_GLOSSARY_TAGS_LIMIT_DEFAULT}."
                ),
                default=None,
                ge=1,
            ),
        ] = None,
        description_custom_field_name: Annotated[
            str | None,
            Field(description="assess: named custom field for description.", default=None),
        ] = None,
        description_term_name: Annotated[
            str | None,
            Field(description="assess: named glossary term for description.", default=None),
        ] = None,
        preferred_function_name: Annotated[
            str | None,
            Field(description="assess: user-selected function candidate.", default=None),
        ] = None,
        excluded_function_names: Annotated[
            list[str] | None,
            Field(description="assess: rejected function names.", default=None),
        ] = None,
        business_rule: Annotated[
            str | None,
            Field(description="generate_query: optional business rule override.", default=None),
        ] = None,
        business_description: Annotated[
            str | None,
            Field(description="generate_query: optional description override.", default=None),
        ] = None,
        connection_id: Annotated[
            int | None,
            Field(description="validate_query: connection id from generate.", default=None),
        ] = None,
        schema_id: Annotated[
            int | None,
            Field(description="validate_query: schema id from generate.", default=None),
        ] = None,
        rule_query: Annotated[
            str | None, Field(description="validate_query: rule SELECT SQL.", default=None)
        ] = None,
        stats_query: Annotated[
            str | None, Field(description="validate_query: stats SELECT SQL.", default=None)
        ] = None,
        failed_values_query: Annotated[
            str | None,
            Field(description="validate_query: failed-values SELECT SQL.", default=None),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(description="lookup: DQ rule id (omit if using rule_name).", default=None),
        ] = None,
        rule_name: Annotated[
            str | None,
            Field(description="lookup: DQ rule name/substring.", default=None),
        ] = None,
        write_confirmed_by_user: Annotated[
            bool,
            Field(
                description="validate_query: true only after user approved SQL execution preview.",
                default=False,
            ),
        ] = False,
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """DQ read/recommend steps (see MCP tool description)."""
        return await _invoke_dq_rule_advisor(
            step=step,
            discover_cde_columns=discover_cde_columns,
            objects=objects,
            limit=limit,
            description_custom_field_name=description_custom_field_name,
            description_term_name=description_term_name,
            preferred_function_name=preferred_function_name,
            excluded_function_names=excluded_function_names,
            business_rule=business_rule,
            business_description=business_description,
            connection_id=connection_id,
            schema_id=schema_id,
            rule_query=rule_query,
            stats_query=stats_query,
            failed_values_query=failed_values_query,
            object_id=object_id,
            rule_name=rule_name,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )

    @mcp.tool(
        title="DQ rule manager",
        description=_DESC_DQ_RULE_MANAGER,
        annotations=GOVERNED_CREATE,
    )
    async def dq_rule_manager(
        step: Annotated[
            Literal["create_standard", "create_custom_sql", "associate"],
            Field(description="create_standard | create_custom_sql | associate"),
        ],
        discover_cde_columns: Annotated[
            bool,
            Field(description="create_standard: discover CDEs when objects empty.", default=False),
        ] = False,
        objects: Annotated[
            _DqObjectsArgOpt,
            Field(
                description=(
                    "Catalog objects {objectId, objectType}. objectType: "
                    + MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC
                ),
                default=None,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description=(
                    f"create_standard max objects (default {MCP_DQ_ASSESS_LIMIT_DEFAULT})."
                ),
                default=MCP_DQ_ASSESS_LIMIT_DEFAULT,
                ge=1,
            ),
        ] = MCP_DQ_ASSESS_LIMIT_DEFAULT,
        prefer_existing_rule: Annotated[
            bool,
            Field(description="create_standard: list same-function rules to choose.", default=True),
        ] = True,
        skip_duplicate_function_on_object: Annotated[
            bool,
            Field(description="create_standard: skip duplicate function on object.", default=True),
        ] = True,
        description_custom_field_name: Annotated[
            str | None,
            Field(description="create_standard: named custom field for description.", default=None),
        ] = None,
        description_term_name: Annotated[
            str | None,
            Field(description="create_standard: glossary term for description.", default=None),
        ] = None,
        supplemental_criteria_text: Annotated[
            str | None,
            Field(
                description="create_standard: prompt criteria if not in metadata.",
                default=None,
            ),
        ] = None,
        preferred_function_name: Annotated[
            str | None,
            Field(description="create_standard: user-selected function from assess.", default=None),
        ] = None,
        excluded_function_names: Annotated[
            list[str] | None,
            Field(description="create_standard: rejected function names.", default=None),
        ] = None,
        dqrule_id: Annotated[
            int | None,
            Field(description="associate: DQ rule id (or use rule_name).", default=None),
        ] = None,
        rule_name: Annotated[
            str | None,
            Field(description="associate: resolve rule id via internal lookup.", default=None),
        ] = None,
        skip_already_associated: Annotated[
            bool,
            Field(description="associate: skip already-linked objects.", default=True),
        ] = True,
        sql_rule_name: Annotated[
            str | None,
            Field(description="create_custom_sql: new DQ rule name.", default=None),
        ] = None,
        rule_query: Annotated[
            str | None, Field(description="create_custom_sql: rule SELECT SQL.", default=None)
        ] = None,
        stats_query: Annotated[
            str | None, Field(description="create_custom_sql: stats SELECT SQL.", default=None)
        ] = None,
        failed_values_query: Annotated[
            str | None,
            Field(description="create_custom_sql: failed-values SELECT SQL.", default=None),
        ] = None,
        connection_id: Annotated[
            int | None, Field(description="create_custom_sql: connection id.", default=None)
        ] = None,
        schema_id: Annotated[
            int | None, Field(description="create_custom_sql: schema id.", default=None)
        ] = None,
        purpose: Annotated[
            str | None, Field(description="create_custom_sql: optional purpose.", default=None)
        ] = None,
        recommended_function: Annotated[
            str | None,
            Field(
                description=(
                    "create_custom_sql: recommendedFunction name from generate_query/assess."
                ),
                default=None,
            ),
        ] = None,
        code_object_id: Annotated[
            int | None,
            Field(description="create_custom_sql: reuse oequery code object.", default=None),
        ] = None,
        write_confirmed_by_user: Annotated[
            bool,
            Field(description="true only after user approved confirm preview.", default=False),
        ] = False,
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION, default=None),
        ] = None,
    ) -> dict[str, Any]:
        """DQ write steps (see MCP tool description)."""
        return await _invoke_dq_rule_manager(
            step=step,
            discover_cde_columns=discover_cde_columns,
            objects=objects,
            limit=limit,
            prefer_existing_rule=prefer_existing_rule,
            skip_duplicate_function_on_object=skip_duplicate_function_on_object,
            description_custom_field_name=description_custom_field_name,
            description_term_name=description_term_name,
            supplemental_criteria_text=supplemental_criteria_text,
            preferred_function_name=preferred_function_name,
            excluded_function_names=excluded_function_names,
            dqrule_id=dqrule_id,
            rule_name=rule_name if step == "associate" else None,
            skip_already_associated=skip_already_associated,
            create_rule_name=sql_rule_name or (rule_name if step == "create_custom_sql" else None),
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
async def _invoke_dq_rule_advisor(
    step: str,
    discover_cde_columns: bool = False,
    objects: _DqObjectsArgOpt = None,
    limit: int | None = None,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
    preferred_function_name: str | None = None,
    excluded_function_names: list[str] | None = None,
    business_rule: str | None = None,
    business_description: str | None = None,
    connection_id: int | None = None,
    schema_id: int | None = None,
    rule_query: str | None = None,
    stats_query: str | None = None,
    failed_values_query: str | None = None,
    object_id: int | None = None,
    rule_name: str | None = None,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    if step == "assess":
        return await _invoke_assess_cde_dq(
            discover_cde_columns=discover_cde_columns,
            objects=objects,
            limit=limit if limit is not None else MCP_DQ_ASSESS_LIMIT_DEFAULT,
            description_custom_field_name=description_custom_field_name,
            description_term_name=description_term_name,
            preferred_function_name=preferred_function_name,
            excluded_function_names=excluded_function_names,
        )
    if step == "generate_query":
        return await _invoke_generate_dq_queries(
            objects=objects,
            business_rule=business_rule,
            business_description=business_description,
        )
    if step == "validate_query":
        if connection_id is None or schema_id is None:
            from server.tools.common.errors import error_payload

            return error_payload(
                "validate_query requires connection_id and schema_id.",
                error_code="validation_required",
            )
        return await _invoke_validate_dq_queries(
            connection_id=connection_id,
            schema_id=schema_id,
            rule_query=rule_query or "",
            stats_query=stats_query or "",
            failed_values_query=failed_values_query or "",
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )
    if step == "lookup":
        return await _invoke_lookup_dq_rule(
            object_id=object_id,
            rule_name=rule_name,
            limit=limit if limit is not None else MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
        )
    from server.tools.common.errors import error_payload

    return error_payload(
        "step must be assess | generate_query | validate_query | lookup.",
        error_code="validation_invalid",
    )


@logged_tool_invocation
async def _invoke_dq_rule_manager(
    step: str,
    discover_cde_columns: bool = False,
    objects: _DqObjectsArgOpt = None,
    limit: int = MCP_DQ_ASSESS_LIMIT_DEFAULT,
    prefer_existing_rule: bool = True,
    skip_duplicate_function_on_object: bool = True,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
    supplemental_criteria_text: str | None = None,
    preferred_function_name: str | None = None,
    excluded_function_names: list[str] | None = None,
    dqrule_id: int | None = None,
    rule_name: str | None = None,
    skip_already_associated: bool = True,
    create_rule_name: str | None = None,
    rule_query: str | None = None,
    stats_query: str | None = None,
    failed_values_query: str | None = None,
    connection_id: int | None = None,
    schema_id: int | None = None,
    purpose: str | None = None,
    recommended_function: str | None = None,
    code_object_id: int | None = None,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    from server.tools.common.errors import error_payload

    if step == "create_standard":
        return await _invoke_create_dq_rules(
            discover_cde_columns=discover_cde_columns,
            objects=objects,
            limit=limit,
            prefer_existing_rule=prefer_existing_rule,
            skip_duplicate_function_on_object=skip_duplicate_function_on_object,
            description_custom_field_name=description_custom_field_name,
            description_term_name=description_term_name,
            supplemental_criteria_text=supplemental_criteria_text,
            preferred_function_name=preferred_function_name,
            excluded_function_names=excluded_function_names,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )
    if step == "create_custom_sql":
        if not create_rule_name or not str(create_rule_name).strip():
            return error_payload(
                "create_custom_sql requires rule_name (or rule_name_for_create).",
                error_code="validation_required",
            )
        if objects is None:
            return error_payload(
                "create_custom_sql requires objects.",
                error_code="validation_required",
            )
        return await _invoke_create_sql_dq_rule(
            objects=objects,
            rule_name=create_rule_name,
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
    if step == "associate":
        resolved_id, resolve_err = await _resolve_dqrule_id_for_associate(dqrule_id, rule_name)
        if resolve_err is not None:
            return resolve_err
        if objects is None:
            return error_payload(
                "associate requires objects.",
                error_code="validation_required",
            )
        return await _invoke_associate_dq_rule_objects(
            dqrule_id=resolved_id,  # type: ignore[arg-type]
            objects=objects,
            skip_already_associated=skip_already_associated,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )
    return error_payload(
        "step must be create_standard | create_custom_sql | associate.",
        error_code="validation_invalid",
    )


async def _resolve_dqrule_id_for_associate(
    dqrule_id: int | None,
    rule_name: str | None,
) -> tuple[int | None, dict[str, Any] | None]:
    """Resolve associate target: explicit id, or internal lookup by rule_name."""
    from server.tools.common.errors import error_payload

    has_id = dqrule_id is not None and int(dqrule_id) > 0
    has_name = rule_name is not None and str(rule_name).strip() != ""
    if has_id and has_name:
        return None, error_payload(
            "Provide either dqrule_id or rule_name for associate, not both.",
            error_code="validation_mutually_exclusive",
        )
    if has_id:
        return int(dqrule_id), None  # type: ignore[arg-type]
    if not has_name:
        return None, error_payload(
            "associate requires dqrule_id or rule_name.",
            error_code="validation_required",
        )
    lookup = await _invoke_lookup_dq_rule(
        object_id=None,
        rule_name=rule_name,
        limit=MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
    )
    if isinstance(lookup, dict) and lookup.get("status_code"):
        return None, lookup
    data = lookup.get("data") if isinstance(lookup, dict) else None
    hits = data if isinstance(data, list) else []
    if not hits:
        return None, error_payload(
            f"No DQ rule found for rule_name={rule_name!r}.",
            error_code="not_found",
        )
    if len(hits) > 1:
        names = [
            str(h.get("objectName") or h.get("objectId"))
            for h in hits[:10]
            if isinstance(h, dict)
        ]
        return None, error_payload(
            "Multiple DQ rules matched rule_name; pass dqrule_id to disambiguate. "
            f"Matches: {', '.join(names)}",
            error_code="validation_ambiguous",
        )
    hit = hits[0]
    oid = hit.get("objectId") if isinstance(hit, dict) else None
    if oid is None:
        return None, error_payload("Lookup result missing objectId.")
    try:
        resolved = int(oid)
    except (TypeError, ValueError):
        return None, error_payload("Lookup result missing objectId.")
    if resolved <= 0:
        return None, error_payload("Lookup result missing objectId.")
    return resolved, None


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
    objects: _DqObjectsArgOpt,
    limit: int,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
    preferred_function_name: str | None = None,
    excluded_function_names: list[str] | None = None,
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
        preferred_function_name,
        excluded_function_names,
    )
    if "error" in payload:
        return payload
    try:
        async with ovaledge_client() as client:
            body = await client.post(MCP_PATH_ASSESS_CDE_DQ, payload)
            out = body if isinstance(body, dict) else {"data": body}
            out["formattedResponse"] = format_assess_cde_dq_response(out)
            out["agentInstruction"] = _DQ_ASSESS_AGENT_INSTRUCTION
            return out
    except OvalEdgeError as e:
        return map_ovaledge_error(e)


@logged_tool_invocation
async def _invoke_associate_dq_rule_objects(
    dqrule_id: int,
    objects: _DqObjectsArg,
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
    objects: _DqObjectsArgOpt,
    limit: int,
    prefer_existing_rule: bool,
    skip_duplicate_function_on_object: bool,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
    supplemental_criteria_text: str | None = None,
    preferred_function_name: str | None = None,
    excluded_function_names: list[str] | None = None,
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
        preferred_function_name,
        excluded_function_names,
    )
    if "error" in payload:
        return payload
    if not write_confirmed_by_user:
        assessment: dict[str, Any] | None = None
        if prefer_existing_rule:
            assess_payload = {
                key: value
                for key, value in payload.items()
                if key
                in {
                    "discoverCdeColumns",
                    "objects",
                    "limit",
                    "descriptionCustomFieldName",
                    "descriptionTermName",
                    "supplementalCriteriaText",
                    "preferredFunctionName",
                    "excludedFunctionNames",
                }
            }
            try:
                async with ovaledge_client() as client:
                    assess_body = await client.post(MCP_PATH_ASSESS_CDE_DQ, assess_payload)
                    assessment = (
                        assess_body if isinstance(assess_body, dict) else {"data": assess_body}
                    )
            except OvalEdgeError as e:
                return map_ovaledge_error(e)
        return format_create_dq_rules_confirmation_preview(payload, assessment)
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
    objects: _DqObjectsArgOpt,
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
    objects: _DqObjectsArgOpt,
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
        objects,
        rule_name,
        rule_query,
        stats_query,
        failed_values_query,
        code_object_id,
        recommended_function,
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
        return map_create_sql_dq_error(e)
