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
    golden_mcp_use_asset_details_after_shortlist,
    golden_mcp_use_knowledge_not_catalog_for_policy,
    golden_mcp_use_open_catalog_search,
    golden_multi_turn_explore_details_lineage,
)
from server.constants import (  # noqa: E402
    TOOL_ASSET_DETAILS,
    TOOL_ASSET_EXPLORER,
    TOOL_ASSET_LINEAGE,
    TOOL_KNOWLEDGE_SEARCH,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
)
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


def _hit_ids(tool_call: MCPToolCall) -> set[int]:
    payload = _structured_result(tool_call)
    hits = payload.get("items") or payload.get("results") or []
    return {h["objectId"] for h in hits if isinstance(h, dict) and "objectId" in h}


def test_open_catalog_search_golden_omits_object_type() -> None:
    """The golden that teaches open discovery must not itself narrow the search."""
    case = golden_mcp_use_open_catalog_search()
    calls = case.mcp_tools_called or []
    explorer = [c for c in calls if c.name == TOOL_ASSET_EXPLORER]
    assert len(explorer) == 1
    args = explorer[0].args
    assert "object_type" not in args, "open-discovery golden must leave object_type unset"
    assert args.get("context_query"), "open discovery relies on context_query for ranking"
    # The point of omitting object_type is that mixed types come back.
    types = {
        h.get("objectType")
        for h in _structured_result(explorer[0])["items"]
        if isinstance(h, dict)
    }
    assert len(types) > 1, f"expected hits across multiple object types, got {types}"


def test_details_golden_only_uses_an_id_the_search_returned() -> None:
    """asset_details must be called with a shortlisted id, not an invented one."""
    case = golden_mcp_use_asset_details_after_shortlist()
    calls = case.mcp_tools_called or []
    names = [c.name for c in calls]
    assert names.index(TOOL_ASSET_EXPLORER) < names.index(TOOL_ASSET_DETAILS), (
        "asset_explorer must be called before asset_details"
    )
    explorer = next(c for c in calls if c.name == TOOL_ASSET_EXPLORER)
    details = next(c for c in calls if c.name == TOOL_ASSET_DETAILS)
    assert details.args["object_id"] in _hit_ids(explorer)
    assert details.args["object_type"]


def test_policy_golden_does_not_call_catalog_search() -> None:
    """Routing negative: a policy question must not reach asset_explorer."""
    case = golden_mcp_use_knowledge_not_catalog_for_policy()
    names = {c.name for c in (case.mcp_tools_called or [])}
    assert names == {TOOL_KNOWLEDGE_SEARCH}, (
        f"policy question should use knowledge_search alone, got {sorted(names)}"
    )


def test_multi_turn_read_chain_order_and_id_consistency() -> None:
    """explore → details → lineage, each step reusing the id the previous step produced."""
    case = golden_multi_turn_explore_details_lineage()
    calls = _tool_calls_from_turns(case.turns)
    assert [c.name for c in calls] == [
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
        TOOL_ASSET_LINEAGE,
    ]
    explorer, details, lineage = calls
    assert "object_type" not in explorer.args, "chain should start with an open search"
    object_id = details.args["object_id"]
    assert object_id in _hit_ids(explorer)
    assert lineage.args["object_id"] == object_id
    assert lineage.args["object_type"] in ("oetable", "oefile")


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
