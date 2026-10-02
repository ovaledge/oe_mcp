from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.client import OvalEdgeError
from server.constants import (
    MCP_PATH_SERVICE_REQUEST_TEMPLATES,
    MCP_PATH_SERVICE_REQUESTS,
    TOOL_CREATE_SERVICE_REQUEST,
)
from server.tools import servicedesk
from tests.helpers import get_tool_fn
from tests.tools.confirm_test_helpers import invoke_write_confirmed

_LOOKUP = {
    "ok": True,
    "data": {
        "ticketTemplateId": 1005,
        "ticketTemplateName": "Table Access",
        "requestType": "access",
        "requestObjectType": "oetable",
        "connType": "all",
        "currentUserId": "admin",
        "fields": [
            {
                "fieldName": "Summary",
                "fieldCode": "summary",
                "fieldType": "inputtext",
                "requiredOnCreate": True,
            },
            {
                "fieldName": "Select table",
                "fieldCode": "object",
                "fieldType": "catalog",
                "objectType": "oetable",
                "requiredOnCreate": True,
            },
            {
                "fieldName": "Requested By",
                "fieldCode": "createdby",
                "fieldType": "oeusers",
                "requiredOnCreate": True,
                "filledByCurrentUser": True,
            },
            {
                "fieldName": "Priority",
                "fieldCode": "priority",
                "fieldType": "dropdown",
                "requiredOnCreate": True,
                "defaultValue": "Medium",
                "fieldData": {
                    "type": "static",
                    "options": [
                        {"label": "High", "value": "High", "selected": False},
                        {"label": "Medium", "value": "Medium", "selected": True},
                    ],
                },
            },
        ],
    },
}

_CREATED = {
    "ok": True,
    "data": {
        "ticketId": 88,
        "displayTicketId": "SR-88",
        "ticketTemplateId": 1005,
        "summary": "Need access",
        "navLink": "#nav/servicedesk?id=88",
    },
}


class TestCreateServiceRequest:
    async def test_lookup_forwards_aliases_and_connection_filters(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _LOOKUP
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="Access Request",
            object_type="table",
            connection_type="mysql",
            connection_name="local",
            connection_id=12,
        )
        assert out["workflowPhase"] == "collect_fields"
        assert "Table Access" in out["formattedResponse"]
        assert "Requested By" in out["formattedResponse"]
        assert "logged-in user" in out["formattedResponse"]
        assert "`admin`" in out["formattedResponse"]
        required_line = out["formattedResponse"].split("Still needed from user:")[1].split("\n")[0]
        assert "Requested By" not in required_line
        assert "Priority" not in required_line
        assert "default `Medium`" in out["formattedResponse"]
        assert "do not ask" in out["agentInstruction"].lower()
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SERVICE_REQUEST_TEMPLATES,
            params={
                "requestType": "access",
                "requestObjectType": "oetable",
                "connType": "mysql",
                "connectionName": "local",
                "connectionId": 12,
            },
        )
        mock_oe_client.post.assert_not_called()

    async def test_lookup_maps_content_and_dq_aliases(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _LOOKUP
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)

        await fn(request_type="content change", object_type="table")
        mock_oe_client.get.assert_called_with(
            MCP_PATH_SERVICE_REQUEST_TEMPLATES,
            params={"requestType": "content", "requestObjectType": "oetable"},
        )

        await fn(
            request_type="Data Quality Rule Recommendation",
            object_type="oetable",
        )
        mock_oe_client.get.assert_called_with(
            MCP_PATH_SERVICE_REQUEST_TEMPLATES,
            params={"requestType": "dataquality", "requestObjectType": "oetable"},
        )

    async def test_lookup_requires_request_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(object_type="oetable")
        assert out["error_code"] == "request_type_required"
        mock_oe_client.get.assert_not_called()

    async def test_lookup_requires_object_type(self, mock_oe_client: AsyncMock) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(request_type="access")
        assert out["error_code"] == "object_type_required"
        mock_oe_client.get.assert_not_called()

    async def test_lookup_maps_ovaledge_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(404, "missing")
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(request_type="access", object_type="oetable")
        assert out["status_code"] == 404
        assert "missing" in out["error"]

    async def test_lookup_maps_field_dependency_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.get.side_effect = OvalEdgeError(
            400,
            "Service Request cannot be created through MCP because the selected "
            "Service Desk template contains Depends-On fields. Please create the "
            "request through the OvalEdge application or contact your administrator.",
        )
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(request_type="access", object_type="oetable")
        assert out["status_code"] == 400
        assert "Depends-On fields" in out["error"]

    async def test_summary_without_template_looks_up_then_previews(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _LOOKUP
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            object_id=3337,
            summary="Need access",
            description="Please grant",
        )
        assert out["workflowPhase"] == "confirm_create"
        assert out["confirmationToken"]
        pending = out["pendingCreate"]["ticketFields"]
        assert pending["Select table"] == 3337
        assert pending["Requested By"] == "admin"
        assert pending["Priority"] == "Medium"
        preview = out["formattedResponse"]
        assert "Table Access" in preview
        assert "Need access" in preview
        assert "Please grant" in preview
        assert "Priority" in preview
        assert "Template id" not in preview
        assert "Request type" not in preview
        assert "Object type" not in preview
        assert "Object id" not in preview
        assert "oetable" not in preview
        assert "3337" not in preview
        mock_oe_client.post.assert_not_called()

    async def test_confirmed_create_posts_body(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = _CREATED
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await invoke_write_confirmed(
            fn,
            ticket_template_id=1005,
            summary="Need access",
            description="Please grant",
            object_id=3337,
            object_type="oetable",
            ticket_fields={"Priority": "High"},
            custom_fields={"tcf1": "note"},
        )
        assert out["workflowPhase"] == "created"
        created = out["formattedResponse"]
        assert "SR-88" in created
        assert "Open the ticket:" in created
        assert "https://mock.ovaledge.com/#nav/servicedesk?id=88" in created
        assert out["data"]["redirectUrl"].startswith("https://mock.ovaledge.com/")
        assert out["data"]["navLink"] == "#nav/servicedesk?id=88"
        mock_oe_client.get.assert_not_called()
        mock_oe_client.post.assert_called_once_with(
            MCP_PATH_SERVICE_REQUESTS,
            body={
                "ticketTemplateId": 1005,
                "summary": "Need access",
                "description": "Please grant",
                "objectId": 3337,
                "objectType": "oetable",
                "ticketFields": {"Priority": "High"},
                "customFields": {"tcf1": "note"},
            },
        )

    async def test_confirmed_create_does_not_rewrite_dates_without_lookup(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = _CREATED
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await invoke_write_confirmed(
            fn,
            ticket_template_id=1005,
            summary="Need access",
            object_id=3337,
            object_type="oetable",
            ticket_fields={"Expiration Date": "25-10-2026", "Mandate": "yes"},
        )
        assert out["workflowPhase"] == "created"
        posted = mock_oe_client.post.call_args.kwargs["body"]
        assert posted["ticketFields"]["Expiration Date"] == "25-10-2026"
        assert posted["ticketFields"]["Mandate"] == "yes"

    async def test_preview_hides_internal_ids_and_formats_dates(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _LOOKUP
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            object_id=3337,
            summary="Need access",
            ticket_fields={"Expiration Date": "25-10-2026", "Permission": "Data Preview"},
        )
        preview = out["formattedResponse"]
        assert out["workflowPhase"] == "confirm_create"
        assert "Expiration Date" in preview
        assert "25-10-2026" in preview
        assert "2026/10/25" not in preview
        assert "00:00:00" not in preview
        assert "Data Preview" in preview
        assert "Template id" not in preview
        assert "1005" not in preview
        assert "oetable" not in preview
        assert "3337" not in preview
        assert out["pendingCreate"]["ticketTemplateId"] == 1005
        assert out["pendingCreate"]["objectId"] == 3337
        mock_oe_client.post.assert_not_called()

    async def test_lookup_forwards_object_id_and_additional_fields(
        self, mock_oe_client: AsyncMock
    ) -> None:
        lookup = {
            "ok": True,
            "data": {
                **_LOOKUP["data"],
                "fields": [
                    *_LOOKUP["data"]["fields"],
                    {
                        "fieldName": "Additional Fields",
                        "fieldCode": "addfields",
                        "fieldType": "addfields",
                        "requiredOnCreate": False,
                        "fieldData": {
                            "additionalFields": [
                                {"fieldName": "Table_text", "type": "text"},
                                {
                                    "fieldName": "SD for CCF",
                                    "type": "code",
                                    "options": ["SD for CCF1", "SD for CCF2"],
                                },
                            ]
                        },
                    },
                ],
            },
        }
        mock_oe_client.get.return_value = lookup
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="content",
            object_type="oetable",
            object_id=46148,
        )
        assert "Optional additional fields" in out["formattedResponse"]
        assert "Table_text (text)" in out["formattedResponse"]
        assert "SD for CCF (code): SD for CCF1, SD for CCF2" in out["formattedResponse"]
        assert "invalid names are omitted" in out["agentInstruction"]
        assert "never invent" in out["agentInstruction"].lower()
        assert "show that error" in out["agentInstruction"].lower()
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SERVICE_REQUEST_TEMPLATES,
            params={
                "requestType": "content",
                "requestObjectType": "oetable",
                "objectId": 46148,
            },
        )

    async def test_created_response_shows_warnings(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.return_value = {
            "ok": True,
            "data": {
                **_CREATED["data"],
                "warnings": [
                    'Tag "Fake" was not found and was omitted from the request.',
                ],
            },
        }
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await invoke_write_confirmed(
            fn,
            ticket_template_id=1005,
            summary="Need access",
        )
        created = out["formattedResponse"]
        assert "SR-88" in created
        assert "**Warnings**" in created
        assert "Fake" in created

    async def test_create_maps_post_error(self, mock_oe_client: AsyncMock) -> None:
        mock_oe_client.post.side_effect = OvalEdgeError(400, "bad ticket")
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await invoke_write_confirmed(
            fn,
            ticket_template_id=1005,
            summary="Need access",
        )
        assert out["status_code"] == 400
        assert "bad ticket" in out["error"]

    async def test_description_mentions_backends(self) -> None:
        from server.tools.servicedesk.helpers import _DESC_CREATE_SERVICE_REQUEST

        assert MCP_PATH_SERVICE_REQUEST_TEMPLATES in _DESC_CREATE_SERVICE_REQUEST
        assert MCP_PATH_SERVICE_REQUESTS in _DESC_CREATE_SERVICE_REQUEST
        assert "docs://ovaledge/mcp_workflows" in _DESC_CREATE_SERVICE_REQUEST
        assert "asset_explorer" in _DESC_CREATE_SERVICE_REQUEST
        assert "never publish or activate a template from MCP" in _DESC_CREATE_SERVICE_REQUEST
        assert "access_explorer" in _DESC_CREATE_SERVICE_REQUEST
        assert "dq_rule_advisor" in _DESC_CREATE_SERVICE_REQUEST
        assert "write_confirmed_by_user" in _DESC_CREATE_SERVICE_REQUEST
        assert "allowMultiple" in _DESC_CREATE_SERVICE_REQUEST
        assert "I want access to Loan_Data table" not in _DESC_CREATE_SERVICE_REQUEST
        assert "these tables" not in _DESC_CREATE_SERVICE_REQUEST

    async def test_lookup_skips_non_positive_connection_id(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _LOOKUP
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        await fn(request_type="access", object_type="oetable", connection_id=0)
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SERVICE_REQUEST_TEMPLATES,
            params={"requestType": "access", "requestObjectType": "oetable"},
        )

    async def test_summary_without_returned_template_id_is_template_not_found(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"fields": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            summary="Need access",
        )
        assert out["error_code"] == "template_not_found"
        mock_oe_client.post.assert_not_called()

    async def test_lookup_without_template_id_is_template_not_found(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"fields": []}}
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(request_type="access", object_type="oetable")
        assert out["error_code"] == "template_not_found"
        mock_oe_client.post.assert_not_called()

    async def test_summary_without_object_id_stays_collect_fields(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _LOOKUP
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            summary="Need access",
        )
        assert out["workflowPhase"] == "collect_fields"
        assert "Select table" in out["formattedResponse"]
        mock_oe_client.get.assert_called_once()
        mock_oe_client.post.assert_not_called()

    async def test_invalid_dropdown_value_rejected_before_preview(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _LOOKUP
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            object_id=3337,
            summary="Need access",
            ticket_fields={"Priority": "Urgent"},
        )
        assert out["error_code"] == "invalid_ticket_field"
        assert "Priority" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_confirmed_create_posts_joined_selector_from_ticket_fields(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = _CREATED
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await invoke_write_confirmed(
            fn,
            ticket_template_id=1005,
            summary="Need access",
            object_id=[3337, 3338],
            object_type="oetable",
            ticket_fields={"Select table": "3337,3338"},
        )
        assert out["workflowPhase"] == "created"
        mock_oe_client.get.assert_not_called()
        posted = mock_oe_client.post.call_args.kwargs["body"]
        assert posted["objectId"] == "3337,3338"
        assert posted["ticketFields"]["Select table"] == "3337,3338"

    async def test_multi_object_ids_join_when_allow_multiple(
        self, mock_oe_client: AsyncMock
    ) -> None:
        lookup = {
            "ok": True,
            "data": {
                **_LOOKUP["data"],
                "fields": [
                    {
                        **_LOOKUP["data"]["fields"][1],
                        "allowMultiple": True,
                    },
                    *_LOOKUP["data"]["fields"][2:],
                ],
            },
        }
        mock_oe_client.get.return_value = lookup
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            object_id=[3337, 3338, 3339],
            summary="Need access",
        )
        assert out["workflowPhase"] == "confirm_create"
        pending = out["pendingCreate"]["ticketFields"]
        assert pending["Select table"] == "3337,3338,3339"
        assert out["pendingCreate"]["objectId"] == "3337,3338,3339"
        assert "3337,3338,3339" not in out["formattedResponse"]
        mock_oe_client.get.assert_called_once_with(
            MCP_PATH_SERVICE_REQUEST_TEMPLATES,
            params={
                "requestType": "access",
                "requestObjectType": "oetable",
                "objectId": 3337,
            },
        )

    async def test_comma_separated_object_ids_join_when_allow_multiple(
        self, mock_oe_client: AsyncMock
    ) -> None:
        lookup = {
            "ok": True,
            "data": {
                **_LOOKUP["data"],
                "fields": [
                    {
                        **_LOOKUP["data"]["fields"][1],
                        "fieldData": {"allowMultiple": True},
                    },
                    *_LOOKUP["data"]["fields"][2:],
                ],
            },
        }
        mock_oe_client.get.return_value = lookup
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            object_id="3337, 3338",
            summary="Need access",
        )
        assert out["pendingCreate"]["ticketFields"]["Select table"] == "3337,3338"
        assert out["pendingCreate"]["objectId"] == "3337,3338"

    async def test_confirmed_create_posts_csv_object_ids_without_selector_field(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.post.return_value = _CREATED
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await invoke_write_confirmed(
            fn,
            ticket_template_id=1000,
            summary="Access request for ticketfield, ticket2, and tickettemplate tables",
            object_id="1866,1858,1871",
            object_type="oetable",
            request_type="access",
            ticket_fields={
                "Priority": "Medium",
                "Permission": "Data Read",
                "Expiration Date": "2026-12-20",
            },
        )
        assert out["workflowPhase"] == "created"
        posted = mock_oe_client.post.call_args.kwargs["body"]
        assert posted["objectId"] == "1866,1858,1871"
        assert posted["ticketFields"]["Priority"] == "Medium"

    async def test_multi_object_ids_when_not_allow_multiple_returns_error(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mock_oe_client.get.return_value = _LOOKUP
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            object_id=[3337, 3338],
            summary="Need access",
        )
        assert out["error_code"] == "object_id_multiple_not_allowed"
        assert "Select table" in out["error"]
        mock_oe_client.post.assert_not_called()

    async def test_invalid_object_id_tokens_return_error(
        self, mock_oe_client: AsyncMock
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            object_id="1866,abc,1858",
            summary="Need access",
            ticket_template_id=1005,
        )
        assert out["error_code"] == "invalid_object_id"
        assert "abc" in out["error"]
        mock_oe_client.get.assert_not_called()
        mock_oe_client.post.assert_not_called()

    async def test_lookup_date_field_normalizes_datetime_not_name_matches(
        self, mock_oe_client: AsyncMock
    ) -> None:
        lookup = {
            "ok": True,
            "data": {
                **_LOOKUP["data"],
                "fields": [
                    *_LOOKUP["data"]["fields"],
                    {
                        "fieldName": "Expiration Date",
                        "fieldCode": "expiration",
                        "fieldType": "date",
                        "requiredOnCreate": False,
                    },
                ],
            },
        }
        mock_oe_client.get.return_value = lookup
        mcp = FastMCP(name="test", version="0.0.1")
        servicedesk.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_SERVICE_REQUEST)
        out = await fn(
            request_type="access",
            object_type="oetable",
            object_id=3337,
            summary="Need access",
            ticket_fields={
                "Expiration Date": "25-10-2026 14:30:00",
                "Mandate": "yes",
            },
        )
        pending = out["pendingCreate"]["ticketFields"]
        assert pending["Expiration Date"] == "2026/10/25 14:30:00"
        assert pending["Mandate"] == "yes"
        preview = out["formattedResponse"]
        assert "25-10-2026 14:30:00" in preview
        assert "2026/10/25" not in preview


class TestCreateServiceRequestHelpers:
    def test_normalize_object_ids_accepts_int_list_and_csv(self) -> None:
        from server.tools.servicedesk.helpers import parse_object_ids

        assert parse_object_ids(12).ids == [12]
        assert parse_object_ids([12, 13, 12]).ids == [12, 13]
        mixed = parse_object_ids("12, 13, 0, x")
        assert mixed.ids == [12, 13]
        assert mixed.rejected_tokens == ["0", "x"]
        assert parse_object_ids(None).ids == []
        assert parse_object_ids(-1).rejected_tokens == ["-1"]
        overflow = parse_object_ids(2_147_483_648)
        assert overflow.ids == []
        assert overflow.rejected_tokens == ["2147483648"]

    def test_merge_default_ticket_fields_overwrites_selector_from_object_ids(self) -> None:
        from server.tools.servicedesk.helpers import merge_default_ticket_fields

        fields = [
            {
                "fieldName": "Select table",
                "fieldType": "catalog",
                "objectType": "oetable",
                "allowMultiple": True,
            }
        ]
        merged = merge_default_ticket_fields(
            fields,
            {"Select table": 9999},
            object_ids=[1866, 1858],
            current_user_id=None,
        )
        assert merged["Select table"] == "1866,1858"
        from server.tools.servicedesk.helpers import create_object_id_payload

        assert create_object_id_payload([]) is None
        assert create_object_id_payload([1866]) == 1866
        assert create_object_id_payload([1866, 1858, 1871]) == "1866,1858,1871"

    def test_normalize_date_ticket_fields_only_typed_date(self) -> None:
        from server.tools.servicedesk.helpers import normalize_date_ticket_fields

        fields = [{"fieldName": "Expiration Date", "fieldType": "date"}]
        out = normalize_date_ticket_fields(
            fields,
            {
                "Expiration Date": "25-10-2026",
                "Invalidate": "keep",
                "Mandate": "yes",
            },
        )
        assert out["Expiration Date"] == "25-10-2026"
        assert out["Invalidate"] == "keep"
        assert out["Mandate"] == "yes"

        typed = normalize_date_ticket_fields(
            fields,
            {"Expiration Date": "25-10-2026 14:30:00"},
        )
        assert typed["Expiration Date"] == "2026/10/25 14:30:00"

        untyped = normalize_date_ticket_fields(
            None,
            {"Expiration Date": "25-10-2026 14:30:00"},
        )
        assert untyped["Expiration Date"] == "25-10-2026 14:30:00"

    def test_enrich_create_response_prefers_backend_redirect_url(self) -> None:
        from server.tools.servicedesk.helpers import enrich_create_response

        out = enrich_create_response(
            {
                "ok": True,
                "data": {
                    "ticketId": 88,
                    "displayTicketId": "SR-88",
                    "navLink": "#nav/servicedesk?id=88",
                    "redirectUrl": "https://prod.example/ovaledge/#nav/servicedesk?id=88",
                },
            }
        )
        assert out["data"]["navLink"] == "#nav/servicedesk?id=88"
        assert (
            out["data"]["redirectUrl"]
            == "https://prod.example/ovaledge/#nav/servicedesk?id=88"
        )
        assert "https://prod.example/ovaledge/#nav/servicedesk?id=88" in out["formattedResponse"]

    def test_enrich_create_response_builds_redirect_from_nav_link(self) -> None:
        from server.tools.servicedesk.helpers import enrich_create_response

        out = enrich_create_response(
            {
                "ok": True,
                "data": {
                    "ticketId": 88,
                    "displayTicketId": "SR-88",
                    "navLink": "#nav/servicedesk?id=88",
                },
            }
        )
        assert out["data"]["redirectUrl"] == "https://mock.ovaledge.com/#nav/servicedesk?id=88"
        assert out["data"]["navLink"] == "#nav/servicedesk?id=88"

    def test_remaining_required_skips_summary_and_filled_values(self) -> None:
        from server.tools.servicedesk.helpers import remaining_required_ticket_fields

        fields = [
            {"fieldName": "Summary", "fieldCode": "summary", "requiredOnCreate": True},
            {"fieldName": "Select table", "requiredOnCreate": True},
            {"fieldName": "Priority", "requiredOnCreate": True},
        ]
        assert remaining_required_ticket_fields(fields, {"Priority": "Medium"}) == [
            "Select table"
        ]
        assert remaining_required_ticket_fields(
            fields, {"Select table": 3337, "Priority": "Medium"}
        ) == []

    def test_validate_ticket_field_values_rejects_unknown_dropdown(self) -> None:
        from server.tools.servicedesk.helpers import validate_ticket_field_values

        fields = [
            {
                "fieldName": "Priority",
                "fieldType": "dropdown",
                "fieldData": {
                    "options": [{"label": "High", "value": "High"}],
                },
            }
        ]
        err = validate_ticket_field_values(fields, {"Priority": "Urgent"})
        assert err is not None
        assert err["error_code"] == "invalid_ticket_field"
        assert validate_ticket_field_values(fields, {"Priority": "High"}) is None

