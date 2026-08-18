"""Tests for access response enrichment."""

from server.constants import MCP_SOURCE_SYSTEM_UNSUPPORTED_CODE
from server.tools.access.helpers import (
    enrich_get_user_object_access_response,
    is_dam_connector_unsupported,
)


class TestEnrichGetUserObjectAccessResponse:
    def test_oestory_inherited_from_adds_advisory(self) -> None:
        result = {
            "ok": True,
            "data": {
                "objectType": "oestory",
                "objectId": 42,
                "inheritedFrom": {
                    "objectId": 1004,
                    "objectType": "storyzone",
                    "objectName": "OvalEdge",
                },
            },
        }
        out = enrich_get_user_object_access_response(result)
        msg = out["data"]["advisoryMessage"]
        assert "inherited from Story Zone" in msg
        assert "OvalEdge" in msg
        assert "no direct catalog permissions" in msg

    def test_non_oestory_unchanged(self) -> None:
        result = {
            "ok": True,
            "data": {
                "objectType": "dp_domain",
                "objectId": 1028,
            },
        }
        out = enrich_get_user_object_access_response(result)
        assert "advisoryMessage" not in out["data"]


class TestIsDamConnectorUnsupported:
    def test_unsupported_connector_message_matches(self) -> None:
        result = {
            "status_code": 400,
            "error": (
                "Connector type mysql is not supported for native DAM access. "
                "Supported connector types: redshift, snowflake, tableau. "
                "Continue with operation=catalog_access."
            ),
        }
        assert is_dam_connector_unsupported(result) is True

    def test_unsupported_connector_error_code_matches_without_english_copy(self) -> None:
        result = {
            "status_code": 400,
            "error_code": MCP_SOURCE_SYSTEM_UNSUPPORTED_CODE,
            "error": (
                "source_system no compatible. "
                "Valores admitidos: redshift, snowflake, tableau."
            ),
        }
        assert is_dam_connector_unsupported(result) is True

    def test_hint_mismatch_does_not_match(self) -> None:
        result = {
            "status_code": 400,
            "error": (
                "sourceSystem snowflake does not match connectionId type redshift. "
                "Pass a matching sourceSystem or omit sourceSystem."
            ),
        }
        assert is_dam_connector_unsupported(result) is False
