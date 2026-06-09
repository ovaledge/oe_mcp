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
from server.tools.common.errors import error_payload

_DESC_ASSESS_CDE_DQ = (
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
    "recommendedFunction (or Not Identified), recommendedRule (or Not Available), "
    "associatedToDqRule, objectRedirectUrl, and dqRuleRedirectUrl.\n\n"
    "**Not** associate_dq_rule_objects or create_dq_rules — those write draft rules; "
    "use this tool first for read-only recommendations, then writes only after user approval.\n\n"
    "Read-only. Returns validation errors when objects is empty and discover is false; "
    "RBAC applies server-side on catalog reads."
)

_DESC_ASSOCIATE_DQ_RULE_OBJECTS = (
    "Associate catalog objects to an existing draft DQ rule (idempotent when "
    "skip_already_associated=true).\n\n"
    f"Backend: POST {MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS}\n\n"
    "Mirrors the UI flow: batch-validates each objectType against the rule function via "
    "getSupportedDQRuleObjectsForDQFunction (validateDQRuleObjectsForDQFunction), then "
    "associates only supported objects.\n\n"
    "**Not** assess_cde_dq — that is read-only assessment; use this after the user "
    "confirms linking to a specific draft rule.\n\n"
    "**Not** create_dq_rules — use that when you need auto-create or prefer-existing "
    "in one call.\n\n"
    "**dqrule_id** (required): draft rule id from assess_cde_dq or lookup_dq_rule.\n\n"
    "**objects** (required): "
    '[{"objectId": 123, "objectType": "oecolumn"}, ...]\n\n'
    f"**objectType**: {MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC} only.\n\n"
    "Response includes statusMessage (batch function-support summary), counts "
    "(associatedCount, skippedCount, failedCount), and per-row status:\n"
    "- associated: linked to the draft rule\n"
    "- skipped: already linked, or unsupported column data type / connector for the function\n"
    "- failed: invalid object type, not found, or license error\n\n"
    "Present formattedResponse to the user. Audit source OE-MCP."
)

_DESC_CREATE_DQ_RULES = (
    "Assess CDE/DQ objects then associate to a recommended existing rule or auto-create "
    "draft DQ rules when function and business criteria are sufficient.\n\n"
    f"Backend: POST {MCP_PATH_CREATE_DQ_RULES}\n\n"
    "**Not** assess_cde_dq — read-only only; use create_dq_rules when the user wants "
    "draft rules created or associated in one step.\n\n"
    "**Not** associate_dq_rule_objects — use that when the draft rule id is already known.\n\n"
    "Run assess_cde_dq first when unsure; this endpoint re-assesses internally.\n\n"
    "**discover_cde_columns** / **objects** / **limit**: same as assess_cde_dq.\n\n"
    "**prefer_existing_rule** (default true): associate when a recommended rule exists.\n\n"
    "**skip_duplicate_function_on_object** (default true): skip if object already has a "
    "rule for the same function type.\n\n"
    "Row statuses: created, associated, skipped, criteria_missing, function_not_identified, "
    "failed. Audit source OE-MCP."
)

_DESC_LOOKUP_DQ_RULE = (
    "Look up Data Quality rules by name or id (not in search_catalog_assets).\n\n"
    f"Backend: GET {MCP_PATH_LOOKUP_DQ_RULES}\n\n"
    "Provide either rule_name (partial match) or object_id, never both.\n\n"
    "Each hit includes objectId, objectType (dqrule), objectName, steward, redirectUrl. "
    "Use with update_governance_roles: only steward may be updated on DQ rules."
)


def normalize_dq_object_type(object_type: str | None) -> str | None:
    if object_type is None or not str(object_type).strip():
        return None
    key = str(object_type).strip().lower()
    return MCP_DQ_OBJECT_TYPE_ALIASES.get(key)


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
    return None


def build_assess_cde_dq_payload(
    discover_cde_columns: bool,
    objects: list[dict[str, Any]] | None,
    limit: int,
) -> dict[str, Any]:
    capped = min(max(limit, 1), MCP_DQ_ASSESS_LIMIT_MAX)
    payload: dict[str, Any] = {
        "discoverCdeColumns": discover_cde_columns,
        "limit": capped,
    }
    if not objects:
        return payload
    api_objects: list[dict[str, Any]] = []
    for idx, raw in enumerate(objects):
        if not isinstance(raw, dict):
            return error_payload(f"objects[{idx}] must be an object with objectId and objectType.")
        oid = raw.get("objectId", raw.get("object_id"))
        otype_raw = raw.get("objectType", raw.get("object_type"))
        if oid is None:
            return error_payload(f"objects[{idx}] requires objectId (or object_id).")
        try:
            oid_int = int(oid)
        except (TypeError, ValueError):
            return error_payload(f"objects[{idx}].objectId must be a positive integer.")
        if oid_int <= 0:
            return error_payload(f"objects[{idx}].objectId must be a positive integer.")
        otype = normalize_dq_object_type(
            str(otype_raw) if otype_raw is not None else None
        )
        if otype is None:
            return error_payload(
                f"objects[{idx}].objectType must be one of {MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC}, "
                f"got {otype_raw!r}.",
            )
        api_objects.append({"objectId": oid_int, "objectType": otype})
    payload["objects"] = api_objects
    return payload


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
        lines.append(f"Function support: {status_message.strip()}")
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
) -> dict[str, Any]:
    built = build_assess_cde_dq_payload(discover_cde_columns, objects, limit)
    if "error" in built:
        return built
    payload: dict[str, Any] = {
        "discoverCdeColumns": discover_cde_columns,
        "preferExistingRule": prefer_existing_rule,
        "skipDuplicateFunctionOnObject": skip_duplicate_function_on_object,
        "limit": built.get("limit", limit),
    }
    if built.get("objects"):
        payload["objects"] = built["objects"]
    return payload
