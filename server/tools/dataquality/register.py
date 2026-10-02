"""MCP tool registration for Data Quality workflows."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from server.constants import (
    MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC,
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    MCP_DQ_ASSESS_LIMIT_MAX,
    MCP_GLOSSARY_TAGS_LIMIT_DEFAULT,
)
from server.tools.common.annotations import GOVERNED_CREATE, GOVERNED_EXECUTE
from server.tools.common.confirm_gate import CONFIRMATION_TOKEN_PARAM_DESCRIPTION
from server.tools.dataquality.helpers import (
    _DESC_DQ_RULE_ADVISOR,
    _DESC_DQ_RULE_MANAGER,
)
from server.tools.dataquality.invocations import (
    _DqObjectsArgOpt,
    _invoke_dq_rule_advisor,
    _invoke_dq_rule_manager,
)


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
            Field(
                description=(
                    "create_standard: when true (default), associate to recommendedRuleId "
                    "if assess found a context-matching existing rule; otherwise create. "
                    "When false, always create a new rule."
                ),
                default=True,
            ),
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

