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
    golden_mcp_use_catalog_created_date_filter,
    golden_mcp_use_catalog_dq_range_filter,
    golden_mcp_use_catalog_filters_only,
    golden_mcp_use_catalog_popularity_min_filter,
    golden_mcp_use_catalog_rating_min_filter,
    golden_mcp_use_catalog_rating_more_than_filter,
    golden_mcp_use_catalog_search,
    golden_mcp_use_knowledge_not_catalog_for_policy,
    golden_mcp_use_open_catalog_search,
    golden_multi_turn_explore_details_lineage,
)
from evals.golden_cases_coverage import (  # noqa: E402
    golden_governed_service_request_create_two_step,
    golden_mcp_use_request_access_not_access_explorer,
)
from server.constants import (  # noqa: E402
    TOOL_ACCESS_EXPLORER,
    TOOL_ASSET_DETAILS,
    TOOL_ASSET_EXPLORER,
    TOOL_ASSET_LINEAGE,
    TOOL_CREATE_SERVICE_REQUEST,
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


def test_catalog_search_golden_passes_nested_certification_filter() -> None:
    """Certified-tables prompt must put certification on nested filters, not search_terms."""
    case = golden_mcp_use_catalog_search()
    explorer = next(c for c in (case.mcp_tools_called or []) if c.name == TOOL_ASSET_EXPLORER)
    args = explorer.args
    filters = args.get("filters")
    assert isinstance(filters, dict)
    assert filters.get("certification") == ["certified"]
    assert args.get("search_terms") == ["customer", "revenue"]
    assert args.get("object_type") == "oetable"


def test_catalog_filters_only_golden_omits_search_terms_and_glossary() -> None:
    """Facet-only discovery is POST nested filters, not keyword or glossary lookup."""
    case = golden_mcp_use_catalog_filters_only()
    explorer = next(c for c in (case.mcp_tools_called or []) if c.name == TOOL_ASSET_EXPLORER)
    args = explorer.args
    assert "search_terms" not in args
    assert "name" not in args
    assert "glossary_placement" not in args
    filters = args.get("filters")
    assert isinstance(filters, dict)
    assert filters.get("certification") == ["certified"]
    assert filters.get("tableType") == ["VIEW"]
    assert args.get("object_type") == "oetable"


def test_catalog_dq_range_filter_golden_uses_nested_range() -> None:
    """DQ score + parent table belong on nested filters, not flattened FastMCP fields."""
    case = golden_mcp_use_catalog_dq_range_filter()
    explorer = next(c for c in (case.mcp_tools_called or []) if c.name == TOOL_ASSET_EXPLORER)
    args = explorer.args
    assert "object_type" not in args
    filters = args.get("filters")
    assert isinstance(filters, dict)
    assert filters.get("tableName") == ["CUSTOMER"]
    dq = filters.get("dqIndex")
    assert isinstance(dq, dict)
    assert dq.get("min") == 80
    assert "max" not in dq


def test_catalog_rating_min_filter_golden_omits_invented_max() -> None:
    """Star rating lower bound only — do not invent rating max 5."""
    case = golden_mcp_use_catalog_rating_min_filter()
    explorer = next(c for c in (case.mcp_tools_called or []) if c.name == TOOL_ASSET_EXPLORER)
    args = explorer.args
    assert args.get("object_type") == "oetable"
    filters = args.get("filters")
    assert isinstance(filters, dict)
    rating = filters.get("rating")
    assert isinstance(rating, dict)
    assert rating.get("min") == 4
    assert "max" not in rating
    assert "more than" not in (case.input or "").lower()


def test_catalog_rating_more_than_filter_golden_uses_min_just_above() -> None:
    """'More than 4' is exclusive — inclusive min just above 4, no invented max."""
    case = golden_mcp_use_catalog_rating_more_than_filter()
    explorer = next(c for c in (case.mcp_tools_called or []) if c.name == TOOL_ASSET_EXPLORER)
    args = explorer.args
    assert args.get("object_type") == "oetable"
    filters = args.get("filters")
    assert isinstance(filters, dict)
    rating = filters.get("rating")
    assert isinstance(rating, dict)
    assert rating.get("min") == 4.01
    assert "max" not in rating
    assert rating.get("min") != 4


def test_catalog_popularity_min_filter_golden_omits_invented_max() -> None:
    """Popularity lower bound only — do not invent an upper bound."""
    case = golden_mcp_use_catalog_popularity_min_filter()
    explorer = next(c for c in (case.mcp_tools_called or []) if c.name == TOOL_ASSET_EXPLORER)
    args = explorer.args
    assert args.get("object_type") == "oetable"
    popularity = args.get("filters", {}).get("popularity")
    assert isinstance(popularity, dict)
    assert popularity.get("min") == 70
    assert "max" not in popularity


def test_catalog_created_date_filter_golden_uses_from_to() -> None:
    """createdDate uses from/to ISO dates, not min/max."""
    case = golden_mcp_use_catalog_created_date_filter()
    explorer = next(c for c in (case.mcp_tools_called or []) if c.name == TOOL_ASSET_EXPLORER)
    created = explorer.args.get("filters", {}).get("createdDate")
    assert isinstance(created, dict)
    assert created.get("from") == "2024-01-01"
    assert created.get("to") == "2024-12-31"
    assert "min" not in created
    assert "max" not in created


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


def test_service_request_golden_uses_real_tool_parameters() -> None:
    case = golden_governed_service_request_create_two_step()
    calls = [
        c
        for c in _tool_calls_from_turns(case.turns)
        if c.name == TOOL_CREATE_SERVICE_REQUEST
    ]
    assert len(calls) >= 2
    lookup_call = calls[0]
    assert lookup_call.args.get("request_type") == "access"
    assert "summary" not in lookup_call.args
    preview_call = next(
        c for c in calls if c.args.get("write_confirmed_by_user") is False and "summary" in c.args
    )
    confirm_call = next(c for c in calls if c.args.get("write_confirmed_by_user") is True)
    assert preview_call.args.get("ticket_template_id") == 1005
    assert preview_call.args.get("object_type") == "oetable"
    assert preview_call.args.get("write_confirmed_by_user") is False
    assert preview_call.args.get("confirmation_token") is None
    preview_token = _structured_result(preview_call)["confirmationToken"]
    assert confirm_call.args.get("confirmation_token") == preview_token
    assert confirm_call.args.get("ticket_template_id") == preview_call.args.get(
        "ticket_template_id"
    )


def test_request_access_golden_does_not_call_access_explorer() -> None:
    case = golden_mcp_use_request_access_not_access_explorer()
    names = [c.name for c in (case.mcp_tools_called or [])]
    assert TOOL_ACCESS_EXPLORER not in names
    assert TOOL_CREATE_SERVICE_REQUEST in names
    assert TOOL_ASSET_EXPLORER in names
