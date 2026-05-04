"""Unit tests for JSON → LLMTestCase loading (no API key)."""

from __future__ import annotations

from pathlib import Path

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


def test_load_root_array(tmp_path: Path) -> None:
    p = tmp_path / "cases.json"
    p.write_text(
        '[{"input":"hi","actual_output":"ok","mcp_tools_called":[]}]',
        encoding="utf-8",
    )
    cases = load_mcp_use_cases_from_json(p)
    assert len(cases) == 1
    assert cases[0].name == "json_case_0"
