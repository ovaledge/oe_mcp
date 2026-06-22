"""Custom / additional field update helpers."""

from __future__ import annotations

from typing import Any

from server.constants import MCP_CUSTOM_FIELD_OBJECT_TYPES_DOC, MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES
from server.tools.governance._shared import _CREATE_CONFIRM_AGENT_INSTRUCTION

_DESC_UPDATE_CUSTOM_FIELD_VALUE = (
    "Update custom / additional field values on supported OvalEdge assets "
    "(NOT governance Owner/Steward/Custodian — use update_governance_roles for those).\n\n"
    "When the user names a field label like 'Data Owner' that appears in Additional "
    "Information / custom fields, use this tool only if GET custom-fields lists it.\n\n"
    f"Backend: GET /api/v1/mcp/custom-fields, POST {MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES}\n\n"
    "**Human confirmation:** When ready to persist (and dry_run is not true), call without "
    "create_confirmed_by_user to receive a confirm_update preview (doNotUpdate=true). "
    "Show formattedResponse; wait for explicit user approval. Re-call with "
    "create_confirmed_by_user=true and the same object_id, object_type, field_updates, "
    "and clientContext — then POST.\n\n"
    "Workflow:\n"
    "1. Parse field name(s) and value(s) from user text.\n"
    "2. If the asset name is in the utterance, search_catalog_assets — do not ask which object.\n"
    "3. GET custom-fields to verify field exists and editableThroughApi; "
    "list CCF options on errors.\n"
    "4. Confirm, then POST with create_confirmed_by_user=true.\n\n"
    f"Supported object_type values: {MCP_CUSTOM_FIELD_OBJECT_TYPES_DOC}."
)


def _normalize_field_updates(
    field_updates: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not field_updates:
        return None, "field_updates is required (at least one {field_name, value})."
    normalized: list[dict[str, Any]] = []
    for item in field_updates:
        if not isinstance(item, dict):
            return None, "Each field_updates entry must be an object."
        field_name = item.get("field_name") or item.get("fieldName")
        field_key = item.get("field_key") or item.get("fieldKey")
        value = item.get("value")
        if value is None:
            return None, "Each field_updates entry requires a value."
        if not str(field_name or field_key or "").strip():
            return None, "Each field_updates entry requires field_name or field_key."
        entry: dict[str, Any] = {"value": str(value)}
        if field_name is not None and str(field_name).strip():
            entry["fieldName"] = str(field_name).strip()
        if field_key is not None and str(field_key).strip():
            entry["fieldKey"] = str(field_key).strip()
        normalized.append(entry)
    return normalized, None


def _format_update_custom_field_value_response(body: dict[str, Any]) -> str:
    lines: list[str] = ["**Custom field update**"]
    target = body.get("target")
    if isinstance(target, dict):
        otype = target.get("objectType")
        oid = target.get("objectId")
        if otype and oid:
            lines.append(f"- **Target:** {otype} (id {oid})")
        redirect = target.get("redirectUrl")
        if isinstance(redirect, str) and redirect.strip():
            lines.append(f"- [Open in OvalEdge]({redirect.strip()})")
    status = body.get("status")
    if status:
        lines.append(f"- **Status:** {status}")
    updated = body.get("updatedFields")
    if isinstance(updated, list) and updated:
        lines.append(f"- **Updated fields:** {', '.join(str(f) for f in updated)}")
    blocked = body.get("blockedFields")
    if isinstance(blocked, list) and blocked:
        lines.append(f"- **Blocked fields:** {', '.join(str(f) for f in blocked)}")
    reasons = body.get("blockedReasons")
    if isinstance(reasons, list):
        for reason in reasons:
            if isinstance(reason, dict):
                msg = reason.get("message")
                if msg:
                    lines.append(f"  - {msg}")
    audit = body.get("audit")
    if isinstance(audit, dict) and audit.get("source"):
        lines.append(f"- **Audit source:** {audit['source']}")
    message = str(body.get("message") or "").strip()
    if message:
        lines.append(message)
    return "\n".join(lines).strip()


def _enrich_update_custom_field_value_response(body: dict[str, Any]) -> dict[str, Any]:
    raw_data = body.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else body
    formatted = _format_update_custom_field_value_response(data)
    if formatted:
        data["formattedResponse"] = formatted
    return data


def _format_update_custom_field_value_confirmation_preview(
    body: dict[str, Any],
) -> dict[str, Any]:
    target = body.get("target")
    oid = otype = None
    if isinstance(target, dict):
        oid = target.get("objectId")
        otype = target.get("objectType")
    field_updates = body.get("fieldUpdates")
    field_lines: list[str] = []
    if isinstance(field_updates, list):
        for item in field_updates:
            if isinstance(item, dict):
                name = item.get("fieldName") or item.get("fieldKey") or "(field)"
                field_lines.append(f"- **{name}:** {item.get('value', '')}")
    fields_block = "\n".join(field_lines) if field_lines else "- (no field_updates)"
    dry = body.get("options", {})
    dry_note = ""
    if isinstance(dry, dict) and dry.get("dryRun"):
        dry_note = "\n- **Note:** dry_run=true — validate only on confirm.\n"
    return {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_update",
        "doNotUpdate": True,
        "createConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm custom field update**\n\n"
            f"- **Target:** {otype} (id {oid})\n"
            f"{fields_block}\n"
            f"{dry_note}\n"
            "Ask the user to confirm. After they approve, call again with "
            "`create_confirmed_by_user=true` and the same object_id, object_type, "
            "field_updates, and clientContext."
        ),
        "agentInstruction": _CREATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingUpdate": {
            "target": target,
            "fieldUpdates": field_updates,
        },
    }


# In-memory proof that step 1 (parent picker) ran for a tag name — not exposed to clients.
_PENDING_PARENT_PICKER_TTL_SEC = 3600
