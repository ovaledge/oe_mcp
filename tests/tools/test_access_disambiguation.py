"""Who-has-access disambiguation: signal detection and server gate."""

from __future__ import annotations

import pytest

from server.constants import (
    MCP_ACCESS_INTENT_CATALOG_ACL,
    MCP_ACCESS_INTENT_NATIVE,
)
from server.tools.access.disambiguation import (
    detect_access_intent_from_question,
    validate_access_intent_confirmed,
)


class TestDetectAccessIntentFromQuestion:
    @pytest.mark.parametrize(
        "question",
        [
            "Who has native access to ORDERS?",
            "What remote privileges does svc have?",
            "Show DAM grants on BUSINESS.BANKING",
            "Who has source system access to customer1?",
            "List source-system SELECT on the table",
        ],
    )
    def test_native_signals_skip_disambiguation(self, question: str) -> None:
        assert detect_access_intent_from_question(question) == MCP_ACCESS_INTENT_NATIVE

    @pytest.mark.parametrize(
        "question",
        [
            "Who has catalog access to Finance schema?",
            "What is the OvalEdge security ACL on ORDERS?",
            "Which OE security roles can read this?",
            "Show catalog ACL for customer1",
            "Who has catalog permissions on the report?",
        ],
    )
    def test_catalog_acl_signals_skip_disambiguation(self, question: str) -> None:
        assert detect_access_intent_from_question(question) == MCP_ACCESS_INTENT_CATALOG_ACL

    @pytest.mark.parametrize(
        "question",
        [
            "Who has access to BUSINESS.BANKING schema in Snowflake?",
            "Who has access to the customer1 table in redshift1 in Redshift?",
            "Who has access to prod_db.public.orders?",
            "Who can see this table in Tableau?",
            "Who has access to ORDERS?",
        ],
    )
    def test_platform_name_alone_requires_disambiguation(self, question: str) -> None:
        assert detect_access_intent_from_question(question) is None


class TestDisambiguationUserMessage:
    def test_message_names_access_explorer(self) -> None:
        from server.constants import (
            MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
            TOOL_ACCESS_EXPLORER,
        )

        assert TOOL_ACCESS_EXPLORER in MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE
        assert "operation=source_system_access" in MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE
        assert "operation=catalog_access" in MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE
        assert "get_user_object_access" not in MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE
        assert "OvalEdge catalog permissions" in MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE
        assert "OvalEdge catalog ACL" not in MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE

    def test_discovery_vs_access_constant_routes_first_person(self) -> None:
        from server.constants import (
            MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC,
            MCP_ACCESS_DISAMBIGUATION_RULE_DOC,
            MCP_ACCESS_DISAMBIGUATION_SEARCH_GUARD_DOC,
            MCP_CATALOG_DISCOVERY_VS_ACCESS_DOC,
            TOOL_ACCESS_EXPLORER,
            TOOL_ASSET_EXPLORER,
            TOOL_CREATE_SERVICE_REQUEST,
        )

        assert TOOL_ASSET_EXPLORER in MCP_CATALOG_DISCOVERY_VS_ACCESS_DOC
        assert TOOL_ACCESS_EXPLORER in MCP_CATALOG_DISCOVERY_VS_ACCESS_DOC
        assert "What tables/schemas/columns can I see/view/access" in (
            MCP_CATALOG_DISCOVERY_VS_ACCESS_DOC
        )
        assert "named principal" in MCP_CATALOG_DISCOVERY_VS_ACCESS_DOC
        assert MCP_CATALOG_DISCOVERY_VS_ACCESS_DOC in MCP_ACCESS_DISAMBIGUATION_SEARCH_GUARD_DOC
        assert MCP_CATALOG_DISCOVERY_VS_ACCESS_DOC in MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC
        assert MCP_CATALOG_DISCOVERY_VS_ACCESS_DOC in MCP_ACCESS_DISAMBIGUATION_RULE_DOC
        assert TOOL_CREATE_SERVICE_REQUEST in MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC
        lowered = MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC.lower()
        assert "first-person request for access" in lowered


class TestValidateAccessIntentConfirmed:
    def test_object_to_users_requires_native_intent(self) -> None:
        err = validate_access_intent_confirmed(
            None,
            query_direction="object_to_users",
            expected_intent=MCP_ACCESS_INTENT_NATIVE,
        )
        assert err is not None
        assert err["error_code"] == "ACCESS_INTENT_REQUIRED"

    def test_object_to_users_passes_with_native_intent(self) -> None:
        assert (
            validate_access_intent_confirmed(
                "native",
                query_direction="object_to_users",
                expected_intent=MCP_ACCESS_INTENT_NATIVE,
            )
            is None
        )

    def test_object_to_principals_requires_catalog_acl_intent(self) -> None:
        err = validate_access_intent_confirmed(
            None,
            query_direction="object_to_principals",
            expected_intent=MCP_ACCESS_INTENT_CATALOG_ACL,
        )
        assert err is not None
        assert err["error_code"] == "ACCESS_INTENT_REQUIRED"

    def test_browse_is_not_gated(self) -> None:
        assert (
            validate_access_intent_confirmed(
                None,
                query_direction="browse",
                expected_intent=MCP_ACCESS_INTENT_NATIVE,
            )
            is None
        )
