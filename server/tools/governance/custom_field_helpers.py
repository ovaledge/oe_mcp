"""Custom / additional field update helpers."""

from __future__ import annotations

import ast
import re
from typing import Any

from server.constants import (
    MCP_CUSTOM_FIELD_OBJECT_TYPES_DOC,
    MCP_PATH_CUSTOM_FIELDS,
    MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES,
)
from server.tools.common.confirm_gate import attach_confirmation_token
from server.tools.common.descriptions import classify_tool_desc
from server.tools.governance._shared import _CREATE_CONFIRM_AGENT_INSTRUCTION

CODE_UPDATE_MODES = frozenset({"replace_all", "add", "remove"})

_DESC_UPDATE_CUSTOM_FIELD_VALUE = classify_tool_desc(
    "Update custom / additional field values on supported OvalEdge assets "
    "(NOT governance Owner/Steward/Custodian — use update_governance_roles for those).\n\n"
    "When the user names a field label like 'Data Owner' that appears in Additional "
    "Information / custom fields, use this tool only if GET custom-fields lists it.\n\n"
    f"Backend: GET /api/v1/mcp/custom-fields, POST {MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES}\n\n"
    "**Human confirmation:** When ready to persist (and dry_run is not true), call without "
    "write_confirmed_by_user to receive a confirm_update preview (doNotUpdate=true). "
    "Show formattedResponse; wait for explicit user approval. Re-call with "
    "write_confirmed_by_user=true and the same object_id, object_type, field_updates, "
    "and clientContext — then POST.\n\n"
    "Workflow:\n"
    "1. Parse field name(s) and value(s); search_catalog_assets when the asset name is known.\n"
    "2. Code fields: GET custom-fields; validate option names against configured "
    "options; single-select → one option; multi-select → code_update_mode "
    "(replace_all|add|remove).\n"
    "3. Confirm preview, then POST with write_confirmed_by_user=true and "
    "confirmation_token from the preview.\n\n"
    f"Supported object_type values: {MCP_CUSTOM_FIELD_OBJECT_TYPES_DOC}."
)


def _coerce_value_to_comma_string(value: Any) -> str:
    """
    Always return the comma-separated string the backend expects for a field value.

    Handles three shapes an agent/MCP transport may produce for multi-value code fields:
    1. A real list/tuple/set -> join with commas.
    2. A stringified container (e.g. "['a', 'b']" or '["a", "b"]') that slipped through
       as a plain str -> parse and join, instead of forwarding the brackets/quotes which
       the API rejects as invalid options.
    3. A plain scalar string -> returned unchanged.
    """
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(v).strip() for v in value if str(v).strip())
    text = str(value).strip()
    if len(text) >= 2 and text[0] in "[(" and text[-1] in "])":
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            parsed = None
        if isinstance(parsed, (list, tuple, set)):
            return ",".join(str(v).strip() for v in parsed if str(v).strip())
    return text


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
        # Agents sometimes pass multiple code-field options as a list/tuple (or a
        # stringified container). Always coerce to the comma-separated string the
        # backend expects instead of forwarding "['a', 'b']", which the API rejects
        # as an invalid option.
        entry: dict[str, Any] = {"value": _coerce_value_to_comma_string(value)}
        if field_name is not None and str(field_name).strip():
            entry["fieldName"] = str(field_name).strip()
        if field_key is not None and str(field_key).strip():
            entry["fieldKey"] = str(field_key).strip()
        normalized.append(entry)
    return normalized, None


# Code-field option separators: commas plus a natural-language " and " / " & ".
# Lets prompts like "option 1, option 2 and option 3" or "option 1 and option 2"
# resolve to individual options.
_CODE_VALUE_SEPARATOR_RE = re.compile(r"\s*,\s*|\s+and\s+|\s*&\s*", re.IGNORECASE)


def _split_code_values(raw: str) -> list[str]:
    return [part.strip() for part in _CODE_VALUE_SEPARATOR_RE.split(raw) if part.strip()]


def _extract_mcp_data(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else response


def _field_lookup(entry: dict[str, Any]) -> str:
    return str(entry.get("fieldName") or entry.get("fieldKey") or "").strip()


def _format_option_names(options: list[Any]) -> str:
    names: list[str] = []
    for opt in options:
        if isinstance(opt, dict):
            name = opt.get("name")
            if name is not None and str(name).strip():
                names.append(str(name).strip())
    return ", ".join(names) if names else "(no options configured)"


def _option_names_by_lower(options: list[Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for opt in options:
        if isinstance(opt, dict):
            name = opt.get("name")
            if name is not None and str(name).strip():
                key = str(name).strip().lower()
                if key not in mapping:
                    mapping[key] = str(name).strip()
    return mapping


def _validate_and_canonicalize_code_parts(
    parts: list[str],
    options: list[Any],
) -> tuple[list[str], list[str]]:
    """Return (invalid_values, canonical_parts). Skips validation when options is empty."""
    option_map = _option_names_by_lower(options)
    if not option_map:
        return [], _normalize_name_list(parts)
    invalid: list[str] = []
    canonical: list[str] = []
    for part in _normalize_name_list(parts):
        resolved = option_map.get(part.lower())
        if resolved is None:
            invalid.append(part)
        else:
            canonical.append(resolved)
    return invalid, canonical


def _normalize_name_list(values: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen[key] = value.strip()
    return list(seen.values())


def _merge_code_values(current: str, new_parts: list[str], mode: str) -> list[str]:
    current_parts = _normalize_name_list(_split_code_values(current))
    new_parts_norm = _normalize_name_list(new_parts)
    current_map = {value.lower(): value for value in current_parts}
    new_map = {value.lower(): value for value in new_parts_norm}
    if mode == "replace_all":
        return list(new_map.values())
    if mode == "add":
        merged = dict(current_map)
        merged.update(new_map)
        return list(merged.values())
    if mode == "remove":
        return [value for key, value in current_map.items() if key not in new_map]
    return new_parts_norm


async def _fetch_custom_field_meta(
    client: Any,
    object_id: int,
    object_type: str,
    field_lookup: str,
) -> dict[str, Any] | None:
    response = await client.get(
        MCP_PATH_CUSTOM_FIELDS,
        params={
            "objectId": object_id,
            "objectType": object_type,
            "fieldName": field_lookup,
        },
    )
    payload = _extract_mcp_data(response)
    fields = payload.get("fields")
    if not isinstance(fields, list) or not fields:
        return None
    field = fields[0]
    return field if isinstance(field, dict) else None


def _clarify_single_select_response(
    *,
    object_id: int,
    object_type: str,
    field_label: str,
    provided_values: list[str],
    option_names: str,
    field_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": True,
        "awaitingUserClarification": True,
        "workflowPhase": "clarify_single_select",
        "doNotUpdate": True,
        "formattedResponse": (
            "**Code field accepts one value only**\n\n"
            f"- **Target:** {object_type} (id {object_id})\n"
            f"- **Field:** {field_label}\n"
            f"- **You provided:** {', '.join(provided_values)}\n"
            f"- **Valid options:** {option_names}\n\n"
            "Ask the user to choose a single option, then call again with one value only."
        ),
        "agentInstruction": (
            "Show formattedResponse and wait for the user to pick one option. "
            "Re-call update_custom_field_value with a single value for this field."
        ),
        "pendingUpdate": {
            "target": {"objectId": object_id, "objectType": object_type},
            "fieldUpdates": field_updates,
        },
    }


def _invalid_code_options_response(
    *,
    object_id: int,
    object_type: str,
    field_label: str,
    invalid_values: list[str],
    option_names: str,
    field_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    invalid_display = ", ".join(invalid_values)
    return {
        "ok": False,
        "awaitingUserClarification": True,
        "workflowPhase": "invalid_code_options",
        "doNotUpdate": True,
        "error": f"Invalid option(s) for {field_label}: {invalid_display}",
        "status_code": 400,
        "formattedResponse": (
            "**Invalid code field option(s)**\n\n"
            f"- **Target:** {object_type} (id {object_id})\n"
            f"- **Field:** {field_label}\n"
            f"- **Invalid:** {invalid_display}\n"
            f"- **Valid options:** {option_names}\n\n"
            "Ask the user to choose from the valid options only, then call again."
        ),
        "agentInstruction": (
            "Show formattedResponse and wait for the user to pick valid option(s). "
            "Re-call update_custom_field_value with corrected values."
        ),
        "pendingUpdate": {
            "target": {"objectId": object_id, "objectType": object_type},
            "fieldUpdates": field_updates,
        },
    }


def _clarify_multi_select_mode_response(
    *,
    object_id: int,
    object_type: str,
    field_label: str,
    provided_values: list[str],
    current_value: str,
    option_names: str,
    field_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    current_display = current_value.strip() or "(empty)"
    return {
        "ok": True,
        "awaitingUserClarification": True,
        "workflowPhase": "clarify_multi_select_mode",
        "doNotUpdate": True,
        "formattedResponse": (
            "**Multi-select code field — choose update mode**\n\n"
            f"- **Target:** {object_type} (id {object_id})\n"
            f"- **Field:** {field_label}\n"
            f"- **Current value:** {current_display}\n"
            f"- **You provided:** {', '.join(provided_values)}\n"
            f"- **Valid options:** {option_names}\n\n"
            "Ask the user whether to **replace all**, **add** to existing, or **remove** "
            "from existing. Then re-call with the same field_updates and set "
            "`code_update_mode` to `replace_all`, `add`, or `remove`."
        ),
        "agentInstruction": (
            "Show formattedResponse and wait for the user's choice. Re-call with "
            "code_update_mode=replace_all|add|remove and the same field_updates."
        ),
        "pendingUpdate": {
            "target": {"objectId": object_id, "objectType": object_type},
            "fieldUpdates": field_updates,
        },
    }


async def _apply_code_field_update_policies(
    client: Any,
    object_id: int,
    object_type: str,
    field_updates: list[dict[str, Any]],
    code_update_mode: str | None,
) -> dict[str, Any]:
    mode = str(code_update_mode or "").strip().lower() or None
    if mode and mode not in CODE_UPDATE_MODES:
        return {
            "error": (
                "code_update_mode must be one of "
                f"{sorted(CODE_UPDATE_MODES)}, got {code_update_mode!r}"
            ),
            "status_code": 400,
        }

    resolved: list[dict[str, Any]] = []
    for entry in field_updates:
        raw_value = str(entry.get("value", ""))
        parts = _split_code_values(raw_value)
        lookup = _field_lookup(entry)
        if not lookup:
            resolved.append(dict(entry))
            continue

        meta = await _fetch_custom_field_meta(client, object_id, object_type, lookup)
        if not meta or str(meta.get("type", "")).lower() != "code":
            resolved.append(dict(entry))
            continue

        allow_multiple = bool(meta.get("allowMultiple"))
        raw_options = meta.get("options")
        options: list[Any] = raw_options if isinstance(raw_options, list) else []
        option_names = _format_option_names(options)
        field_label = str(meta.get("fieldName") or lookup)
        current_value = str(meta.get("currentValue") or "")

        invalid, canonical_parts = _validate_and_canonicalize_code_parts(parts, options)
        if invalid:
            return _invalid_code_options_response(
                object_id=object_id,
                object_type=object_type,
                field_label=field_label,
                invalid_values=invalid,
                option_names=option_names,
                field_updates=field_updates,
            )

        if not allow_multiple and len(canonical_parts) > 1:
            return _clarify_single_select_response(
                object_id=object_id,
                object_type=object_type,
                field_label=field_label,
                provided_values=canonical_parts,
                option_names=option_names,
                field_updates=field_updates,
            )

        if allow_multiple and len(canonical_parts) > 1 and not mode:
            return _clarify_multi_select_mode_response(
                object_id=object_id,
                object_type=object_type,
                field_label=field_label,
                provided_values=canonical_parts,
                current_value=current_value,
                option_names=option_names,
                field_updates=field_updates,
            )

        if allow_multiple and len(canonical_parts) > 1 and mode:
            merged = _merge_code_values(current_value, canonical_parts, mode)
            new_entry = dict(entry)
            new_entry["value"] = ",".join(merged)
            resolved.append(new_entry)
            continue

        new_entry = dict(entry)
        new_entry["value"] = canonical_parts[0] if canonical_parts else raw_value
        resolved.append(new_entry)

    return {"fieldUpdates": resolved}


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
    requested = body.get("requestedFields")
    if isinstance(requested, list) and requested:
        for entry in requested:
            if str(entry).strip():
                lines.append(f"- {entry}")
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
    tz = body.get("timeZone")
    tz_line = f"\n- **Time zone:** {tz}" if isinstance(tz, str) and tz.strip() else ""
    preview = {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_update",
        "doNotUpdate": True,
        "writeConfirmedByUser": False,
        "formattedResponse": (
            "**Confirm custom field update**\n\n"
            f"- **Target:** {otype} (id {oid})\n"
            f"{fields_block}\n"
            f"{tz_line}"
            f"{dry_note}\n"
            "Ask the user to confirm. After they approve, call again with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same object_id, object_type, field_updates, time_zone, "
            "and clientContext."
        ),
        "agentInstruction": _CREATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingUpdate": {
            "target": target,
            "fieldUpdates": field_updates,
            "timeZone": tz if isinstance(tz, str) else None,
        },
    }
    return attach_confirmation_token(preview, body)


# In-memory proof that step 1 (parent picker) ran for a tag name — not exposed to clients.
_PENDING_PARENT_PICKER_TTL_SEC = 3600
