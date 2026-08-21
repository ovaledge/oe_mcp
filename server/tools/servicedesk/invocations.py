"""Invocation logic for create_service_request."""

from __future__ import annotations

from typing import Any

from server.client import OvalEdgeError
from server.constants import MCP_PATH_SERVICE_REQUEST_TEMPLATES, MCP_PATH_SERVICE_REQUESTS
from server.tools.common import as_dict as _as_dict
from server.tools.common import blank as _blank
from server.tools.common import map_ovaledge_error, ovaledge_client
from server.tools.common.confirm_gate import verify_write_confirmation
from server.tools.common.errors import error_payload
from server.tools.common.tool_logging import logged_tool_invocation
from server.tools.servicedesk.helpers import (
    build_create_body,
    build_lookup_params,
    enrich_create_response,
    format_create_confirmation_preview,
    format_template_lookup_response,
    merge_default_ticket_fields,
    normalize_date_ticket_fields,
    normalize_object_type,
    normalize_request_type,
    validate_lookup_args,
)


def _positive_id(value: int | None) -> int | None:
    if value is None or value <= 0:
        return None
    return value


@logged_tool_invocation
async def _invoke_create_service_request(
    request_type: str | None = None,
    object_type: str | None = None,
    object_id: int | None = None,
    connection_type: str | None = None,
    connection_name: str | None = None,
    connection_id: int | None = None,
    ticket_template_id: int | None = None,
    summary: str | None = None,
    description: str | None = None,
    ticket_fields: dict[str, Any] | None = None,
    custom_fields: dict[str, str] | None = None,
    write_confirmed_by_user: bool = False,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    """Look up a service-desk template or create a request after confirm_create."""
    req_type = normalize_request_type(request_type)
    obj_type = normalize_object_type(object_type)
    template_id = _positive_id(ticket_template_id)
    summary_text = str(summary).strip() if not _blank(summary) else None
    template_name: str | None = None

    needs_lookup = template_id is None or summary_text is None
    if needs_lookup:
        err = validate_lookup_args(req_type, obj_type)
        if err is not None:
            return err
        assert req_type is not None
        assert obj_type is not None
        params = build_lookup_params(
            request_type=req_type,
            object_type=obj_type,
            connection_type=connection_type,
            connection_name=connection_name,
            connection_id=connection_id,
            ticket_template_id=template_id,
            object_id=_positive_id(object_id),
        )
        try:
            async with ovaledge_client() as client:
                body = await client.get(MCP_PATH_SERVICE_REQUEST_TEMPLATES, params=params)
        except OvalEdgeError as e:
            return map_ovaledge_error(e)
        shaped = format_template_lookup_response(
            body if isinstance(body, dict) else {},
            object_id=_positive_id(object_id),
        )
        data = _as_dict(shaped.get("data"))
        resolved = data.get("ticketTemplateId")
        if isinstance(resolved, int) and resolved > 0:
            template_id = resolved
        template_name = str(data.get("ticketTemplateName") or "") or None
        if summary_text is None:
            return shaped
        if template_id is None:
            return error_payload(
                "No Published and Active template was returned. Show the error, "
                "tell the user to publish and activate the template in OvalEdge, "
                "and stop. Never change template status from MCP.",
                status_code=404,
                error_code="template_not_found",
            )
        ticket_fields = merge_default_ticket_fields(
            [row for row in (data.get("fields") or []) if isinstance(row, dict)],
            ticket_fields,
            object_id=_positive_id(object_id),
            current_user_id=str(data.get("currentUserId") or "") or None,
        )

    if template_id is None:
        return error_payload(
            "ticket_template_id is required to create a service request.",
            status_code=400,
            error_code="ticket_template_id_required",
        )
    if summary_text is None:
        return error_payload(
            "summary is required to create a service request.",
            status_code=400,
            error_code="summary_required",
        )

    ticket_fields = normalize_date_ticket_fields(None, ticket_fields)

    post_body = build_create_body(
        ticket_template_id=template_id,
        summary=summary_text,
        description=description,
        object_id=_positive_id(object_id),
        object_type=obj_type,
        ticket_fields=ticket_fields,
        custom_fields=custom_fields,
    )
    if not write_confirmed_by_user:
        return format_create_confirmation_preview(
            template_name=template_name,
            object_id=_positive_id(object_id),
            summary=summary_text,
            description=description,
            post_body=post_body,
        )
    confirm_err = verify_write_confirmation(
        post_body,
        write_confirmed_by_user=write_confirmed_by_user,
        confirmation_token=confirmation_token,
    )
    if confirm_err is not None:
        return confirm_err
    try:
        async with ovaledge_client() as client:
            created = await client.post(MCP_PATH_SERVICE_REQUESTS, body=post_body)
    except OvalEdgeError as e:
        return map_ovaledge_error(e)
    return enrich_create_response(created if isinstance(created, dict) else {})
