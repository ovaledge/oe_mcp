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
from server.nav_links import build_absolute_nav_url
from server.tools.common import as_dict as _as_dict
from server.tools.common import blank as _blank
from server.tools.common.confirm_gate import attach_confirmation_token
from server.tools.common.descriptions import classify_tool_desc
from server.tools.common.errors import error_payload
from server.tools.governance._shared import _CREATE_CONFIRM_AGENT_INSTRUCTION, _cell

_DESC_CREATE_SERVICE_REQUEST = classify_tool_desc(
    "Create a service desk ticket. Trigger: "
    '"I want access to Loan_Data table", '
    '"I need Data Read access for Customer table", '
    '"Create a content change request for Employee table", '
    '"Raise a Data Quality Rule Recommendation request", '
    '"I want access for Loan_Data, Employee_Details and Sales_Target", '
    '"Raise an access request for these tables".\n\n'
    f"Backend lookup: GET {MCP_PATH_SERVICE_REQUEST_TEMPLATES}. "
    f"Backend create: POST {MCP_PATH_SERVICE_REQUESTS}.\n\n"
    "**Not** who-has-access (`access_explorer` / `resolve_object_access`). "
    "**Not** `dq_rule_advisor` — a DQ Rule Recommendation **request** is a ticket. "
    "Resolve objects with asset_explorer first (object_id, object_type, connection_id).\n\n"
    "Infer request_type (access / content / dataquality) and object_type (table → oetable). "
    "Call without ticket_template_id/summary to look up the Published and Active "
    "template and required fields. "
    "Templates with field dependencies (dependsOn) are skipped, except Tags, Terms, "
    "Business Description, Technical Description, and Additional Fields. "
    "If none is returned, stop — never publish or activate a template from MCP. "
    "Honor lookup field validations (maxlength, dropdown options, additional-field "
    "types, user/role/team). "
    "Confirm gate: confirm_create preview, then write_confirmed_by_user=true.\n\n"
    "Playbook: docs://ovaledge/mcp_workflows (Create a service request)."
)


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


def _parse_ticket_date(value: str) -> datetime | None:
    for fmt in _TICKET_DATE_TIME_FORMATS + _TICKET_DATE_FORMATS:
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
    parsed = _parse_ticket_date(trimmed)
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


def _is_internal_preview_field(name: str, value: Any, *, object_id: int | None) -> bool:
    if name.strip().lower() in _INTERNAL_PREVIEW_FIELD_NAMES:
        return True
    return object_id is not None and str(value) == str(object_id)


def normalize_date_ticket_fields(
    fields: list[dict[str, Any]] | None,
    ticket_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(ticket_fields or {})
    date_names = {
        str(field.get("fieldName") or "").strip()
        for field in (fields or [])
        if str(field.get("fieldType") or "").lower() == "date"
        and str(field.get("fieldName") or "").strip()
    }
    for name, value in list(merged.items()):
        if name not in date_names and "date" not in name.lower():
            continue
        if value in (None, ""):
            continue
        merged[name] = normalize_ticket_date(str(value))
    return merged


def validate_lookup_args(
    request_type: str | None, object_type: str | None
) -> dict[str, Any] | None:
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
    return None


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
    if connection_id is not None:
        params["connectionId"] = connection_id
    if ticket_template_id is not None and ticket_template_id > 0:
        params["ticketTemplateId"] = ticket_template_id
    if object_id is not None and object_id > 0:
        params["objectId"] = object_id
    return params


def build_create_body(
    *,
    ticket_template_id: int,
    summary: str,
    description: str | None,
    object_id: int | None,
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
    if object_id is not None and object_id > 0:
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
        name = _cell(row.get("fieldName"))
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
    object_id: int | None,
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
        if object_id and object_type and object_type not in {"oeusers", ""}:
            merged[name] = object_id
            continue
        default = _field_default(field)
        if default is not None:
            merged[name] = default
    return merged


def format_template_lookup_response(
    body: dict[str, Any], *, object_id: int | None = None
) -> dict[str, Any]:
    data = _as_dict(body.get("data")) if isinstance(body, dict) else {}
    fields = _field_rows(data)
    current_user = data.get("currentUserId")

    def _auto_filled(field: dict[str, Any]) -> bool:
        if field.get("filledByCurrentUser"):
            return True
        if _is_requested_for_field(field) and not _blank(current_user):
            return True
        object_type = str(field.get("objectType") or "").strip().lower()
        if object_id and object_type and object_type not in {"oeusers"}:
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
        f"- **Template:** {_cell(data.get('ticketTemplateName'))} "
        f"(id `{_cell(data.get('ticketTemplateId'))}`)",
        f"- **Request type:** {_cell(data.get('requestType'))}",
        f"- **Object type:** {_cell(data.get('requestObjectType'))}",
    ]
    if data.get("connType"):
        lines.append(f"- **Connection type:** {_cell(data.get('connType'))}")
    if current_user:
        lines.append(
            f"- **Requested By:** `{_cell(current_user)}` (logged-in user — do not ask)"
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
                required_cell = f"logged-in user (`{_cell(current_user)}`)"
            elif default is not None:
                required_cell = f"default `{_cell(default)}`"
            elif field.get("requiredOnCreate"):
                required_cell = "yes"
            else:
                required_cell = "no"
            lines.append(
                f"| {_cell(field.get('fieldName'))} | {_cell(field.get('fieldCode'))} | "
                f"{_cell(field.get('fieldType'))} | {required_cell} |"
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
        "Use object_id for catalog selectors. Ask only for remaining required fields. "
        "Never invent Business Description, Technical Description, tags, terms, "
        "or additional field values — ask the user and omit any they skip. "
        "If the user names tags or terms, pass those names in ticket_fields; "
        "invalid names are omitted with a warning — still create. "
        "Additional fields are optional: present fieldData.additionalFields "
        "(name, type, options), collect FieldName=value only for fields they want, "
        "and pass them as custom_fields keyed by fieldName. "
        "Honor each field's validations (character limit, dropdown options). "
        "Additional field types: text maxlength, code=predefined options only, "
        "number=numeric, date requires date and time, URL must be a valid hyperlink. "
        "Author/Viewer user and role fields accept only that license type; teams must exist. "
        "Re-call with ticket_template_id, object_id, summary, ticket_fields, "
        "and write_confirmed_by_user only after confirm_create."
    )
    return out


def format_create_confirmation_preview(
    *,
    template_name: str | None,
    object_id: int | None,
    summary: str,
    description: str | None,
    post_body: dict[str, Any],
) -> dict[str, Any]:
    lines = [
        "**Confirm service request creation**",
        "",
    ]
    if template_name and not _blank(template_name):
        lines.append(f"- **Template:** {_cell(template_name)}")
    lines.append(f"- **Summary:** {_cell(summary)}")
    if description and not _blank(description):
        lines.append(f"- **Description:** {_cell(description)}")
    pending_fields = post_body.get("ticketFields")
    if isinstance(pending_fields, dict) and pending_fields:
        for name, value in pending_fields.items():
            field_name = str(name or "").strip()
            if not field_name or _is_internal_preview_field(
                field_name, value, object_id=object_id
            ):
                continue
            display = (
                format_ticket_date_for_display(value)
                if "date" in field_name.lower()
                else value
            )
            lines.append(f"- **{_cell(field_name)}:** {_cell(display)}")
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
        "agentInstruction": _CREATE_CONFIRM_AGENT_INSTRUCTION,
        "pendingCreate": post_body,
    }
    return attach_confirmation_token(preview, post_body)


def enrich_create_response(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body) if isinstance(body, dict) else {"ok": True, "data": body}
    data = _as_dict(out.get("data"))
    nav = str(data.get("navLink") or "")
    if nav:
        data["redirectUrl"] = build_absolute_nav_url(nav)
        out["data"] = data
    display = _cell(data.get("displayTicketId") or data.get("ticketId"))
    redirect = str(data.get("redirectUrl") or "").strip()
    out["workflowPhase"] = "created"
    created_lines = [f"**Service request created:** {display}"]
    if redirect:
        created_lines.extend(["", f"Open the ticket: {redirect}"])
    warnings = data.get("warnings")
    if isinstance(warnings, list) and warnings:
        created_lines.extend(["", "**Warnings**"])
        created_lines.extend(f"- {_cell(item)}" for item in warnings if item not in (None, ""))
    out["formattedResponse"] = "\n".join(created_lines)
    return out
