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
        assert _mcp_tools_called(c)[0].name == "search_catalog_assets"
    if "example_catalog_then_details" in by_name:
        c = by_name["example_catalog_then_details"]
        assert [x.name for x in _mcp_tools_called(c)] == [
            "search_catalog_assets",
            "catalog_asset_details",
        ]
    if "example_datastory_lookup" in by_name:
        c = by_name["example_datastory_lookup"]
        assert _mcp_tools_called(c)[0].name == "lookup_datastory"
    if "example_glossary_lookup" in by_name:
        c = by_name["example_glossary_lookup"]
        assert _mcp_tools_called(c)[0].args.get("term_name") == "PII"


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


def test_llm_only_skips_structural_validation_fixtures() -> None:
    """Intentional invalid-arg rows use llm_score=false so MCPUseMetric is not run on them."""
    all_cases = load_mcp_use_cases_from_json(_EXAMPLES)
    llm_cases = load_mcp_use_cases_from_json(_EXAMPLES, llm_only=True)
    assert len(llm_cases) < len(all_cases)
    skipped = {c.name for c in all_cases} - {c.name for c in llm_cases}
    assert "example_search_rejects_invalid_object_type" in skipped
    assert "example_lookup_tags_neither_id_nor_name" in skipped


def test_load_root_array(tmp_path: Path) -> None:
    p = tmp_path / "cases.json"
    p.write_text(
        '[{"input":"hi","actual_output":"ok","mcp_tools_called":[]}]',
        encoding="utf-8",
    )
    cases = load_mcp_use_cases_from_json(p)
    assert len(cases) == 1
    assert cases[0].name == "json_case_0"
