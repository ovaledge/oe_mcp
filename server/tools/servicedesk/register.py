"""MCP tool registration for service-desk workflows."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from server.tools.common.annotations import GOVERNED_CREATE
from server.tools.common.confirm_gate import CONFIRMATION_TOKEN_PARAM_DESCRIPTION
from server.tools.servicedesk.helpers import _DESC_CREATE_SERVICE_REQUEST
from server.tools.servicedesk.invocations import _invoke_create_service_request


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Create a service request",
        description=_DESC_CREATE_SERVICE_REQUEST,
        annotations=GOVERNED_CREATE,
    )
    async def create_service_request(
        request_type: Annotated[
            str | None,
            Field(description="Request type, e.g. access. Required for template lookup."),
        ] = None,
        object_type: Annotated[
            str | None,
            Field(description="Catalog object type, e.g. table or oetable."),
        ] = None,
        object_id: Annotated[
            int | None,
            Field(description="Catalog object id from asset_explorer (required on create)."),
        ] = None,
        connection_type: Annotated[
            str | None,
            Field(description="Optional connector type from the asset (maps to connType)."),
        ] = None,
        connection_name: Annotated[
            str | None,
            Field(description="Optional connector name from the asset."),
        ] = None,
        connection_id: Annotated[
            int | None,
            Field(description="Optional connection id from the asset."),
        ] = None,
        ticket_template_id: Annotated[
            int | None,
            Field(description="Template id from lookup; required to create."),
        ] = None,
        summary: Annotated[
            str | None,
            Field(description="Ticket summary; required to create. Omit to look up the template."),
        ] = None,
        description: Annotated[
            str | None,
            Field(description="Optional ticket description."),
        ] = None,
        ticket_fields: Annotated[
            dict[str, Any] | None,
            Field(description="Extra template fields keyed by fieldName from lookup."),
        ] = None,
        custom_fields: Annotated[
            dict[str, str] | None,
            Field(description="Additional field values keyed by fieldName from lookup."),
        ] = None,
        write_confirmed_by_user: Annotated[
            bool,
            Field(
                description="Set true only after the user approves the confirm_create preview.",
            ),
        ] = False,
        confirmation_token: Annotated[
            str | None,
            Field(description=CONFIRMATION_TOKEN_PARAM_DESCRIPTION),
        ] = None,
    ) -> dict[str, Any]:
        """Create a service desk request or look up the matching template."""
        return await _invoke_create_service_request(
            request_type=request_type,
            object_type=object_type,
            object_id=object_id,
            connection_type=connection_type,
            connection_name=connection_name,
            connection_id=connection_id,
            ticket_template_id=ticket_template_id,
            summary=summary,
            description=description,
            ticket_fields=ticket_fields,
            custom_fields=custom_fields,
            write_confirmed_by_user=write_confirmed_by_user,
            confirmation_token=confirmation_token,
        )
