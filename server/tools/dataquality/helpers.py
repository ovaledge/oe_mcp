"""Helpers for Data Quality MCP tools."""

from typing import Any

from server.constants import (
    MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC,
    MCP_DQ_ASSESS_LIMIT_MAX,
    MCP_DQ_OBJECT_TYPE_ALIASES,
    MCP_PATH_ASSESS_CDE_DQ,
    MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS,
    MCP_PATH_CREATE_DQ_RULES,
    MCP_PATH_LOOKUP_DQ_RULES,
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
    "Description resolution order (server-side):\n"
    "1. Object/catalog description when present.\n"
    "2. Associated glossary term description(s) when object description is empty.\n"
    "3. Named custom field only when the user explicitly requests it — pass "
    "description_custom_field_name with the field label/key the user named.\n"
    "4. When still unavailable, descriptionMessage explains object id/type, term "
    "status, and lists availableCustomFields for the user to choose from.\n\n"
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
    "**description_custom_field_name**: same as assess_cde_dq.\n\n"
    "**prefer_existing_rule** (default true): associate when a recommended rule exists.\n\n"
    "**skip_duplicate_function_on_object** (default true): skip if object already has a "
    "rule for the same function type.\n\n"
    "Validates objects like associate_dq_rule_objects; auto-creates from business metadata "
    "or function defaults. Row statuses: created, associated, skipped, criteria_missing, "
    "function_not_identified, failed.\n\n"
    "Extended routing: docs://ovaledge/mcp_workflows (CDE / DQ intelligence).\n\n"
    "**Confirm gate:** preview without write_confirmed_by_user → user approval → "
    "write_confirmed_by_user=true + confirmation_token from preview.\n\n"
    "Audit source OE-MCP."
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
) -> dict[str, Any]:
    capped = min(max(limit, 1), MCP_DQ_ASSESS_LIMIT_MAX)
    payload: dict[str, Any] = {
        "discoverCdeColumns": discover_cde_columns,
        "limit": capped,
    }
    field_name = strip_or_none_description_field(description_custom_field_name)
    if field_name is not None:
        payload["descriptionCustomFieldName"] = field_name
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
    object_lines = _summarize_dq_object_refs(body.get("objects"))
    objects_block = "\n".join(object_lines) if object_lines else "- (discover mode or empty)"
    field_line = ""
    if isinstance(field_name, str) and field_name.strip():
        field_line = f"\n- **description_custom_field_name:** {field_name.strip()}"
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
            "description_custom_field_name."
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
) -> dict[str, Any]:
    built = build_assess_cde_dq_payload(
        discover_cde_columns, objects, limit, description_custom_field_name
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
    if built.get("objects"):
        payload["objects"] = built["objects"]
    return payload
