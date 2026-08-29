"""Helpers for Data Quality MCP tools."""

from __future__ import annotations

import ast
import json
from typing import Any

from server.constants import (
    MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC,
    MCP_DQ_ASSESS_LIMIT_MAX,
    MCP_DQ_OBJECT_TYPE_ALIASES,
    MCP_PATH_ASSESS_CDE_DQ,
    MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS,
    MCP_PATH_CREATE_DQ_RULES,
    MCP_PATH_CREATE_SQL_DQ_RULE,
    MCP_PATH_GENERATE_DQ_QUERIES,
    MCP_PATH_LOOKUP_DQ_RULES,
    MCP_PATH_VALIDATE_DQ_QUERIES,
    TOOL_DQ_RULE_ADVISOR,
    TOOL_DQ_RULE_MANAGER,
)
from server.tools.common.confirm_gate import attach_confirmation_token
from server.tools.common.descriptions import classify_tool_desc
from server.tools.common.errors import error_payload

_DQ_ASSOCIATE_CONFIRM_INSTRUCTION = (
    "Present formattedResponse and wait for explicit user approval before setting "
    "write_confirmed_by_user=true."
)
_DQ_CREATE_CONFIRM_INSTRUCTION = (
    "Present formattedResponse and wait for explicit user approval before setting "
    "write_confirmed_by_user=true."
)

_DQ_RETRY_POLICY = (
    "Retry policy: on error, auto-retry the last successful ladder step once. "
    "If it still fails, stop and ask the user whether to retry again. "
    "Retry again only if the user explicitly says yes; if they decline, stop. "
    "Never invent SQL or recommendedFunction names."
)

_DQ_OE_FUNCTION_ONLY = (
    "Only use exact recommendedFunction / recommendedFunctionCandidates names "
    "returned by the tool (real OvalEdge dqfunctiondef names). "
    "Never invent labels such as Max Length Check, Length Check, or similar. "
    "Do not recommend or create DBT_* / dbt_* functions — they are not in scope "
    "for MCP rule creation. Use the table-column catalog name from the tool "
    "(for example Non-Null Validation on oecolumn), not a file-column *fc variant "
    "and not legacy internal names."
)

_DESC_DQ_RULE_ADVISOR = classify_tool_desc(
    "Read/recommend DQ workflow (no rule create/associate).\n\n"
    f"step: assess | generate_query | validate_query | lookup\n"
    f"Backends: POST {MCP_PATH_ASSESS_CDE_DQ}, {MCP_PATH_GENERATE_DQ_QUERIES}, "
    f"{MCP_PATH_VALIDATE_DQ_QUERIES}; GET {MCP_PATH_LOOKUP_DQ_RULES}\n\n"
    f"**Not** {TOOL_DQ_RULE_MANAGER} — writes (create/associate) live there.\n\n"
    "Use exact recommendedFunction / candidate names from the tool; never invent "
    "labels. Ladder and retry policy: docs://ovaledge/mcp_workflows "
    "(CDE / DQ intelligence).\n\n"
    "lookup: resolve existing dqrule by rule_name or object_id (not asset search).\n\n"
    f"**objectType**: {MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC}. "
    "validate_query confirm gate before running SQL."
)

_DESC_DQ_RULE_MANAGER = classify_tool_desc(
    "DQ rule write workflow (create/associate only).\n\n"
    f"step: create_standard | create_custom_sql | associate\n"
    f"Backends: POST {MCP_PATH_CREATE_DQ_RULES}, {MCP_PATH_CREATE_SQL_DQ_RULE}, "
    f"{MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS}\n\n"
    f"**Not** {TOOL_DQ_RULE_ADVISOR} — assessment/SQL draft/validate/lookup live there.\n\n"
    "Use exact recommendedFunction / candidate names from the tool; never invent "
    "labels. Ladder and retry policy: docs://ovaledge/mcp_workflows "
    "(CDE / DQ intelligence).\n\n"
    "create_custom_sql requires recommended_function = recommendedFunction name from "
    "generate_query/assess (reject blank/CUSTOM_SQL). "
    "associate: dqrule_id or rule_name + objects.\n\n"
    f"**objectType**: {MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC}. "
    "Confirm gate on every step. Audit OE-MCP. "
    "Details: docs://ovaledge/mcp_workflows"
)

_DQ_ASSESS_AGENT_INSTRUCTION = (
    "Follow the DQ ladder: present recommendedFunction and "
    "recommendedFunctionCandidates (exact OE names only). "
    "Prefer associate, then create_standard with an exact candidate name. "
    "If Not Identified but candidates are present, ask the user to pick one "
    "candidate — do not invent a function name. "
    "Only after user confirms custom SQL when no usable catalog candidate remains, "
    f"call {TOOL_DQ_RULE_ADVISOR} step=generate_query — never hand-write SQL. "
    f"{_DQ_OE_FUNCTION_ONLY} {_DQ_RETRY_POLICY}"
)

_DQ_CREATE_SQL_LOOP_BACK = (
    f"Auto-retry once: call {TOOL_DQ_RULE_ADVISOR} step=generate_query (or step=assess), "
    "copy the returned recommendedFunction name into recommended_function, then "
    "validate_query → create_custom_sql. Do not invent function names or SQL. "
    "If that retry still fails, stop and ask the user whether to retry again; "
    "retry only if they say yes, otherwise stop."
)

_INVALID_RECOMMENDED_FUNCTION_PLACEHOLDERS = frozenset(
    {
        "custom_sql",
        "customsql",
        "not identified",
        "not_identified",
        "none",
        "null",
        "n/a",
        "na",
        "unknown",
    }
)

# Dissolved tool _DESC_* aliases removed — use _DESC_DQ_RULE_ADVISOR / _DESC_DQ_RULE_MANAGER.


def validate_lookup_dq_rule_args(
    object_id: int | None,
    rule_name: str | None,
) -> dict[str, Any] | None:
    has_id = object_id is not None and object_id > 0
    has_name = rule_name is not None and str(rule_name).strip() != ""
    if has_id and has_name:
        return error_payload(
            "Provide either rule_name or object_id for DQ rule lookup, not both.",
            error_code="validation_mutually_exclusive",
        )
    if not has_id and not has_name:
        return error_payload(
            "Provide rule_name or object_id.",
            error_code="validation_required",
        )
    return None


def normalize_dq_object_type(object_type: str | None) -> str | None:
    if object_type is None or not str(object_type).strip():
        return None
    key = str(object_type).strip().lower()
    return MCP_DQ_OBJECT_TYPE_ALIASES.get(key)


def _coerce_dq_objects_arg(
    objects: Any,
) -> tuple[list[Any] | None, dict[str, Any] | None]:
    """
    Normalize agent/transport shapes for ``objects`` into a Python list.

    Hosts sometimes pass a JSON *string* (or a bare dict). Iterating a string would
    treat each character as an entry and fail with a misleading objects[0] error.
    """
    if objects is None:
        return [], None
    if isinstance(objects, dict):
        return [objects], None
    if isinstance(objects, list):
        return objects, None
    if isinstance(objects, str):
        text = objects.strip()
        if not text:
            return [], None
        parsed: Any = None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed = None
        if isinstance(parsed, dict):
            return [parsed], None
        if isinstance(parsed, list):
            return parsed, None
        return None, error_payload(
            "objects must be a JSON array of {objectId, objectType} "
            '(e.g. [{"objectId": 123, "objectType": "oecolumn"}]), '
            "not a plain string. If you pass JSON, pass it as an array value — "
            "do not stringify the array.",
            error_code="validation_objects_shape",
        )
    return None, error_payload(
        "objects must be a list of {objectId, objectType} "
        f"(got {type(objects).__name__}).",
        error_code="validation_objects_shape",
    )


def _normalize_dq_api_objects(
    objects: Any,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Validate and normalize catalog object refs for DQ assess/create payloads."""
    refs, coerce_err = _coerce_dq_objects_arg(objects)
    if coerce_err is not None:
        return None, coerce_err
    assert refs is not None
    api_objects: list[dict[str, Any]] = []
    for idx, raw in enumerate(refs):
        if not isinstance(raw, dict):
            return None, error_payload(
                f"objects[{idx}] must be an object with objectId and objectType."
            )
        oid = raw.get("objectId", raw.get("object_id"))
        otype_raw = raw.get("objectType", raw.get("object_type"))
        if oid is None:
            return None, error_payload(f"objects[{idx}] requires objectId (or object_id).")
        try:
            oid_int = int(oid)
        except (TypeError, ValueError):
            return None, error_payload(f"objects[{idx}].objectId must be a positive integer.")
        if oid_int <= 0:
            return None, error_payload(f"objects[{idx}].objectId must be a positive integer.")
        otype = normalize_dq_object_type(
            str(otype_raw) if otype_raw is not None else None
        )
        if otype is None:
            return None, error_payload(
                f"objects[{idx}].objectType must be one of {MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC}, "
                f"got {otype_raw!r}.",
            )
        api_objects.append({"objectId": oid_int, "objectType": otype})
    return api_objects, None


def validate_assess_cde_dq_args(
    discover_cde_columns: bool,
    objects: Any,
) -> dict[str, Any] | None:
    refs, err = _normalize_dq_api_objects(objects)
    if err is not None:
        return err
    if not refs and not discover_cde_columns:
        return error_payload(
            "Provide objects from search_catalog_assets, or set discover_cde_columns=true "
            "to discover CDE columns.",
        )
    return None


def build_assess_cde_dq_payload(
    discover_cde_columns: bool,
    objects: Any,
    limit: int,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
    preferred_function_name: str | None = None,
    excluded_function_names: list[str] | None = None,
) -> dict[str, Any]:
    capped = min(max(limit, 1), MCP_DQ_ASSESS_LIMIT_MAX)
    payload: dict[str, Any] = {
        "discoverCdeColumns": discover_cde_columns,
        "limit": capped,
    }
    field_name = strip_or_none_description_field(description_custom_field_name)
    if field_name is not None:
        payload["descriptionCustomFieldName"] = field_name
    term_name = strip_or_none_description_field(description_term_name)
    if term_name is not None:
        payload["descriptionTermName"] = term_name
    preferred = strip_or_none_description_field(preferred_function_name)
    if preferred is not None:
        payload["preferredFunctionName"] = preferred
    excluded = _normalize_excluded_function_names(excluded_function_names)
    if excluded:
        payload["excludedFunctionNames"] = excluded
    api_objects, err = _normalize_dq_api_objects(objects)
    if err is not None:
        return err
    if api_objects:
        payload["objects"] = api_objects
    return payload


def _normalize_excluded_function_names(
    excluded_function_names: list[str] | None,
) -> list[str]:
    if not excluded_function_names:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for name in excluded_function_names:
        trimmed = strip_or_none_description_field(name if isinstance(name, str) else None)
        if trimmed is None:
            continue
        key = trimmed.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(trimmed)
    return out


def strip_or_none_description_field(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed or None


def _is_dbt_function_name(name: Any) -> bool:
    text = str(name or "").strip().lower()
    return text.startswith("dbt_") or text.startswith("dbt ")


def format_assess_cde_dq_response(body: dict[str, Any]) -> str:
    """Human-readable summary highlighting description gaps and function candidates."""
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return "CDE DQ assessment completed."
    lines: list[str] = []
    count = data.get("assessedCount")
    if count is not None:
        lines.append(f"Assessed {count} object(s).")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        return "\n".join(lines) if lines else "CDE DQ assessment completed."
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("tableColumnName", "?")
        oid = row.get("objectId", "?")
        otype = row.get("objectType", "?")
        source = row.get("descriptionSource", "?")
        lines.append(f"- {name} ({otype}, id={oid}): descriptionSource={source}")
        business_rule = row.get("businessRule")
        if isinstance(business_rule, str) and business_rule.strip():
            lines.append(f"  businessRule: {business_rule.strip()}")
        message = row.get("descriptionMessage")
        if isinstance(message, str) and message.strip():
            # When Business Rule text is present, the long "add a catalog description"
            # message misleads agents into inventing custom SQL — keep it short.
            if isinstance(business_rule, str) and business_rule.strip() and (
                "No business description is available" in message
                or "Add a catalog description" in message
            ):
                lines.append(
                    "  No catalog/wiki description; matching uses businessRule text above."
                )
            else:
                lines.append(f"  {message.strip()}")
        elif source == "none":
            fields = row.get("availableCustomFields")
            if isinstance(fields, list) and fields:
                lines.append(f"  Available custom fields: {', '.join(str(f) for f in fields)}")
        rec_fn = row.get("recommendedFunction")
        workflow = row.get("recommendedWorkflow")
        if isinstance(rec_fn, str) and rec_fn.strip() and not _is_dbt_function_name(rec_fn):
            wf = f" [{workflow}]" if isinstance(workflow, str) and workflow.strip() else ""
            lines.append(f"  recommendedFunction: `{rec_fn}`{wf}")
        candidates = row.get("recommendedFunctionCandidates")
        visible_candidates = [
            cand
            for cand in candidates
            if isinstance(candidates, list)
            and isinstance(cand, dict)
            and not _is_dbt_function_name(cand.get("functionName", ""))
        ] if isinstance(candidates, list) else []
        if visible_candidates:
            lines.append(
                "  recommendedFunctionCandidates (pick one, or exclude to get alternatives):"
            )
            for cand in visible_candidates[:5]:
                cname = cand.get("functionName", "?")
                score = cand.get("score")
                reason = cand.get("matchReason", "")
                score_bit = f", score={score}" if score is not None else ""
                reason_bit = f", {reason}" if isinstance(reason, str) and reason.strip() else ""
                lines.append(f"    - `{cname}`{score_bit}{reason_bit}")
            if isinstance(workflow, str) and workflow.strip().lower() == "custom_sql":
                lines.append(
                    "  Next: after user confirms custom SQL, call "
                    f"{TOOL_DQ_RULE_ADVISOR} step=generate_query → validate_query → "
                    f"{TOOL_DQ_RULE_MANAGER} step=create_custom_sql with recommendedFunction "
                    "verbatim. Never hand-write SQL. Do not use create_standard for an "
                    "OEQUERY SQL function. IN/NOT IN or allowed-value sets use "
                    "SQL Values Contains, not SQL Exact Value."
                )
            else:
                not_id = (
                    isinstance(rec_fn, str)
                    and rec_fn.strip().lower() == "not identified"
                )
                if not_id:
                    lines.append(
                        "  recommendedFunction is Not Identified, but candidates above are "
                        "real OE catalog functions — ask the user to pick one exact name "
                        "for create_standard. Never invent names (Max Length Check, etc.)."
                    )
                lines.append(
                    f"  Next: {TOOL_DQ_RULE_MANAGER} step=create_standard with "
                    "preferred_function_name = one exact candidate / recommendedFunction "
                    "name from the list above. If none fit: re-call "
                    f"{TOOL_DQ_RULE_ADVISOR} step=assess with excluded_function_names."
                )
        elif (
            isinstance(rec_fn, str)
            and rec_fn.strip().lower() == "not identified"
        ) or (
            isinstance(workflow, str) and workflow.strip().lower() == "custom_sql"
        ):
            if (
                isinstance(rec_fn, str)
                and rec_fn.strip()
                and rec_fn.strip().lower() != "not identified"
                and not _is_dbt_function_name(rec_fn)
            ):
                lines.append(
                    f"  Next (custom SQL): use recommendedFunction `{rec_fn}` with "
                    f"{TOOL_DQ_RULE_ADVISOR} step=generate_query → validate_query → "
                    f"{TOOL_DQ_RULE_MANAGER} step=create_custom_sql. "
                    "Never invent a different function name or hand-write SQL."
                )
            elif isinstance(business_rule, str) and business_rule.strip():
                lines.append(
                    "  No auto-picked recommendedFunction. "
                    "If recommendedFunctionCandidates are listed above, ask the user to "
                    "pick one exact OE name for create_standard — never invent names "
                    "(e.g. Max Length Check). "
                    "Only if the user rejects all candidates and confirms custom SQL, "
                    f"call {TOOL_DQ_RULE_ADVISOR} step=generate_query."
                )
            else:
                lines.append(
                    "  No recommendedFunction returned. Ask the user to confirm custom SQL "
                    f"before calling {TOOL_DQ_RULE_ADVISOR} step=generate_query; "
                    "never invent a function name or hand-write SQL."
                )
        existing_rules = row.get("existingRulesForFunction")
        if isinstance(existing_rules, list) and existing_rules:
            lines.append(
                "  existingRulesForFunction (user must choose → associate before create):"
            )
            for rule in existing_rules:
                if not isinstance(rule, dict):
                    continue
                lines.append(f"    {_format_existing_rule_choice(rule)}")
    lines.append("")
    lines.append(
        "Ladder reminder: associate existing same-function rules first; else "
        "create_standard; custom SQL only after user confirmation when no "
        "recommendedFunction remains — then generate → validate → create. "
        f"{_DQ_RETRY_POLICY}"
    )
    return "\n".join(lines)


def validate_associate_dq_rule_objects_args(
    dqrule_id: int | None,
    objects: Any,
) -> dict[str, Any] | None:
    if dqrule_id is None or int(dqrule_id) <= 0:
        return error_payload("dqrule_id must be a positive integer.")
    refs, err = _normalize_dq_api_objects(objects)
    if err is not None:
        return err
    if not refs:
        return error_payload("At least one object with objectId and objectType is required.")
    return None


def format_associate_dq_rule_objects_response(body: dict[str, Any]) -> str:
    """Human-readable summary of associate_dq_rule_objects API result."""
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return "DQ rule association completed."
    lines: list[str] = []
    rule_id = data.get("dqruleId")
    if rule_id is not None:
        lines.append(f"DQ rule id: {rule_id}")
    status_message = data.get("statusMessage")
    if isinstance(status_message, str) and status_message.strip():
        lines.append(f"Outcome: {status_message.strip()}")
    associated = data.get("associatedCount", 0)
    skipped = data.get("skippedCount", 0)
    failed = data.get("failedCount", 0)
    lines.append(
        f"Summary: {associated} associated, {skipped} skipped, {failed} failed."
    )
    rows = data.get("rows")
    if isinstance(rows, list) and rows:
        lines.append("Per object:")
        for row in rows:
            if not isinstance(row, dict):
                continue
            oid = row.get("objectId", "?")
            otype = row.get("objectType", "?")
            status = row.get("status", "?")
            message = row.get("message")
            detail = f" — {message}" if isinstance(message, str) and message.strip() else ""
            lines.append(f"  - {oid} ({otype}): {status}{detail}")
    return "\n".join(lines)


def format_create_dq_rules_response(body: dict[str, Any]) -> str:
    """Human-readable summary of create_dq_rules API result."""
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return "DQ rule create/associate completed."
    lines: list[str] = []
    created = data.get("createdCount", 0)
    associated = data.get("associatedCount", 0)
    skipped = data.get("skippedCount", 0)
    failed = data.get("failedCount", 0)
    lines.append(
        f"Summary: {created} created, {associated} associated, "
        f"{skipped} skipped, {failed} failed."
    )
    rows = data.get("rows")
    if isinstance(rows, list) and rows:
        lines.append("Per object:")
        for row in rows:
            if not isinstance(row, dict):
                continue
            oid = row.get("objectId", "?")
            otype = row.get("objectType", "?")
            status = row.get("status", "?")
            rule_name = row.get("ruleName")
            dqrule_id = row.get("dqruleId")
            object_linked = row.get("objectAssociated")
            parts = [f"  - {oid} ({otype}): {status}"]
            if isinstance(rule_name, str) and rule_name.strip():
                parts.append(f"rule={rule_name}")
            if dqrule_id is not None:
                parts.append(f"dqruleId={dqrule_id}")
            if object_linked is True or status == "created":
                parts.append("object linked")
            criteria_source = row.get("criteriaSource")
            if isinstance(criteria_source, str) and criteria_source.strip():
                parts.append(f"criteriaSource={criteria_source.strip()}")
            criteria_message = row.get("criteriaMessage")
            if isinstance(criteria_message, str) and criteria_message.strip():
                parts.append(f"— Warning: {criteria_message.strip()}")
            message = row.get("message")
            if isinstance(message, str) and message.strip():
                parts.append(f"— {message.strip()}")
            lines.append(" ".join(parts))
    return "\n".join(lines)


def _summarize_dq_object_refs(objects: list[dict[str, Any]] | None) -> list[str]:
    lines: list[str] = []
    if not isinstance(objects, list):
        return lines
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        oid = obj.get("objectId", "?")
        otype = obj.get("objectType", "?")
        lines.append(f"- **{otype}** (id {oid})")
    return lines


def format_associate_dq_rule_confirmation_preview(body: dict[str, Any]) -> dict[str, Any]:
    rule_id = body.get("dqruleId")
    skip = body.get("skipAlreadyAssociated")
    object_lines = _summarize_dq_object_refs(body.get("objects"))
    objects_block = "\n".join(object_lines) if object_lines else "- (no objects)"
    preview = {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_update",
        "doNotUpdate": True,
        "writeConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm DQ rule association**\n\n"
            f"- **DQ rule id:** {rule_id}\n"
            f"- **skip_already_associated:** {skip}\n"
            f"**Objects:**\n{objects_block}\n\n"
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same dqrule_id, objects, and skip_already_associated."
        ),
        "agentInstruction": _DQ_ASSOCIATE_CONFIRM_INSTRUCTION,
        "pendingUpdate": body,
    }
    return attach_confirmation_token(preview, body)


def format_create_dq_rules_confirmation_preview(
    body: dict[str, Any],
    assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    discover = body.get("discoverCdeColumns")
    prefer = body.get("preferExistingRule")
    skip_dup = body.get("skipDuplicateFunctionOnObject")
    limit = body.get("limit")
    field_name = body.get("descriptionCustomFieldName")
    term_name = body.get("descriptionTermName")
    object_lines = _summarize_dq_object_refs(body.get("objects"))
    objects_block = "\n".join(object_lines) if object_lines else "- (discover mode or empty)"
    field_line = ""
    if isinstance(field_name, str) and field_name.strip():
        field_line = f"\n- **description_custom_field_name:** {field_name.strip()}"
    if isinstance(term_name, str) and term_name.strip():
        field_line += f"\n- **description_term_name:** {term_name.strip()}"
    assessment_data = assessment.get("data", assessment) if isinstance(assessment, dict) else {}
    assessment_rows = (
        assessment_data.get("rows", []) if isinstance(assessment_data, dict) else []
    )
    action_lines: list[str] = []
    selection_lines: list[str] = []
    selection_choices: list[dict[str, Any]] = []
    for row in assessment_rows if isinstance(assessment_rows, list) else []:
        if not isinstance(row, dict):
            continue
        object_id = row.get("objectId")
        object_type = row.get("objectType")
        existing_rules = row.get("existingRulesForFunction")
        if prefer and isinstance(existing_rules, list) and existing_rules:
            selection_lines.append(f"- `{object_type}:{object_id}`:")
            selection_choices.append(
                {
                    "objectId": object_id,
                    "objectType": object_type,
                    "rules": [rule for rule in existing_rules if isinstance(rule, dict)],
                }
            )
            selection_lines.extend(
                f"  {_format_existing_rule_choice(rule)}"
                for rule in existing_rules
                if isinstance(rule, dict)
            )
            continue
        action_lines.append(
            f"- `{object_type}:{object_id}`: create a new rule "
            "(no existing rule uses the recommended function)"
        )
    if selection_lines:
        return {
            "ok": True,
            "awaitingUserConfirmation": True,
            "workflowPhase": "select_existing_rule",
            "doNotCreate": True,
            "requiresRuleSelection": True,
            "writeConfirmedByUser": False,
            "formattedResponse": (
                "**Choose an existing DQ rule or explicitly request a new rule**\n\n"
                "The following active rules use the recommended function:\n"
                f"{chr(10).join(selection_lines)}\n\n"
                "Ask the user to choose a DQ rule ID. For a selected rule, call "
                f"`{TOOL_DQ_RULE_MANAGER}` step=associate and use its confirmation flow. "
                "If the user explicitly wants a new rule instead, re-call "
                f"`{TOOL_DQ_RULE_MANAGER}` step=create_standard with "
                "`prefer_existing_rule=false` to receive a create confirmation preview."
            ),
            "agentInstruction": (
                "Do not create or auto-select. Present every same-function rule and wait for "
                "the user to choose a dqruleId, or explicitly choose creation."
            ),
            "existingRuleChoices": selection_choices,
            "pendingCreate": body,
        }
    planned_actions = (
        "\n".join(action_lines)
        if action_lines
        else "- Assessment returned no actionable objects."
    )
    preview = {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_create",
        "doNotCreate": True,
        "writeConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm DQ rule create/associate**\n\n"
            f"- **discover_cde_columns:** {discover}\n"
            f"- **prefer_existing_rule:** {prefer}\n"
            f"- **skip_duplicate_function_on_object:** {skip_dup}\n"
            f"- **limit:** {limit}"
            f"{field_line}\n"
            f"**Objects:**\n{objects_block}\n\n"
            f"**Planned actions:**\n{planned_actions}\n\n"
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same discover_cde_columns, objects, limit, flags, and optional "
            "description_term_name or description_custom_field_name."
        ),
        "agentInstruction": _DQ_CREATE_CONFIRM_INSTRUCTION,
        "pendingCreate": body,
    }
    return attach_confirmation_token(preview, body)


def _format_existing_rule_choice(rule: dict[str, Any]) -> str:
    rule_id = rule.get("dqruleId", "?")
    name = rule.get("name", "?")
    purpose = rule.get("purpose")
    similarity = rule.get("purposeSimilarity")
    associated = rule.get("associatedToObject")
    success_op = rule.get("successOperator")
    success_values = [
        str(value)
        for value in (rule.get("successValue1"), rule.get("successValue2"))
        if value not in (None, "")
    ]
    input_op = rule.get("inputOperator")
    input_values = [
        str(value)
        for value in (rule.get("inputValue1"), rule.get("inputValue2"))
        if value not in (None, "")
    ]
    details = [f"ID {rule_id}: **{name}**"]
    if isinstance(purpose, str) and purpose.strip():
        details.append(f"purpose={purpose.strip()}")
    if success_op or success_values:
        details.append(
            f"success={success_op or '?'}"
            + (f" ({', '.join(success_values)})" if success_values else "")
        )
    if input_op or input_values:
        details.append(
            f"input={input_op or '?'}"
            + (f" ({', '.join(input_values)})" if input_values else "")
        )
    if similarity is not None:
        details.append(f"purposeSimilarity={similarity}")
    if associated is True:
        details.append("already associated")
    return " — ".join(details)


def build_associate_dq_rule_objects_payload(
    dqrule_id: int,
    objects: Any,
    skip_already_associated: bool,
) -> dict[str, Any]:
    built = build_assess_cde_dq_payload(False, objects, 1)
    if "error" in built:
        return built
    payload: dict[str, Any] = {
        "dqruleId": int(dqrule_id),
        "skipAlreadyAssociated": skip_already_associated,
    }
    if built.get("objects"):
        payload["objects"] = built["objects"]
    return payload


def validate_create_dq_rules_args(
    discover_cde_columns: bool,
    objects: Any,
) -> dict[str, Any] | None:
    return validate_assess_cde_dq_args(discover_cde_columns, objects)


def build_create_dq_rules_payload(
    discover_cde_columns: bool,
    objects: Any,
    limit: int,
    prefer_existing_rule: bool,
    skip_duplicate_function_on_object: bool,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
    supplemental_criteria_text: str | None = None,
    preferred_function_name: str | None = None,
    excluded_function_names: list[str] | None = None,
) -> dict[str, Any]:
    built = build_assess_cde_dq_payload(
        discover_cde_columns,
        objects,
        limit,
        description_custom_field_name,
        description_term_name,
        preferred_function_name,
        excluded_function_names,
    )
    if "error" in built:
        return built
    payload: dict[str, Any] = {
        "discoverCdeColumns": discover_cde_columns,
        "preferExistingRule": prefer_existing_rule,
        "skipDuplicateFunctionOnObject": skip_duplicate_function_on_object,
        "limit": built.get("limit", limit),
    }
    if built.get("descriptionCustomFieldName"):
        payload["descriptionCustomFieldName"] = built["descriptionCustomFieldName"]
    if built.get("descriptionTermName"):
        payload["descriptionTermName"] = built["descriptionTermName"]
    if built.get("preferredFunctionName"):
        payload["preferredFunctionName"] = built["preferredFunctionName"]
    if built.get("excludedFunctionNames"):
        payload["excludedFunctionNames"] = built["excludedFunctionNames"]
    supplemental = strip_or_none_description_field(supplemental_criteria_text)
    if supplemental is not None:
        payload["supplementalCriteriaText"] = supplemental
    if built.get("objects"):
        payload["objects"] = built["objects"]
    return payload


def _unwrap_api_data(body: Any) -> Any:
    if isinstance(body, dict) and "data" in body:
        return body.get("data")
    return body


_DQ_SQL_VALIDATE_CONFIRM_INSTRUCTION = (
    "Present formattedResponse and wait for explicit user approval before setting "
    "write_confirmed_by_user=true to execute SQL on the connection."
)
_DQ_SQL_CREATE_CONFIRM_INSTRUCTION = (
    "Present formattedResponse and wait for explicit user approval before setting "
    "write_confirmed_by_user=true."
)

_REUSE_ASSOCIATE_EXISTING_DQR = "associate_existing_dqr"
_REUSE_CREATE_FROM_CODE = "create_from_code"
_REUSE_ALREADY_ASSOCIATED = "already_associated"


def _sql_context_ids(data: dict[str, Any]) -> tuple[int | None, int | None]:
    context = data.get("context")
    if not isinstance(context, dict):
        return None, None
    connection_id = context.get("connectionId")
    schema_id = context.get("schemaId")
    conn = int(connection_id) if connection_id is not None and connection_id > 0 else None
    schema = int(schema_id) if schema_id is not None and schema_id > 0 else None
    return conn, schema


def _format_sql_context_lines(data: dict[str, Any]) -> list[str]:
    connection_id, schema_id = _sql_context_ids(data)
    if connection_id is None or schema_id is None:
        return []
    return [
        f"- **connection_id:** {connection_id} (for {TOOL_DQ_RULE_ADVISOR} step=validate_query)",
        f"- **schema_id:** {schema_id} (for {TOOL_DQ_RULE_ADVISOR} step=validate_query)",
    ]


def _validate_queries_context_hint(data: dict[str, Any]) -> str:
    connection_id, schema_id = _sql_context_ids(data)
    if connection_id is None or schema_id is None:
        return (
            f"Pass connection_id and schema_id from data.context when calling "
            f"{TOOL_DQ_RULE_ADVISOR} step=validate_query."
        )
    return (
        f"Call {TOOL_DQ_RULE_ADVISOR} step=validate_query with connection_id={connection_id}, "
        f"schema_id={schema_id}, and all three queries."
    )


def _resolve_dqrule_id_from_code_match(data: dict[str, Any]) -> int | None:
    rec_id = data.get("recommendedCodeObjectId")
    matches = data.get("matchingCodeObjects")
    if not isinstance(matches, list):
        return None
    for item in matches:
        if not isinstance(item, dict):
            continue
        if rec_id is not None and item.get("codeObjectId") == rec_id:
            dqrule_id = item.get("dqruleId")
            return int(dqrule_id) if dqrule_id is not None and dqrule_id > 0 else None
    first = matches[0] if matches else None
    if isinstance(first, dict):
        dqrule_id = first.get("dqruleId")
        return int(dqrule_id) if dqrule_id is not None and dqrule_id > 0 else None
    return None


def _append_generate_query_preview_lines(lines: list[str], data: dict[str, Any]) -> None:
    if data.get("ruleQuery"):
        lines.append("**Rule query** (preview):")
        lines.append(f"```sql\n{data['ruleQuery']}\n```")
    if data.get("statsQuery"):
        lines.append("**Stats query** (preview):")
        lines.append(f"```sql\n{data['statsQuery']}\n```")
    if data.get("failedValuesQuery"):
        lines.append("**Failed-values query** (preview):")
        lines.append(f"```sql\n{data['failedValuesQuery']}\n```")


def _agent_instruction_for_code_found(data: dict[str, Any]) -> str:
    action = str(data.get("recommendedReuseAction") or "")
    code_id = data.get("recommendedCodeObjectId")
    dqrule_id = _resolve_dqrule_id_from_code_match(data)
    if action == _REUSE_ALREADY_ASSOCIATED:
        return (
            "Target is already associated to the matching DQ rule. "
            f"Do not call {TOOL_DQ_RULE_ADVISOR} step=validate_query or "
            f"{TOOL_DQ_RULE_MANAGER} step=create_custom_sql."
        )
    if action == _REUSE_ASSOCIATE_EXISTING_DQR:
        rule_hint = f"dqrule_id={dqrule_id}" if dqrule_id else "dqrule_id from data"
        return (
            f"Call {TOOL_DQ_RULE_MANAGER} step=associate with {rule_hint} and the target "
            f"object(s), confirm gate required. Do not call {TOOL_DQ_RULE_ADVISOR} "
            f"step=validate_query or {TOOL_DQ_RULE_MANAGER} step=create_custom_sql."
        )
    if action == _REUSE_CREATE_FROM_CODE:
        code_hint = f"code_object_id={code_id}" if code_id else "code_object_id from data"
        conn, schema = _sql_context_ids(data)
        ctx = ""
        if conn is not None and schema is not None:
            ctx = f", connection_id={conn}, schema_id={schema}"
        return (
            f"Call {TOOL_DQ_RULE_MANAGER} step=create_custom_sql with "
            f"{code_hint}{ctx} and rule_name; confirm gate required. "
            "Skip validate unless the user explicitly requests it."
        )
    return (
        f"Review recommendedReuseAction in data. Prefer "
        f"{TOOL_DQ_RULE_MANAGER} step=associate or "
        f"{TOOL_DQ_RULE_MANAGER} step=create_custom_sql with "
        "code_object_id before generating new SQL."
    )


def validate_generate_dq_queries_args(
    objects: Any,
) -> dict[str, Any] | None:
    refs, err = _normalize_dq_api_objects(objects)
    if err is not None:
        return err
    if not refs:
        return error_payload(
            "At least one object with objectId and objectType is required.",
        )
    return None


def build_generate_dq_queries_payload(
    objects: Any,
    business_rule: str | None,
    business_description: str | None,
) -> dict[str, Any]:
    built = build_assess_cde_dq_payload(False, objects, 1)
    if "error" in built:
        return built
    api_objects = built.get("objects") or []
    if not api_objects:
        return error_payload(
            "At least one object with objectId and objectType is required.",
        )
    target = api_objects[0]
    payload: dict[str, Any] = {
        "objectId": target["objectId"],
        "objectType": target.get("objectType", "oecolumn"),
    }
    br = strip_or_none_description_field(business_rule)
    bd = strip_or_none_description_field(business_description)
    if br is not None:
        payload["businessRule"] = br
    if bd is not None:
        payload["businessDescription"] = bd
    return payload


def format_generate_dq_queries_response(body: dict[str, Any]) -> dict[str, Any]:
    data = _unwrap_api_data(body)
    if not isinstance(data, dict):
        return body if isinstance(body, dict) else {"ok": True, "data": body}
    status = str(data.get("status", ""))
    lines = [
        f"**Generate SQL queries** — status: `{status}`",
        "",
    ]
    if data.get("recommendedFunction"):
        lines.append(f"- recommendedFunction: `{data.get('recommendedFunction')}`")
    if data.get("recommendedWorkflow"):
        lines.append(f"- Workflow: `{data.get('recommendedWorkflow')}`")
    if status == "cross_schema_blocked":
        message = data.get("message", "")
        return {
            "ok": True,
            "workflowPhase": "generate_queries",
            "formattedResponse": (
                f"**Generate SQL queries** — status: `{status}`\n\n"
                f"{message or 'Cross-schema dependent rules cannot be created.'}"
            ),
            "data": data,
            "agentInstruction": (
                f"Do not call {TOOL_DQ_RULE_ADVISOR} step=validate_query or "
                f"{TOOL_DQ_RULE_MANAGER} step=create_custom_sql. "
                "Cross-schema dependent rules are not supported for custom SQL."
            ),
        }
    if status == "function_based":
        lines.append(
            f"This DQ function is not oequery-based. Use "
            f"{TOOL_DQ_RULE_MANAGER} step=create_standard "
            f"(or {TOOL_DQ_RULE_ADVISOR} step=assess → "
            f"{TOOL_DQ_RULE_MANAGER} step=associate) instead."
        )
        return {
            "ok": True,
            "workflowPhase": "generate_queries",
            "formattedResponse": "\n".join(lines),
            "data": data,
            "agentInstruction": (
                f"Do not call {TOOL_DQ_RULE_ADVISOR} step=validate_query or "
                f"{TOOL_DQ_RULE_MANAGER} step=create_custom_sql. "
                f"Route to {TOOL_DQ_RULE_MANAGER} step=create_standard or "
                "step=associate."
            ),
        }
    if status == "function_not_identified":
        lines.append(
            f"No DQ function could be resolved. Run "
            f"{TOOL_DQ_RULE_ADVISOR} step=assess first or add "
            "Function Name to business description."
        )
        return {
            "ok": True,
            "workflowPhase": "generate_queries",
            "formattedResponse": "\n".join(lines),
            "data": data,
            "agentInstruction": (
                "No OEQUERY function was resolved for custom SQL. "
                f"Retry {TOOL_DQ_RULE_ADVISOR} step=generate_query once. "
                "Do not invent a function name. If it still fails, stop and ask the user."
            ),
        }
    context_lines = _format_sql_context_lines(data)
    if context_lines:
        lines.extend(context_lines)
    if status == "code_found":
        action = data.get("recommendedReuseAction") or "reuse"
        lines.append("")
        lines.append(
            f"Existing code object **{data.get('recommendedCodeObjectId')}** matched — "
            f"recommended action: `{action}`."
        )
        _append_generate_query_preview_lines(lines, data)
        out: dict[str, Any] = {
            "ok": True,
            "workflowPhase": "generate_queries",
            "formattedResponse": "\n".join(lines),
            "data": data,
            "agentInstruction": _agent_instruction_for_code_found(data),
        }
        connection_id, schema_id = _sql_context_ids(data)
        if connection_id is not None:
            out["connectionId"] = connection_id
        if schema_id is not None:
            out["schemaId"] = schema_id
        return out
    lines.append("")
    _append_generate_query_preview_lines(lines, data)
    if data.get("reuseExistingCode"):
        action = data.get("recommendedReuseAction") or "reuse"
        lines.append(
            f"Existing code object **{data.get('recommendedCodeObjectId')}** matched — "
            f"recommended action: `{action}`."
        )
    elif data.get("matchingCodeObjects"):
        lines.append("Matching code objects found — prefer reuse before create.")
    validate_hint = _validate_queries_context_hint(data)
    rec_fn = data.get("recommendedFunction")
    rf_bit = (
        f" Copy recommendedFunction `{rec_fn}` into create_custom_sql "
        "recommended_function."
        if isinstance(rec_fn, str) and rec_fn.strip()
        else " Copy recommendedFunction from this response into create_custom_sql "
        "recommended_function."
    )
    out = {
        "ok": True,
        "workflowPhase": "generate_queries",
        "formattedResponse": "\n".join(lines),
        "data": data,
        "agentInstruction": (
            f"{validate_hint} Confirm gate required.{rf_bit} "
            "Never hand-write SQL or invent function names. "
            f"{_DQ_RETRY_POLICY} "
            f"After canCreateRule is true, call {TOOL_DQ_RULE_MANAGER} "
            "step=create_custom_sql with user approval."
        ),
    }
    connection_id, schema_id = _sql_context_ids(data)
    if connection_id is not None:
        out["connectionId"] = connection_id
    if schema_id is not None:
        out["schemaId"] = schema_id
    return out


def validate_validate_dq_queries_args(
    connection_id: int | None,
    schema_id: int | None,
    rule_query: str | None,
    stats_query: str | None,
    failed_values_query: str | None,
) -> dict[str, Any] | None:
    if connection_id is None or connection_id <= 0 or schema_id is None or schema_id <= 0:
        return error_payload("connection_id and schema_id are required.")
    if not strip_or_none_description_field(rule_query):
        return error_payload("rule_query is required.")
    if not strip_or_none_description_field(stats_query):
        return error_payload("stats_query is required.")
    if not strip_or_none_description_field(failed_values_query):
        return error_payload("failed_values_query is required.")
    return None


def build_validate_dq_queries_payload(
    connection_id: int,
    schema_id: int,
    rule_query: str,
    stats_query: str,
    failed_values_query: str,
) -> dict[str, Any]:
    return {
        "connectionId": int(connection_id),
        "schemaId": int(schema_id),
        "ruleQuery": rule_query.strip(),
        "statsQuery": stats_query.strip(),
        "failedValuesQuery": failed_values_query.strip(),
    }


def format_validate_dq_queries_confirmation_preview(
    payload: dict[str, Any],
) -> dict[str, Any]:
    preview = {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_create",
        "doNotCreate": True,
        "writeConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm DQ SQL validation (executes on connection)**\n\n"
            f"- **connection_id:** {payload.get('connectionId')}\n"
            f"- **schema_id:** {payload.get('schemaId')}\n"
            "- **Queries:** rule, stats, and failed-values SELECTs will be executed "
            "(limit 1 row each).\n\n"
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same connection_id, schema_id, and three queries."
        ),
        "agentInstruction": _DQ_SQL_VALIDATE_CONFIRM_INSTRUCTION,
        "pendingCreate": payload,
    }
    return attach_confirmation_token(preview, payload)


def format_validate_dq_queries_response(body: dict[str, Any]) -> dict[str, Any]:
    data = _unwrap_api_data(body)
    if not isinstance(data, dict):
        return body if isinstance(body, dict) else {"ok": True, "data": body}
    can_create = bool(data.get("canCreateRule"))
    lines = [
        "**Validate SQL queries**",
        f"- Rule query valid: {'Yes' if data.get('ruleQueryValid') else 'No'}",
        f"- Can create rule: {'Yes' if can_create else 'No'}",
    ]
    results = data.get("results")
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            qtype = item.get("queryType", "?")
            valid = "valid" if item.get("valid") else "invalid"
            msg = item.get("message", "")
            lines.append(f"- {qtype}: {valid}" + (f" ({msg})" if msg else ""))
    return {
        "ok": True,
        "workflowPhase": "validate_queries",
        "canCreateRule": can_create,
        "formattedResponse": "\n".join(lines),
        "data": data,
        "agentInstruction": (
            f"Proceed to {TOOL_DQ_RULE_MANAGER} step=create_custom_sql only when "
            "canCreateRule is true and the user confirms. Pass recommended_function = "
            "recommendedFunction from generate_query/assess. "
            f"{_DQ_RETRY_POLICY}"
        ),
    }


def validate_create_sql_dq_rule_args(
    objects: Any,
    rule_name: str | None,
    rule_query: str | None,
    stats_query: str | None,
    failed_values_query: str | None,
    code_object_id: int | None,
    recommended_function: str | None = None,
) -> dict[str, Any] | None:
    refs, err = _normalize_dq_api_objects(objects)
    if err is not None:
        return err
    if not refs:
        return error_payload(
            "At least one object with objectId and objectType is required.",
        )
    if not strip_or_none_description_field(rule_name):
        return error_payload("rule_name is required.")
    has_code = code_object_id is not None and code_object_id > 0
    has_rule_query = bool(strip_or_none_description_field(rule_query))
    if not has_code and not has_rule_query:
        return error_payload("rule_query or code_object_id is required.")
    if has_rule_query and not has_code:
        if not strip_or_none_description_field(stats_query):
            return error_payload("stats_query is required when rule_query is provided.")
        if not strip_or_none_description_field(failed_values_query):
            return error_payload(
                "failed_values_query is required when rule_query is provided."
            )
    rf_err = _validate_recommended_function_for_create_sql(recommended_function)
    if rf_err is not None:
        return rf_err
    return None


def _validate_recommended_function_for_create_sql(
    recommended_function: str | None,
) -> dict[str, Any] | None:
    """create_custom_sql must pass recommendedFunction name from generate/assess."""
    rf = strip_or_none_description_field(recommended_function)
    if not rf:
        return error_payload(
            "recommended_function is required for create_custom_sql. "
            + _DQ_CREATE_SQL_LOOP_BACK,
            error_code="validation_required",
        )
    if rf.strip().lower() in _INVALID_RECOMMENDED_FUNCTION_PLACEHOLDERS:
        return error_payload(
            "recommended_function must be a real recommendedFunction name from "
            "generate_query/assess (not a placeholder). "
            + _DQ_CREATE_SQL_LOOP_BACK,
            error_code="validation_invalid",
        )
    return None


def map_create_sql_dq_error(exc: Exception) -> dict[str, Any]:
    """Map OvalEdge create-sql errors; loop agent back when recommendedFunction missing."""
    from server.client import OvalEdgeError
    from server.tools.common.errors import map_ovaledge_error

    if isinstance(exc, OvalEdgeError):
        out = map_ovaledge_error(exc)
    else:
        out = error_payload(str(exc), status_code=500)
    msg = str(exc).lower()
    if "recommended dq function" in msg or "recommendedfunction" in msg.replace(" ", ""):
        out["agentInstruction"] = _DQ_CREATE_SQL_LOOP_BACK
        detail = out.get("error") or str(exc)
        out["error"] = f"{detail} {_DQ_CREATE_SQL_LOOP_BACK}"
    return out


def build_create_sql_dq_rule_payload(
    objects: Any,
    rule_name: str,
    rule_query: str | None,
    stats_query: str | None,
    failed_values_query: str | None,
    connection_id: int | None,
    schema_id: int | None,
    purpose: str | None,
    recommended_function: str | None,
    code_object_id: int | None,
) -> dict[str, Any]:
    built = build_assess_cde_dq_payload(False, objects, 1)
    if "error" in built:
        return built
    api_objects = built.get("objects") or []
    if not api_objects:
        return error_payload(
            "At least one object with objectId and objectType is required.",
        )
    target = api_objects[0]
    payload: dict[str, Any] = {
        "objectId": target["objectId"],
        "objectType": target.get("objectType", "oecolumn"),
        "ruleName": rule_name.strip(),
    }
    rq = strip_or_none_description_field(rule_query)
    sq = strip_or_none_description_field(stats_query)
    fv = strip_or_none_description_field(failed_values_query)
    if rq:
        payload["ruleQuery"] = rq
    if sq:
        payload["statsQuery"] = sq
    if fv:
        payload["failedValuesQuery"] = fv
    if code_object_id is not None and code_object_id > 0:
        payload["codeObjectId"] = int(code_object_id)
    if connection_id is not None and connection_id > 0:
        payload["connectionId"] = int(connection_id)
    if schema_id is not None and schema_id > 0:
        payload["schemaId"] = int(schema_id)
    p = strip_or_none_description_field(purpose)
    if p:
        payload["purpose"] = p
    rf = strip_or_none_description_field(recommended_function)
    if rf:
        payload["recommendedFunction"] = rf
    if len(api_objects) > 1:
        payload["additionalObjects"] = api_objects[1:]
    return payload


def format_create_sql_dq_rule_confirmation_preview(
    payload: dict[str, Any],
) -> dict[str, Any]:
    object_lines = _summarize_dq_object_refs(
        [{"objectId": payload.get("objectId"), "objectType": payload.get("objectType")}]
        + (payload.get("additionalObjects") or [])
    )
    objects_block = "\n".join(object_lines) if object_lines else "- (none)"
    preview = {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_create",
        "doNotCreate": True,
        "writeConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm custom SQL DQ rule create**\n\n"
            f"- **rule_name:** {payload.get('ruleName')}\n"
            f"- **recommendedFunction:** {payload.get('recommendedFunction')}\n"
            f"**Objects:**\n{objects_block}\n\n"
            "Creates custom SQL data quality rule with rule/stats/failed-values code objects. "
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same parameters (including recommended_function)."
        ),
        "agentInstruction": (
            f"{_DQ_SQL_CREATE_CONFIRM_INSTRUCTION} Keep recommended_function = "
            f"recommendedFunction from generate/assess. {_DQ_RETRY_POLICY}"
        ),
        "pendingCreate": payload,
    }
    return attach_confirmation_token(preview, payload)


def format_create_sql_dq_rule_response(body: dict[str, Any]) -> dict[str, Any]:
    data = _unwrap_api_data(body)
    if not isinstance(data, dict):
        return body if isinstance(body, dict) else {"ok": True, "data": body}
    status = data.get("status", "")
    message = data.get("message", "")
    if status == "cross_schema_blocked":
        return {
            "ok": True,
            "workflowPhase": "create_sql_rule",
            "formattedResponse": (
                f"**Custom SQL DQ rule** — status: `{status}`\n\n"
                f"{message or 'Cross-schema dependent rules cannot be created.'}"
            ),
            "data": data,
            "agentInstruction": (
                "Do not retry with manual SQL for cross-schema dependent rules."
            ),
        }
    rule_name = data.get("ruleName") or data.get("dqruleId")
    out = body if isinstance(body, dict) else {"ok": True, "data": data}
    out = dict(out)
    out["workflowPhase"] = "create_sql_rule"
    out["formattedResponse"] = (
        f"**Custom SQL DQ rule** — status: `{status}`\n\n"
        f"DQ rule **{rule_name}** created. Review queries and associations in OvalEdge."
    )
    return out
