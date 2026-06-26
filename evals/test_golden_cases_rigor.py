"""Structural rigor checks on eval goldens (no LLM calls)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pytest

pytest.importorskip("deepeval", reason="Install eval extras: poetry install --with eval")

from deepeval.test_case import MCPToolCall, Turn  # noqa: E402
from mcp.types import CallToolResult  # noqa: E402

from evals.golden_cases import (  # noqa: E402
    _GOVERNED_WRITE_CONFIRMATION_TOKEN,
    _GOVERNED_WRITE_POST_BODY,
    golden_governed_write_confirm_two_step,
)
from server.constants import TOOL_UPDATE_ASSET_DESCRIPTIONS
from server.tools.common.confirm_gate import compute_confirmation_token


def _tool_calls_from_turns(turns: Sequence[Turn]) -> list[MCPToolCall]:
    calls: list[MCPToolCall] = []
    for turn in turns:
        calls.extend(turn.mcp_tools_called or [])
    return calls


def _structured_result(tool_call: MCPToolCall) -> dict[str, Any]:
    result = cast(CallToolResult, tool_call.result)
    structured = result.structuredContent
    assert isinstance(structured, dict)
    inner = structured.get("result")
    assert isinstance(inner, dict)
    return inner


def test_governed_write_golden_preview_and_confirm_share_token() -> None:
    case = golden_governed_write_confirm_two_step()
    update_calls = [
        c
        for c in _tool_calls_from_turns(case.turns)
        if c.name == TOOL_UPDATE_ASSET_DESCRIPTIONS
    ]
    assert len(update_calls) == 2
    preview_call, confirm_call = update_calls
    assert preview_call.args.get("write_confirmed_by_user") is False
    assert confirm_call.args.get("write_confirmed_by_user") is True
    preview_token = _structured_result(preview_call)["confirmationToken"]
    assert preview_token == _GOVERNED_WRITE_CONFIRMATION_TOKEN
    assert confirm_call.args.get("confirmation_token") == preview_token
    assert preview_call.args.get("description_text") == confirm_call.args.get(
        "description_text"
    )


def test_governed_write_golden_token_matches_post_body_digest() -> None:
    assert _GOVERNED_WRITE_CONFIRMATION_TOKEN == compute_confirmation_token(
        _GOVERNED_WRITE_POST_BODY
    )


def test_governed_write_golden_preview_blocks_post_semantics() -> None:
    case = golden_governed_write_confirm_two_step()
    preview_turn = next(
        t
        for t in case.turns
        if any(
            c.name == TOOL_UPDATE_ASSET_DESCRIPTIONS
            and c.args.get("write_confirmed_by_user") is False
            for c in (t.mcp_tools_called or [])
        )
    )
    preview_call = next(
        c
        for c in (preview_turn.mcp_tools_called or [])
        if c.name == TOOL_UPDATE_ASSET_DESCRIPTIONS
    )
    payload = _structured_result(preview_call)
    assert payload["workflowPhase"] == "confirm_update"
    assert payload["doNotUpdate"] is True
