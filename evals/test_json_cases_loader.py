"""Unit tests for JSON → LLMTestCase loading (no API key)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("deepeval", reason="Install eval extras: poetry install --with eval")

from deepeval.test_case import LLMTestCase, MCPToolCall

from evals.json_cases import load_mcp_use_cases_from_json
from evals.mcp_eval_helpers import ovaledge_eval_mcp_server

_EXAMPLES = Path(__file__).resolve().parent / "examples" / "mcp_use_cases.example.json"


def _mcp_tools_called(case: LLMTestCase) -> list[MCPToolCall]:
    tools = case.mcp_tools_called
    assert tools is not None
    return tools


def _tool_result_payload(tool: MCPToolCall) -> dict[str, Any]:
    """Best-effort structured content from an MCPToolCall result."""
    result = tool.result
    if result is None:
        return {}
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        # tool_call_result() wraps as {"result": <payload>}
        inner = structured.get("result")
        if isinstance(inner, dict):
            return inner
        return structured
    # DeepEval / MCP CallToolResult may nest content differently across versions.
    content = getattr(result, "content", None)
    if isinstance(content, list):
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str) and text.strip().startswith("{"):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    inner = parsed.get("result")
                    return inner if isinstance(inner, dict) else parsed
    if isinstance(result, dict):
        inner = result.get("result")
        return inner if isinstance(inner, dict) else result
    return {}


def _path_kind(result: dict[str, Any]) -> str:
    """Classify a tool result as happy vs adverse (error / empty / confirm gate / intent)."""
    if result.get("error") is not None or result.get("status_code") is not None:
        return "adverse"
    if result.get("error_code") is not None:
        return "adverse"
    if result.get("doNotUpdate") or result.get("doNotCreate") or result.get("doNotCreateTag"):
        return "adverse"
    phase = str(result.get("workflowPhase") or "")
    if phase.startswith("confirm_"):
        return "adverse"
    if result.get("total") == 0:
        return "adverse"
    data = result.get("data")
    if isinstance(data, dict):
        fb = data.get("fallback")
        if isinstance(fb, dict) and fb.get("show") is True:
            return "adverse"
    return "happy"


def test_load_example_mcp_use_json() -> None:
    """Structural checks only — add or reorder rows in ``mcp_use_cases.example.json`` freely."""
    cases = load_mcp_use_cases_from_json(_EXAMPLES)
    assert cases, "example file should load at least one case"

    srv_tools = ovaledge_eval_mcp_server().available_tools
    assert srv_tools is not None
    allowed_tools = {t.name for t in srv_tools}
    for case in cases:
        assert (case.input or "").strip()
        assert (case.actual_output or "").strip()
        tools = _mcp_tools_called(case)
        assert tools, "each case should declare at least one tool call"
        for t in tools:
            assert t.name in allowed_tools, (
                f"unknown tool {t.name!r}; fix JSON or extend ovaledge_eval_mcp_server()"
            )

    by_name = {c.name: c for c in cases if c.name}
    if "example_catalog_search" in by_name:
        c = by_name["example_catalog_search"]
        assert "revenue" in (c.input or "")
        assert _mcp_tools_called(c)[0].name == "asset_explorer"
    if "example_catalog_then_details" in by_name:
        c = by_name["example_catalog_then_details"]
        assert [x.name for x in _mcp_tools_called(c)] == [
            "asset_explorer",
            "asset_details",
        ]
    if "example_datastory_lookup" in by_name:
        c = by_name["example_datastory_lookup"]
        assert _mcp_tools_called(c)[0].name == "knowledge_search"
    if "example_glossary_lookup" in by_name:
        c = by_name["example_glossary_lookup"]
        assert _mcp_tools_called(c)[0].args.get("name") == "PII"


def test_example_json_covers_all_mcp_tools() -> None:
    from server.mcp_surface import MCP_TOOL_NAMES

    cases = load_mcp_use_cases_from_json(_EXAMPLES)
    covered: set[str] = set()
    for case in cases:
        for tool in _mcp_tools_called(case):
            covered.add(tool.name)
    missing = MCP_TOOL_NAMES - covered
    assert not missing, f"example JSON missing tools: {sorted(missing)}"


def test_example_json_has_happy_and_adverse_path_per_tool() -> None:
    """Every MCP tool must appear in ≥1 happy and ≥1 adverse (error/empty/confirm/intent) case."""
    from server.mcp_surface import MCP_TOOL_NAMES

    cases = load_mcp_use_cases_from_json(_EXAMPLES)
    happy: set[str] = set()
    adverse: set[str] = set()
    for case in cases:
        for tool in _mcp_tools_called(case):
            kind = _path_kind(_tool_result_payload(tool))
            if kind == "happy":
                happy.add(tool.name)
            else:
                adverse.add(tool.name)

    missing_happy = sorted(MCP_TOOL_NAMES - happy)
    missing_adverse = sorted(MCP_TOOL_NAMES - adverse)
    assert not missing_happy, (
        "example JSON missing happy-path coverage for: "
        f"{missing_happy}. Add a success result (no error/confirm-block)."
    )
    assert not missing_adverse, (
        "example JSON missing adverse-path coverage for: "
        f"{missing_adverse}. Add error, empty, confirm preview, or ACCESS_INTENT result."
    )


def test_example_json_catalog_nested_filters() -> None:
    """POST asset_explorer nested filters: views, dqIndex, at-least/more-than/max rating."""
    cases = load_mcp_use_cases_from_json(_EXAMPLES)
    by_name = {c.name: c for c in cases if c.name}

    search = by_name["example_catalog_search"]
    assert _mcp_tools_called(search)[0].args.get("filters", {}).get("certification") == [
        "certified"
    ]

    views = by_name["example_catalog_filters_certified_views"]
    view_args = _mcp_tools_called(views)[0].args
    assert "search_terms" not in view_args
    view_filters = view_args.get("filters")
    assert isinstance(view_filters, dict)
    assert view_filters.get("tableType") == ["VIEW"]
    assert view_filters.get("certification") == ["certified"]

    dq_case = by_name["example_catalog_dq_index_range"]
    dq = _mcp_tools_called(dq_case)[0].args.get("filters", {}).get("dqIndex")
    assert isinstance(dq, dict)
    assert dq.get("min") == 80
    assert "max" not in dq

    rating_case = by_name["example_catalog_rating_min_filter"]
    rating_args = _mcp_tools_called(rating_case)[0].args
    assert rating_args.get("object_type") == "oetable"
    rating = rating_args.get("filters", {}).get("rating")
    assert isinstance(rating, dict)
    assert rating.get("min") == 4
    assert "max" not in rating

    more_than = by_name["example_catalog_rating_more_than_filter"]
    more_than_rating = _mcp_tools_called(more_than)[0].args.get("filters", {}).get("rating")
    assert isinstance(more_than_rating, dict)
    assert more_than_rating.get("min") == 4.01
    assert "max" not in more_than_rating

    max_case = by_name["example_catalog_rating_max_filter"]
    max_rating = _mcp_tools_called(max_case)[0].args.get("filters", {}).get("rating")
    assert isinstance(max_rating, dict)
    assert max_rating.get("max") == 3
    assert "min" not in max_rating

    popularity = _mcp_tools_called(by_name["example_catalog_popularity_min_filter"])[0].args.get(
        "filters", {}
    ).get("popularity")
    assert isinstance(popularity, dict)
    assert popularity.get("min") == 70
    assert "max" not in popularity

    created = _mcp_tools_called(by_name["example_catalog_created_date_filter"])[0].args.get(
        "filters", {}
    ).get("createdDate")
    assert isinstance(created, dict)
    assert created.get("from") == "2024-01-01"
    assert created.get("to") == "2024-12-31"
    assert "min" not in created
    assert "max" not in created

    null_density = _mcp_tools_called(by_name["example_catalog_null_density_eq"])[0].args.get(
        "filters", {}
    ).get("nullDensity")
    assert isinstance(null_density, dict)
    assert null_density.get("eq") == 6.7
    assert "min" not in null_density
    assert "max" not in null_density

    sort_case = _mcp_tools_called(by_name["example_catalog_sort_popularity_desc"])[0]
    assert sort_case.args.get("object_type") == "glossary"
    sort = sort_case.args.get("sort")
    assert isinstance(sort, dict)
    assert sort.get("field") == "popularity"
    assert sort.get("direction") == "desc"
    assert "search_terms" not in sort_case.args
    assert "context_query" not in sort_case.args

    empty = by_name["example_catalog_filters_no_match"]
    assert _tool_result_payload(_mcp_tools_called(empty)[0]).get("total") == 0


def test_llm_only_skips_structural_validation_fixtures() -> None:
    """Intentional invalid-arg rows use llm_score=false so MCPUseMetric is not run on them."""
    all_cases = load_mcp_use_cases_from_json(_EXAMPLES)
    llm_cases = load_mcp_use_cases_from_json(_EXAMPLES, llm_only=True)
    assert len(llm_cases) < len(all_cases)
    skipped = {c.name for c in all_cases} - {c.name for c in llm_cases}
    assert "example_search_rejects_invalid_object_type" in skipped
    assert "example_asset_explorer_neither_id_nor_name" in skipped


def test_load_root_array(tmp_path: Path) -> None:
    p = tmp_path / "cases.json"
    p.write_text(
        '[{"input":"hi","actual_output":"ok","mcp_tools_called":[]}]',
        encoding="utf-8",
    )
    cases = load_mcp_use_cases_from_json(p)
    assert len(cases) == 1
    assert cases[0].name == "json_case_0"
