"""Helpers for create_service_request."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from server.constants import (
    MCP_PATH_SERVICE_REQUEST_TEMPLATES,
    MCP_PATH_SERVICE_REQUESTS,
    MCP_SERVICE_REQUEST_OBJECT_TYPE_ALIASES,
    MCP_SERVICE_REQUEST_TYPE_ALIASES,
)
from server.nav_links import build_absolute_nav_url, extract_hash_nav_link
from server.tools.common import as_dict as _as_dict
from server.tools.common import blank as _blank
from server.tools.common.confirm_gate import (
    CREATE_CONFIRM_AGENT_INSTRUCTION,
    attach_confirmation_token,
)
from server.tools.common.descriptions import classify_tool_desc
from server.tools.common.errors import error_payload
from server.tools.common.formatting import cell

_DESC_CREATE_SERVICE_REQUEST = classify_tool_desc(
    "Create a service desk ticket for access, content change, or a data-quality "
    "recommendation.\n\n"
    f"Backend lookup: GET {MCP_PATH_SERVICE_REQUEST_TEMPLATES}. "
    f"Backend create: POST {MCP_PATH_SERVICE_REQUESTS}.\n\n"
    "**Not** who-has-access (`access_explorer` / `resolve_object_access`). "
    "**Not** `dq_rule_advisor` — a DQ Rule Recommendation **request** is a ticket. "
    "Resolve objects with asset_explorer first (object_id, object_type, connection_id). "
    "object_id accepts one id, a list, or comma-separated ids "
    "(join when Select Table allowMultiple is true).\n\n"
    "Infer request_type (access / content / dataquality) and object_type (table → oetable). "
    "Call without ticket_template_id/summary to look up the Published and Active template. "
    "If none is returned, stop — never publish or activate a template from MCP. "
    "Confirm gate: confirm_create preview, then write_confirmed_by_user=true.\n\n"
    "Playbook: docs://ovaledge/mcp_workflows (Create a service request).",
    confidential=True,
)

ObjectIdArg = int | list[Any] | str | None


def normalize_request_type(value: str | None) -> str | None:
    if _blank(value):
        return None
    raw = str(value).strip().lower()
    return MCP_SERVICE_REQUEST_TYPE_ALIASES.get(raw, raw.replace(" ", ""))


def normalize_object_type(value: str | None) -> str | None:
    if _blank(value):
        return None
    raw = str(value).strip().lower()
    return MCP_SERVICE_REQUEST_OBJECT_TYPE_ALIASES.get(raw, raw)


_TICKET_DATE_STORE = "%Y/%m/%d %H:%M:%S"
_TICKET_DATE_DISPLAY = "%d-%m-%Y"
_TICKET_DATE_TIME_FORMATS = (
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
)
_TICKET_DATE_FORMATS = (
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
)
_INTERNAL_PREVIEW_FIELD_NAMES = frozenset(
    {
        "select table",
        "select file",
        "requested by",
        "requested for user",
        "service request id",
        "service request link",
        "service request source",
    }
)


def _parse_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed.isdigit():
            parsed = int(trimmed)
            return parsed if parsed > 0 else None
    return None


def normalize_object_ids(value: ObjectIdArg) -> list[int]:
    if value is None or isinstance(value, bool):
        return []
    raw_items: list[object]
    if isinstance(value, int):
        raw_items = [value]
    elif isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, list):
        raw_items = []
        for item in value:
            if isinstance(item, str) and "," in item:
                raw_items.extend(part.strip() for part in item.split(",") if part.strip())
            else:
                raw_items.append(item)
    else:
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for item in raw_items:
        parsed = _parse_positive_int(item)
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        ids.append(parsed)
    return ids


def primary_object_id(object_ids: list[int]) -> int | None:
    return object_ids[0] if object_ids else None


def joined_object_ids(object_ids: list[int]) -> str:
    return ",".join(str(item) for item in object_ids)


def _field_allows_multiple(field: dict[str, Any]) -> bool:
    if field.get("allowMultiple"):
        return True
    data = field.get("fieldData") or field.get("fielddata") or {}
    return isinstance(data, dict) and bool(data.get("allowMultiple"))


def _catalog_selector_value(field: dict[str, Any], object_ids: list[int]) -> int | str | None:
    if not object_ids:
        return None
    if _field_allows_multiple(field):
        return joined_object_ids(object_ids)
    return object_ids[0]


def _parse_ticket_date(value: str) -> datetime | None:
    for fmt in _TICKET_DATE_TIME_FORMATS + _TICKET_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_ticket_datetime(value: str) -> datetime | None:
    for fmt in _TICKET_DATE_TIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def normalize_ticket_date(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = str(value).strip()
    if not trimmed:
        return trimmed
    parsed = _parse_ticket_datetime(trimmed)
    if parsed is None:
        return trimmed
    return parsed.strftime(_TICKET_DATE_STORE)


def format_ticket_date_for_display(value: Any) -> str:
    text = str(value).strip()
    parsed = _parse_ticket_date(text)
    if parsed is None:
        return text
    if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
        return parsed.strftime(_TICKET_DATE_DISPLAY)
    return parsed.strftime(f"{_TICKET_DATE_DISPLAY} %H:%M:%S")


def _date_field_names(fields: list[dict[str, Any]] | None) -> set[str]:
    return {
        str(field.get("fieldName") or "").strip()
        for field in (fields or [])
        if str(field.get("fieldType") or "").lower() == "date"
        and str(field.get("fieldName") or "").strip()
    }


def _is_internal_preview_field(name: str, value: Any, *, object_ids: list[int]) -> bool:
    if name.strip().lower() in _INTERNAL_PREVIEW_FIELD_NAMES:
        return True
    if not object_ids:
        return False
    text = str(value)
    return text == joined_object_ids(object_ids) or text == str(object_ids[0])


def normalize_date_ticket_fields(
    fields: list[dict[str, Any]] | None,
    ticket_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(ticket_fields or {})
    date_names = _date_field_names(fields)
    if not date_names:
        return merged
    for name, value in list(merged.items()):
        if name not in date_names or value in (None, ""):
            continue
        merged[name] = normalize_ticket_date(str(value))
    return merged


def resolve_lookup_args(
    request_type: str | None, object_type: str | None
) -> tuple[str, str] | dict[str, Any]:
    if _blank(request_type):
        return error_payload(
            "request_type is required (for example access).",
            status_code=400,
            error_code="request_type_required",
        )
    if _blank(object_type):
        return error_payload(
            "object_type is required (for example table or oetable).",
            status_code=400,
            error_code="object_type_required",
        )
    return str(request_type), str(object_type)


def build_lookup_params(
    *,
    request_type: str,
    object_type: str,
    connection_type: str | None,
    connection_name: str | None,
    connection_id: int | None,
    ticket_template_id: int | None,
    object_id: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "requestType": request_type,
        "requestObjectType": object_type,
    }
    if not _blank(connection_type):
        params["connType"] = str(connection_type).strip()
    if not _blank(connection_name):
        params["connectionName"] = str(connection_name).strip()
    if connection_id is not None and connection_id > 0:
        params["connectionId"] = connection_id
    if ticket_template_id is not None and ticket_template_id > 0:
        params["ticketTemplateId"] = ticket_template_id
    if object_id is not None and object_id > 0:
        params["objectId"] = object_id
    return params


def create_object_id_payload(object_ids: list[int]) -> int | str | None:
    if not object_ids:
        return None
    if len(object_ids) == 1:
        return object_ids[0]
    return joined_object_ids(object_ids)


def build_create_body(
    *,
    ticket_template_id: int,
    summary: str,
    description: str | None,
    object_ids: list[int],
    object_type: str | None,
    ticket_fields: dict[str, Any] | None,
    custom_fields: dict[str, str] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ticketTemplateId": ticket_template_id,
        "summary": summary.strip(),
    }
    if not _blank(description):
        body["description"] = str(description).strip()
    object_id = create_object_id_payload(object_ids)
    if object_id is not None:
        body["objectId"] = object_id
    if not _blank(object_type):
        body["objectType"] = object_type
    if ticket_fields:
        body["ticketFields"] = ticket_fields
    if custom_fields:
        body["customFields"] = custom_fields
    return body


def _field_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    fields = data.get("fields")
    if not isinstance(fields, list):
        return []
    return [row for row in fields if isinstance(row, dict)]


def _field_default(field: dict[str, Any]) -> Any:
    explicit = field.get("defaultValue")
    if explicit not in (None, ""):
        return explicit
    data = field.get("fieldData") or field.get("fielddata") or {}
    if not isinstance(data, dict):
        return None
    options = data.get("options")
    if not isinstance(options, list):
        return None
    for option in options:
        if isinstance(option, dict) and option.get("selected"):
            value = option.get("value")
            if value not in (None, ""):
                return value
    return None


def _is_requested_for_field(field: dict[str, Any]) -> bool:
    return str(field.get("fieldCode") or "").lower() == "requestedfor" and str(
        field.get("fieldType") or ""
    ).lower() == "oeusers"


def _additional_field_defs(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    defs: list[dict[str, Any]] = []
    for field in fields:
        if str(field.get("fieldType") or "").lower() != "addfields":
            continue
        data = field.get("fieldData") or field.get("fielddata") or {}
        if not isinstance(data, dict):
            continue
        rows = data.get("additionalFields")
        if not isinstance(rows, list):
            continue
        defs.extend(row for row in rows if isinstance(row, dict) and row.get("fieldName"))
    return defs


def _format_additional_fields_section(fields: list[dict[str, Any]]) -> list[str]:
    defs = _additional_field_defs(fields)
    if not defs:
        return []
    lines = [
        "",
        "**Optional additional fields** — ask only if the user wants them; skip the rest.",
        "User replies `Field name = value`. Code fields must use an option below.",
    ]
    for row in defs:
        name = cell(row.get("fieldName"))
        field_type = str(row.get("type") or "text").strip() or "text"
        options = row.get("options")
        option_text = ""
        if isinstance(options, list) and options:
            labels = [str(opt) for opt in options if opt not in (None, "")]
            if labels:
                option_text = f": {', '.join(labels)}"
        lines.append(f"- {name} ({field_type}){option_text}")
    return lines


def merge_default_ticket_fields(
    fields: list[dict[str, Any]],
    ticket_fields: dict[str, Any] | None,
    *,
    object_ids: list[int],
    current_user_id: str | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(ticket_fields or {})
    for field in fields:
        name = str(field.get("fieldName") or "").strip()
        if not name or name in merged:
            continue
        if field.get("filledByCurrentUser") or _is_requested_for_field(field):
            if not _blank(current_user_id):
                merged[name] = current_user_id
            continue
        object_type = str(field.get("objectType") or "").strip().lower()
        selector = _catalog_selector_value(field, object_ids)
        if selector is not None and object_type and object_type not in {"oeusers", ""}:
            merged[name] = selector
            continue
        default = _field_default(field)
        if default is not None:
            merged[name] = default
    return merged


def _is_summary_field(field: dict[str, Any]) -> bool:
    code = str(field.get("fieldCode") or "").strip().lower()
    name = str(field.get("fieldName") or "").strip().lower()
    return code == "summary" or name == "summary"


def remaining_required_ticket_fields(
    fields: list[dict[str, Any]],
    ticket_fields: dict[str, Any] | None,
) -> list[str]:
    """Required create fields still empty after merge (summary is a top-level arg)."""
    merged = ticket_fields or {}
    missing: list[str] = []
    for field in fields:
        if not field.get("requiredOnCreate") or _is_summary_field(field):
            continue
        name = str(field.get("fieldName") or "").strip()
        if not name:
            continue
        if name in merged and not _blank(merged[name]):
            continue
        missing.append(name)
    return missing


def _dropdown_allowed_values(field: dict[str, Any]) -> list[str] | None:
    if str(field.get("fieldType") or "").strip().lower() != "dropdown":
        return None
    data = field.get("fieldData") or field.get("fielddata") or {}
    if not isinstance(data, dict):
        return None
    options = data.get("options")
    if not isinstance(options, list) or not options:
        return None
    allowed: list[str] = []
    for option in options:
        if isinstance(option, dict):
            value = option.get("value")
            if value not in (None, ""):
                allowed.append(str(value))
        elif option not in (None, ""):
            allowed.append(str(option))
    return allowed or None


def validate_ticket_field_values(
    fields: list[dict[str, Any]],
    ticket_fields: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Reject dropdown/date values that cannot be posted; None means ok."""
    if not fields or not ticket_fields:
        return None
    by_name = {
        str(field.get("fieldName") or "").strip(): field
        for field in fields
        if str(field.get("fieldName") or "").strip()
    }
    for name, value in ticket_fields.items():
        field = by_name.get(str(name).strip())
        if field is None or value in (None, ""):
            continue
        allowed = _dropdown_allowed_values(field)
        if allowed is not None and str(value) not in allowed:
            return error_payload(
                f"{name} value '{value}' is not one of: {', '.join(allowed)}.",
                status_code=400,
                error_code="invalid_ticket_field",
            )
        if str(field.get("fieldType") or "").strip().lower() == "date":
            text = str(value).strip()
            if text and _parse_ticket_date(text) is None:
                return error_payload(
                    f"{name} is not a recognized date.",
                    status_code=400,
                    error_code="invalid_ticket_field",
                )
    return None


def format_template_lookup_response(
    body: dict[str, Any], *, object_ids: list[int] | None = None
) -> dict[str, Any]:
    data = _as_dict(body.get("data")) if isinstance(body, dict) else {}
    fields = _field_rows(data)
    current_user = data.get("currentUserId")
    ids = object_ids or []

    def _auto_filled(field: dict[str, Any]) -> bool:
        if field.get("filledByCurrentUser"):
            return True
        if _is_requested_for_field(field) and not _blank(current_user):
            return True
        object_type = str(field.get("objectType") or "").strip().lower()
        if ids and object_type and object_type not in {"oeusers"}:
            return True
        return _field_default(field) is not None

    required = [
        str(f.get("fieldName") or f.get("fieldCode") or "")
        for f in fields
        if f.get("requiredOnCreate") and not _auto_filled(f)
    ]
    lines = [
        "**Service request template**",
        "",
        f"- **Template:** {cell(data.get('ticketTemplateName'))} "
        f"(id `{cell(data.get('ticketTemplateId'))}`)",
        f"- **Request type:** {cell(data.get('requestType'))}",
        f"- **Object type:** {cell(data.get('requestObjectType'))}",
    ]
    if data.get("connType"):
        lines.append(f"- **Connection type:** {cell(data.get('connType'))}")
    if current_user:
        lines.append(
            f"- **Requested By:** `{cell(current_user)}` (logged-in user — do not ask)"
        )
    if required:
        lines.append(f"- **Still needed from user:** {', '.join(required)}")
    if fields:
        lines.extend(["", "| Field | Code | Type | Required |", "|---|---|---|---|"])
        for field in fields:
            default = _field_default(field)
            if field.get("filledByCurrentUser"):
                required_cell = "logged-in user"
            elif _is_requested_for_field(field) and current_user:
                required_cell = f"logged-in user (`{cell(current_user)}`)"
            elif default is not None:
                required_cell = f"default `{cell(default)}`"
            elif field.get("requiredOnCreate"):
                required_cell = "yes"
            else:
                required_cell = "no"
            lines.append(
                f"| {cell(field.get('fieldName'))} | {cell(field.get('fieldCode'))} | "
                f"{cell(field.get('fieldType'))} | {required_cell} |"
            )
    lines.extend(_format_additional_fields_section(fields))
    lines.extend(
        [
            "",
            "Fill summary yourself. Use fieldData/defaultValue for dropdowns. "
            "Ask only for required fields that have no default. Then re-call with "
            "`ticket_template_id`, `object_id`, `summary`, and those field values.",
        ]
    )
    out = dict(body) if isinstance(body, dict) else {"ok": True}
    out["data"] = data
    out["awaitingUserInput"] = True
    out["workflowPhase"] = "collect_fields"
    out["formattedResponse"] = "\n".join(lines)
    out["agentInstruction"] = (
        "Show formattedResponse. Write summary yourself. "
        "Use defaultValue / fieldData selected option for Priority, Permission, "
        "and other dropdowns — do not ask unless the user wants a different value. "
        "Do not ask for Requested By or Requested for User; use currentUserId. "
        "Use object_id for catalog selectors (list or comma-separated ids when "
        "allowMultiple is true). Ask only for remaining required fields. "
        "Never invent Business Description, Technical Description, tags, terms, "
        "or additional field values — ask the user and omit any they skip. "
        "If the user names tags or terms, pass those names in ticket_fields; "
        "invalid names are omitted with a warning — still create. "
        "Additional fields are optional: present fieldData.additionalFields "
        "(name, type, options), collect FieldName=value only for fields they want, "
        "and pass them as custom_fields keyed by fieldName. "
        "If OvalEdge rejects a field value, show that error and ask for a correction. "
        "Re-call with ticket_template_id, object_id, summary, ticket_fields, "
        "and write_confirmed_by_user only after confirm_create."
    )
    return out


def format_create_confirmation_preview(
    *,
    template_name: str | None,
    object_ids: list[int],
    summary: str,
    description: str | None,
    post_body: dict[str, Any],
    fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    date_names = _date_field_names(fields)
    lines = [
        "**Confirm service request creation**",
        "",
    ]
    if template_name and not _blank(template_name):
        lines.append(f"- **Template:** {cell(template_name)}")
    lines.append(f"- **Summary:** {cell(summary)}")
    if description and not _blank(description):
        lines.append(f"- **Description:** {cell(description)}")
    pending_fields = post_body.get("ticketFields")
    if isinstance(pending_fields, dict) and pending_fields:
        for name, value in pending_fields.items():
            field_name = str(name or "").strip()
            if not field_name or _is_internal_preview_field(
                field_name, value, object_ids=object_ids
            ):
                continue
            display = (
                format_ticket_date_for_display(value) if field_name in date_names else value
            )
            lines.append(f"- **{cell(field_name)}:** {cell(display)}")
    lines.extend(
        [
            "",
            "Ask the user to confirm. After they approve, re-call with "
            "`write_confirmed_by_user=true`, `confirmation_token` from this preview, "
            "and the same parameters.",
        ]
    )
    preview: dict[str, Any] = {
        "ok": True,
        "awaitingUserConfirmation": True,
        "workflowPhase": "confirm_create",
        "doNotCreate": True,
        "writeConfirmedByUser": False,
        "formattedResponse": "\n".join(lines),
        "agentInstruction": CREATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingCreate": post_body,
    }
    return attach_confirmation_token(preview, post_body)


def enrich_create_response(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body) if isinstance(body, dict) else {"ok": True, "data": body}
    data = _as_dict(out.get("data"))
    nav = extract_hash_nav_link(str(data.get("navLink") or ""))
    if not nav:
        nav = extract_hash_nav_link(str(data.get("redirectUrl") or ""))
    redirect = str(data.get("redirectUrl") or "").strip()
    if nav:
        data["navLink"] = nav
    if redirect.startswith(("http://", "https://")):
        data["redirectUrl"] = redirect
    elif nav:
        data["redirectUrl"] = build_absolute_nav_url(nav)
    if nav or redirect:
        out["data"] = data
    display = cell(data.get("displayTicketId") or data.get("ticketId"))
    redirect = str(data.get("redirectUrl") or "").strip()
    out["workflowPhase"] = "created"
    created_lines = [f"**Service request created:** {display}"]
    if redirect:
        created_lines.extend(["", f"Open the ticket: {redirect}"])
    warnings = data.get("warnings")
    if isinstance(warnings, list) and warnings:
        created_lines.extend(["", "**Warnings**"])
        created_lines.extend(f"- {cell(item)}" for item in warnings if item not in (None, ""))
    out["formattedResponse"] = "\n".join(created_lines)
    return out
