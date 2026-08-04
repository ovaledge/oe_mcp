"""End-to-end confirmation_token binding on governed write tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from server.constants import (
    TOOL_ASSOCIATE_DQ_RULE_OBJECTS,
    TOOL_CREATE_DQ_RULES,
    TOOL_CREATE_GLOSSARY_TERM,
    TOOL_CREATE_SQL_DQ_RULE,
    TOOL_CREATE_TAG,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
    TOOL_UPDATE_CDE_ASSOCIATIONS,
    TOOL_UPDATE_CUSTOM_FIELD_VALUE,
    TOOL_UPDATE_GOVERNANCE_ROLES,
    TOOL_VALIDATE_DQ_QUERIES,
)
from server.tools import catalog, dataquality, governance
from server.tools.common.confirm_gate import compute_confirmation_token
from tests.helpers import get_tool_fn


@dataclass(frozen=True)
class StaleTokenCase:
    tool_name: str
    register: Callable[[FastMCP], None]
    preview_kwargs: dict[str, Any]
    tamper_kwargs: dict[str, Any] = field(default_factory=dict)
    setup: Callable[[AsyncMock], Awaitable[None]] | None = None


async def _open_tag_preview_setup(mock_oe_client: AsyncMock) -> None:
    open_opts = {
        "ok": True,
        "data": {
            "tagSecurityMode": "open",
            "parentTagChoices": [{"parentTagId": 1, "tagName": "Root"}],
        },
    }

    async def _get(_path: str, **_kwargs: object) -> dict[str, object]:
        return open_opts

    mock_oe_client.get.side_effect = _get


STALE_TOKEN_CASES: tuple[StaleTokenCase, ...] = (
    StaleTokenCase(
        tool_name=TOOL_UPDATE_ASSET_DESCRIPTIONS,
        register=catalog.register,
        preview_kwargs={
            "object_id": 42,
            "object_type": "oetable",
            "description_field": "business_description",
            "description_text": "Original business text",
        },
        tamper_kwargs={"description_text": "Tampered business text"},
    ),
    StaleTokenCase(
        tool_name=TOOL_UPDATE_CDE_ASSOCIATIONS,
        register=catalog.register,
        preview_kwargs={
            "targets": [{"object_id": 3337, "object_type": "oeschema"}],
            "action": "Yes",
            "cde_justification": "Original justification",
        },
        tamper_kwargs={"action": "No"},
    ),
    StaleTokenCase(
        tool_name=TOOL_CREATE_GLOSSARY_TERM,
        register=governance.register,
        preview_kwargs={
            "term_name": "Revenue",
            "domain_id": 12,
            "description": "Original definition",
            "skip_category": True,
            "category_skip_confirmed": True,
        },
        tamper_kwargs={"description": "Tampered definition"},
    ),
    StaleTokenCase(
        tool_name=TOOL_UPDATE_GOVERNANCE_ROLES,
        register=governance.register,
        preview_kwargs={
            "object_id": 99,
            "object_type": "oetable",
            "role_updates": {"owner": "mike"},
        },
        tamper_kwargs={"role_updates": {"owner": "alice"}},
    ),
    StaleTokenCase(
        tool_name=TOOL_UPDATE_CUSTOM_FIELD_VALUE,
        register=governance.register,
        preview_kwargs={
            "object_id": 99,
            "object_type": "oetable",
            "field_updates": [{"field_name": "Data Owner", "value": "John Smith"}],
        },
        tamper_kwargs={
            "field_updates": [{"field_name": "Data Owner", "value": "Jane Doe"}],
        },
    ),
    StaleTokenCase(
        tool_name=TOOL_ASSOCIATE_DQ_RULE_OBJECTS,
        register=dataquality.register,
        preview_kwargs={
            "dqrule_id": 42,
            "objects": [{"objectId": 10, "objectType": "oecolumn"}],
        },
        tamper_kwargs={"dqrule_id": 99},
    ),
    StaleTokenCase(
        tool_name=TOOL_CREATE_DQ_RULES,
        register=dataquality.register,
        preview_kwargs={"discover_cde_columns": True},
        tamper_kwargs={"prefer_existing_rule": False},
    ),
    StaleTokenCase(
        tool_name=TOOL_VALIDATE_DQ_QUERIES,
        register=dataquality.register,
        preview_kwargs={
            "connection_id": 1,
            "schema_id": 2,
            "rule_query": "SELECT 1",
            "stats_query": "SELECT 2",
            "failed_values_query": "SELECT 3",
        },
        tamper_kwargs={"rule_query": "SELECT 9"},
    ),
    StaleTokenCase(
        tool_name=TOOL_CREATE_SQL_DQ_RULE,
        register=dataquality.register,
        preview_kwargs={
            "objects": [{"objectId": 101, "objectType": "oecolumn"}],
            "rule_name": "mcp_rule",
            "rule_query": "SELECT 1",
            "stats_query": "SELECT 2",
            "failed_values_query": "SELECT 3",
        },
        tamper_kwargs={"rule_name": "tampered"},
    ),
)


class TestGovernedWriteStaleConfirmationToken:
    @pytest.mark.parametrize(
        "case",
        STALE_TOKEN_CASES,
        ids=[c.tool_name for c in STALE_TOKEN_CASES],
    )
    async def test_rejects_stale_token_when_payload_changes(
        self, mock_oe_client: AsyncMock, case: StaleTokenCase
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        case.register(mcp)
        fn = await get_tool_fn(mcp, case.tool_name)

        if case.setup is not None:
            await case.setup(mock_oe_client)
            if case.tool_name == TOOL_CREATE_TAG:
                await fn(tag_name="Logistics")

        preview = await fn(**case.preview_kwargs)
        assert preview.get("confirmationToken"), (
            f"{case.tool_name} preview missing confirmationToken"
        )
        assert preview.get("workflowPhase", "").startswith("confirm_")
        mock_oe_client.post.reset_mock()

        confirm_kwargs = {**case.preview_kwargs, **case.tamper_kwargs}
        out = await fn(
            **confirm_kwargs,
            write_confirmed_by_user=True,
            confirmation_token=preview["confirmationToken"],
        )
        assert out.get("error_code") == "confirmation_token_mismatch"
        assert out.get("status_code") == 400
        assert out.get("expectedConfirmationToken")
        mock_oe_client.post.assert_not_called()

    @pytest.mark.parametrize(
        "case",
        STALE_TOKEN_CASES,
        ids=[c.tool_name for c in STALE_TOKEN_CASES],
    )
    async def test_rejects_missing_token_when_confirmed(
        self, mock_oe_client: AsyncMock, case: StaleTokenCase
    ) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        case.register(mcp)
        fn = await get_tool_fn(mcp, case.tool_name)

        if case.setup is not None:
            await case.setup(mock_oe_client)
            if case.tool_name == TOOL_CREATE_TAG:
                await fn(tag_name="Logistics")

        await fn(**case.preview_kwargs)
        mock_oe_client.post.reset_mock()
        out = await fn(
            **case.preview_kwargs,
            write_confirmed_by_user=True,
            confirmation_token=None,
        )
        assert out.get("error_code") == "confirmation_token_mismatch"
        mock_oe_client.post.assert_not_called()


class TestCreateTagStaleConfirmationToken:
    async def test_rejects_stale_token_at_confirm(self, mock_oe_client: AsyncMock) -> None:
        await _open_tag_preview_setup(mock_oe_client)
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_TAG)
        await fn(tag_name="Logistics")
        preview = await fn(
            tag_name="Logistics",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        assert preview.get("confirmationToken")
        stale_token = compute_confirmation_token(
            {"tagName": "LogisticsTampered", "description": "<p>x</p>"}
        )
        out = await fn(
            tag_name="Logistics",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
            write_confirmed_by_user=True,
            confirmation_token=stale_token,
        )
        assert out.get("error_code") == "confirmation_token_mismatch"
        mock_oe_client.post.assert_not_called()

    async def test_rejects_missing_token_when_confirmed(self, mock_oe_client: AsyncMock) -> None:
        await _open_tag_preview_setup(mock_oe_client)
        mcp = FastMCP(name="test", version="0.0.1")
        governance.register(mcp)
        fn = await get_tool_fn(mcp, TOOL_CREATE_TAG)
        await fn(tag_name="Logistics")
        await fn(
            tag_name="Logistics",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
        )
        out = await fn(
            tag_name="Logistics",
            create_directly_under_master=True,
            parent_step_completed_by_user=True,
            write_confirmed_by_user=True,
            confirmation_token=None,
        )
        assert out.get("error_code") == "confirmation_token_mismatch"
        mock_oe_client.post.assert_not_called()
