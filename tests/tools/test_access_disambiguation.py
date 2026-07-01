"""Tests for who-has-access disambiguation gate."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastmcp import FastMCP

from server.constants import (
    MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE,
    MCP_ACCESS_INTENT_CATALOG_ACL,
    MCP_ACCESS_INTENT_NATIVE,
    TOOL_GET_USER_OBJECT_ACCESS,
    TOOL_SOURCE_SYSTEM_ACCESS,
)
from server.tools import access, rdam
from server.tools.access.disambiguation import (
    infer_access_intent_from_question,
    question_has_catalog_acl_access_signals,
    question_has_native_access_signals,
    validate_access_intent_confirmed,
)
from tests.helpers import get_tool_fn


class TestAccessIntentSignals:
    def test_native_signals_detected(self) -> None:
        assert question_has_native_access_signals("Who has native access to ORDERS?")
        assert not question_has_catalog_acl_access_signals("Who has native access to ORDERS?")
        assert infer_access_intent_from_question("Show DAM grants for BUSINESS.BANKING") == "native"

    def test_catalog_acl_signals_detected(self) -> None:
        assert question_has_catalog_acl_access_signals("Show OE security on ORDERS")
        assert question_has_catalog_acl_access_signals("Who has catalog ACL on BANKING?")
        assert not question_has_native_access_signals("Who has catalog ACL on BANKING?")
        assert infer_access_intent_from_question("catalog access for orders table") == "catalog_acl"

    def test_ambiguous_question_has_no_inferred_intent(self) -> None:
        assert infer_access_intent_from_question("Who has access to ORDERS in snowflake?") is None
        assert (
            infer_access_intent_from_question("native catalog acl on orders")
            is None
        )


class TestValidateAccessIntentConfirmed:
    def test_object_to_users_requires_native(self) -> None:
        err = validate_access_intent_confirmed(
            None,
            query_direction="object_to_users",
            expected_intent=MCP_ACCESS_INTENT_NATIVE,
        )
        assert err is not None
        assert err["error_code"] == "ACCESS_INTENT_REQUIRED"
        assert err["advisoryMessage"] == MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE

    def test_object_to_users_accepts_native_signals_in_user_question(self) -> None:
        assert (
            validate_access_intent_confirmed(
                None,
                query_direction="object_to_users",
                expected_intent=MCP_ACCESS_INTENT_NATIVE,
                user_question="Who has native access to BUSINESS.BANKING?",
            )
            is None
        )

    def test_object_to_principals_accepts_catalog_acl_signals_in_user_question(self) -> None:
        assert (
            validate_access_intent_confirmed(
                None,
                query_direction="object_to_principals",
                expected_intent=MCP_ACCESS_INTENT_CATALOG_ACL,
                user_question="Show OE security permissions on orders table",
            )
            is None
        )

    def test_object_to_users_accepts_native(self) -> None:
        assert (
            validate_access_intent_confirmed(
                "native",
                query_direction="object_to_users",
                expected_intent=MCP_ACCESS_INTENT_NATIVE,
            )
            is None
        )

    def test_user_to_objects_not_gated(self) -> None:
        assert (
            validate_access_intent_confirmed(
                None,
                query_direction="user_to_objects",
                expected_intent=MCP_ACCESS_INTENT_NATIVE,
            )
            is None
        )

    def test_object_to_principals_requires_catalog_acl(self) -> None:
        err = validate_access_intent_confirmed(
            None,
            query_direction="object_to_principals",
            expected_intent=MCP_ACCESS_INTENT_CATALOG_ACL,
        )
        assert err is not None
        assert err["error_code"] == "ACCESS_INTENT_REQUIRED"


class TestAccessToolsDisambiguationGate:
    async def test_source_system_access_blocks_object_to_users_without_intent(
        self,
    ) -> None:
        mcp = FastMCP("test")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_SOURCE_SYSTEM_ACCESS)
        result = await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            object_path="BUSINESS.BANKING",
            object_type="schema",
        )
        assert result["error_code"] == "ACCESS_INTENT_REQUIRED"
        assert "formattedResponse" in result

    async def test_source_system_access_allows_object_to_users_with_native_intent(
        self,
        mock_oe_client: AsyncMock,
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP("test")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_SOURCE_SYSTEM_ACCESS)
        result = await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            object_path="BUSINESS.BANKING",
            object_type="schema",
            access_intent_confirmed="native",
        )
        assert "error_code" not in result
        mock_oe_client.get.assert_awaited_once()

    async def test_get_user_object_access_allows_catalog_acl_signals_in_user_question(
        self,
        mock_oe_client: AsyncMock,
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"principals": []}}
        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_GET_USER_OBJECT_ACCESS)
        result = await fn(
            query_direction="object_to_principals",
            object_id=1,
            object_type="oeschema",
            user_question="Who has catalog ACL access on BUSINESS.BANKING?",
        )
        assert "error_code" not in result
        mock_oe_client.get.assert_awaited_once()

    async def test_source_system_access_allows_native_signals_in_user_question(
        self,
        mock_oe_client: AsyncMock,
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"grants": []}}
        mcp = FastMCP("test")
        rdam.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_SOURCE_SYSTEM_ACCESS)
        result = await fn(
            source_system="snowflake",
            query_direction="object_to_users",
            object_path="BUSINESS.BANKING",
            object_type="schema",
            user_question="Show DAM grants for BUSINESS.BANKING",
        )
        assert "error_code" not in result
        mock_oe_client.get.assert_awaited_once()

    async def test_get_user_object_access_blocks_object_to_principals_without_intent(
        self,
    ) -> None:
        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_GET_USER_OBJECT_ACCESS)
        result = await fn(
            query_direction="object_to_principals",
            object_id=1,
            object_type="oeschema",
        )
        assert result["error_code"] == "ACCESS_INTENT_REQUIRED"

    async def test_get_user_object_access_allows_object_to_principals_with_catalog_intent(
        self,
        mock_oe_client: AsyncMock,
    ) -> None:
        mock_oe_client.get.return_value = {"ok": True, "data": {"principals": []}}
        mcp = FastMCP("test")
        access.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_GET_USER_OBJECT_ACCESS)
        result = await fn(
            query_direction="object_to_principals",
            object_id=1,
            object_type="oeschema",
            access_intent_confirmed="catalog_acl",
        )
        assert "error_code" not in result
        mock_oe_client.get.assert_awaited_once()
