"""Helpers for Data Quality MCP tools."""

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
    TOOL_ASSESS_CDE_DQ,
    TOOL_ASSOCIATE_DQ_RULE_OBJECTS,
    TOOL_CREATE_DQ_RULES,
    TOOL_CREATE_SQL_DQ_RULE,
    TOOL_VALIDATE_DQ_QUERIES,
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

_DESC_ASSESS_CDE_DQ = classify_tool_desc(
    "Assess Critical Data Element (CDE) columns and DQ-applicable assets for coverage: "
    "business metadata, recommended DQ function, reusable DQ rule, and whether the "
    "object is already associated to the recommended rule.\n\n"
    f"Backend: POST {MCP_PATH_ASSESS_CDE_DQ}\n\n"
    "**Not** lookup_dq_rule — that resolves existing DQ rules by name/id; use this tool "
    "for CDE column intelligence and function/rule recommendations.\n\n"
    "**Not** search_catalog_assets alone — search finds assets; call this tool with "
    "items[].objectId/objectType (or discover_cde_columns) for DQ assessment rows.\n\n"
    f"**objectType** (per object): {MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC} only "
    "(aliases such as table, column, filecolumn are normalized).\n\n"
    "**discover_cde_columns** (optional): when true and objects is empty, discovers "
    "table/file columns marked CDE (criticalDataElement=Yes) via catalog search.\n\n"
    "**objects** (optional): "
    '[{"objectId": 123, "objectType": "oecolumn"}, ...] from search_catalog_assets.\n\n'
    "Each row includes tableColumnName, businessDescription, businessRule, "
    "descriptionSource, descriptionMessage (when none), availableCustomFields, "
    "associatedTermDescriptions, recommendedFunction (or Not Identified), "
    "recommendedRule (or Not Available), associatedToDqRule, objectRedirectUrl, "
    "and dqRuleRedirectUrl.\n\n"
    "Description routing (server): default object/catalog description; pass "
    "description_term_name or description_custom_field_name only when the user names "
    "a term or field (no automatic glossary/custom-field fallback).\n\n"
    "**Not** associate_dq_rule_objects or create_dq_rules — those write data quality rules; "
    "use this tool first for read-only recommendations, then writes only after user approval.\n\n"
    "Read-only. Returns validation errors when objects is empty and discover is false; "
    "RBAC applies server-side on catalog reads."
)

_DESC_ASSOCIATE_DQ_RULE_OBJECTS = classify_tool_desc(
    "Associate catalog objects to an existing data quality rule (idempotent when "
    "skip_already_associated=true).\n\n"
    f"Backend: POST {MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS}\n\n"
    "Mirrors the UI flow: batch-validates each objectType against the rule function via "
    "getSupportedDQRuleObjectsForDQFunction (validateDQRuleObjectsForDQFunction), then "
    "associates only supported objects.\n\n"
    "**Not** assess_cde_dq — that is read-only assessment; use this after the user "
    "confirms linking to a specific data quality rule.\n\n"
    "**Not** create_dq_rules — use that when you need auto-create or prefer-existing "
    "in one call.\n\n"
    "**dqrule_id** (required): data quality rule id from assess_cde_dq or lookup_dq_rule.\n\n"
    "**objects** (required): "
    '[{"objectId": 123, "objectType": "oecolumn"}, ...]\n\n'
    f"**objectType**: {MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC} only.\n\n"
    "Published (ACTIVE) data quality rules are temporarily demoted to draft for association, "
    "then restored to published when complete. Rules already in draft proceed directly.\n\n"
    "Response: statusMessage, associatedCount/skippedCount/failedCount, per-row status "
    "(associated, skipped, failed).\n\n"
    "**Confirm gate:** preview without write_confirmed_by_user → user approval → "
    "write_confirmed_by_user=true + confirmation_token from preview.\n\n"
    "Present formattedResponse to the user. Audit source OE-MCP."
)

_DESC_CREATE_DQ_RULES = classify_tool_desc(
    "Assess CDE/DQ objects then associate to a recommended existing rule or auto-create "
    "data quality rules when function and business criteria are sufficient.\n\n"
    f"Backend: POST {MCP_PATH_CREATE_DQ_RULES}\n\n"
    "**Not** assess_cde_dq — read-only only; use create_dq_rules when the user wants "
    "data quality rules created or associated in one step.\n\n"
    "**Not** associate_dq_rule_objects — use that when the data quality rule id "
    "is already known.\n\n"
    "**discover_cde_columns** / **objects** / **limit** / "
    "**description_term_name** / **description_custom_field_name**: same as assess_cde_dq.\n\n"
    "**prefer_existing_rule** (default true): associate when a recommended rule exists.\n\n"
    "**skip_duplicate_function_on_object** (default true): skip if object already has a "
    "rule for the same function type.\n\n"
    "**supplemental_criteria_text** (optional): user prompt criteria when not in "
    "catalog metadata.\n\n"
    "Criteria priority: metadata or supplemental_criteria_text, then function defaults.\n\n"
    "Object validation and row statuses: same as associate_dq_rule_objects.\n\n"
    "**Confirm gate:** preview → user approval → write_confirmed_by_user=true + "
    "confirmation_token from preview.\n\n"
    "Routing: docs://ovaledge/mcp_workflows (CDE / DQ intelligence). Audit source OE-MCP."
)

_DESC_LOOKUP_DQ_RULE = classify_tool_desc(
    "Look up Data Quality rules by name or id (not in search_catalog_assets).\n\n"
    f"Backend: GET {MCP_PATH_LOOKUP_DQ_RULES}\n\n"
    "Provide either rule_name (partial match) or object_id, never both.\n\n"
    "Each hit includes objectId, objectType (dqrule), objectName, steward, redirectUrl. "
    "Use with update_governance_roles: only steward may be updated on DQ rules."
)


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


def _normalize_dq_api_objects(
    objects: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Validate and normalize catalog object refs for DQ assess/create payloads."""
    api_objects: list[dict[str, Any]] = []
    for idx, raw in enumerate(objects):
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
    objects: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    refs = objects or []
    if not refs and not discover_cde_columns:
        return error_payload(
            "Provide objects from search_catalog_assets, or set discover_cde_columns=true "
            "to discover CDE columns.",
        )
    if refs:
        _, err = _normalize_dq_api_objects(refs)
        if err is not None:
            return err
    return None


def build_assess_cde_dq_payload(
    discover_cde_columns: bool,
    objects: list[dict[str, Any]] | None,
    limit: int,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
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
    if not objects:
        return payload
    api_objects, err = _normalize_dq_api_objects(objects)
    if err is not None:
        return err
    payload["objects"] = api_objects
    return payload


def strip_or_none_description_field(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = str(value).strip()
    return trimmed or None


def format_assess_cde_dq_response(body: dict[str, Any]) -> str:
    """Human-readable summary highlighting description gaps."""
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
        message = row.get("descriptionMessage")
        if isinstance(message, str) and message.strip():
            lines.append(message.strip())
        elif source == "none":
            fields = row.get("availableCustomFields")
            if isinstance(fields, list) and fields:
                lines.append(f"  Available custom fields: {', '.join(str(f) for f in fields)}")
    return "\n".join(lines)


def validate_associate_dq_rule_objects_args(
    dqrule_id: int | None,
    objects: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if dqrule_id is None or int(dqrule_id) <= 0:
        return error_payload("dqrule_id must be a positive integer.")
    refs = objects or []
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


def format_create_dq_rules_confirmation_preview(body: dict[str, Any]) -> dict[str, Any]:
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
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same discover_cde_columns, objects, limit, flags, and optional "
            "description_term_name or description_custom_field_name."
        ),
        "agentInstruction": _DQ_CREATE_CONFIRM_INSTRUCTION,
        "pendingCreate": body,
    }
    return attach_confirmation_token(preview, body)


def build_associate_dq_rule_objects_payload(
    dqrule_id: int,
    objects: list[dict[str, Any]] | None,
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
    objects: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    return validate_assess_cde_dq_args(discover_cde_columns, objects)


def build_create_dq_rules_payload(
    discover_cde_columns: bool,
    objects: list[dict[str, Any]] | None,
    limit: int,
    prefer_existing_rule: bool,
    skip_duplicate_function_on_object: bool,
    description_custom_field_name: str | None = None,
    description_term_name: str | None = None,
    supplemental_criteria_text: str | None = None,
) -> dict[str, Any]:
    built = build_assess_cde_dq_payload(
        discover_cde_columns,
        objects,
        limit,
        description_custom_field_name,
        description_term_name,
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


_DESC_GENERATE_DQ_QUERIES = classify_tool_desc(
    "Generate rule/stats/failed-values SQL (custom_sql). "
    f"POST {MCP_PATH_GENERATE_DQ_QUERIES}. Requires objects; after {TOOL_ASSESS_CDE_DQ}."
)

_DESC_VALIDATE_DQ_QUERIES = classify_tool_desc(
    "Validate DQ SQL on connection. "
    f"POST {MCP_PATH_VALIDATE_DQ_QUERIES}. connection_id, schema_id, three queries; confirm gate."
)

_DESC_CREATE_SQL_DQ_RULE = classify_tool_desc(
    "Create draft oequery DQ rule and associate objects. "
    f"POST {MCP_PATH_CREATE_SQL_DQ_RULE}. rule_name; queries or code_object_id; confirm gate."
)

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
        f"- **connection_id:** {connection_id} (for {TOOL_VALIDATE_DQ_QUERIES})",
        f"- **schema_id:** {schema_id} (for {TOOL_VALIDATE_DQ_QUERIES})",
    ]


def _validate_queries_context_hint(data: dict[str, Any]) -> str:
    connection_id, schema_id = _sql_context_ids(data)
    if connection_id is None or schema_id is None:
        return (
            f"Pass connection_id and schema_id from data.context when calling "
            f"{TOOL_VALIDATE_DQ_QUERIES}."
        )
    return (
        f"Call {TOOL_VALIDATE_DQ_QUERIES} with connection_id={connection_id}, "
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
            f"Do not call {TOOL_VALIDATE_DQ_QUERIES} or {TOOL_CREATE_SQL_DQ_RULE}."
        )
    if action == _REUSE_ASSOCIATE_EXISTING_DQR:
        rule_hint = f"dqrule_id={dqrule_id}" if dqrule_id else "dqrule_id from data"
        return (
            f"Call {TOOL_ASSOCIATE_DQ_RULE_OBJECTS} with {rule_hint} and the target "
            f"object(s), confirm gate required. Do not call {TOOL_VALIDATE_DQ_QUERIES} "
            f"or {TOOL_CREATE_SQL_DQ_RULE}."
        )
    if action == _REUSE_CREATE_FROM_CODE:
        code_hint = f"code_object_id={code_id}" if code_id else "code_object_id from data"
        conn, schema = _sql_context_ids(data)
        ctx = ""
        if conn is not None and schema is not None:
            ctx = f", connection_id={conn}, schema_id={schema}"
        return (
            f"Call {TOOL_CREATE_SQL_DQ_RULE} with {code_hint}{ctx} and rule_name; "
            "confirm gate required. Skip validate unless the user explicitly requests it."
        )
    return (
        f"Review recommendedReuseAction in data. Prefer {TOOL_ASSOCIATE_DQ_RULE_OBJECTS} "
        f"or {TOOL_CREATE_SQL_DQ_RULE} with code_object_id before generating new SQL."
    )


def validate_generate_dq_queries_args(
    objects: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    refs = objects or []
    if not refs:
        return error_payload(
            "At least one object with objectId and objectType is required.",
        )
    _, err = _normalize_dq_api_objects(refs)
    return err


def build_generate_dq_queries_payload(
    objects: list[dict[str, Any]] | None,
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
        lines.append(f"- Recommended function: `{data.get('recommendedFunction')}`")
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
                f"Do not call {TOOL_VALIDATE_DQ_QUERIES} or {TOOL_CREATE_SQL_DQ_RULE}. "
                "Cross-schema dependent rules are not supported for custom SQL."
            ),
        }
    if status == "function_based":
        lines.append(
            f"This DQ function is not oequery-based. Use {TOOL_CREATE_DQ_RULES} "
            f"(or {TOOL_ASSESS_CDE_DQ} → {TOOL_ASSOCIATE_DQ_RULE_OBJECTS}) instead."
        )
        return {
            "ok": True,
            "workflowPhase": "generate_queries",
            "formattedResponse": "\n".join(lines),
            "data": data,
            "agentInstruction": (
                f"Do not call {TOOL_VALIDATE_DQ_QUERIES} or {TOOL_CREATE_SQL_DQ_RULE}. "
                f"Route to {TOOL_CREATE_DQ_RULES} or {TOOL_ASSOCIATE_DQ_RULE_OBJECTS}."
            ),
        }
    if status == "function_not_identified":
        lines.append(
            f"No DQ function could be resolved. Run {TOOL_ASSESS_CDE_DQ} first or add "
            "Function Name to business description."
        )
        return {
            "ok": True,
            "workflowPhase": "generate_queries",
            "formattedResponse": "\n".join(lines),
            "data": data,
            "agentInstruction": "Ask the user to clarify the DQ function name before retrying.",
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
    out = {
        "ok": True,
        "workflowPhase": "generate_queries",
        "formattedResponse": "\n".join(lines),
        "data": data,
        "agentInstruction": (
            f"{validate_hint} Confirm gate required. After canCreateRule is true, call "
            f"{TOOL_CREATE_SQL_DQ_RULE} with user approval."
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
            f"Proceed to {TOOL_CREATE_SQL_DQ_RULE} only when canCreateRule is true "
            "and the user confirms."
        ),
    }


def validate_create_sql_dq_rule_args(
    objects: list[dict[str, Any]] | None,
    rule_name: str | None,
    rule_query: str | None,
    stats_query: str | None,
    failed_values_query: str | None,
    code_object_id: int | None,
) -> dict[str, Any] | None:
    refs = objects or []
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
    _, err = _normalize_dq_api_objects(refs)
    return err


def build_create_sql_dq_rule_payload(
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
            f"**Objects:**\n{objects_block}\n\n"
            "Creates draft oequery DQ rule with rule/stats/failed-values code objects. "
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same parameters."
        ),
        "agentInstruction": _DQ_SQL_CREATE_CONFIRM_INSTRUCTION,
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
        f"Draft rule **{rule_name}** created. Review queries and associations in OvalEdge."
    )
    return out
