"""Unit tests for JSON → LLMTestCase loading (no API key)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("deepeval", reason="Install eval extras: poetry install --with eval")

from evals.json_cases import load_mcp_use_cases_from_json

_EXAMPLES = Path(__file__).resolve().parent / "examples" / "mcp_use_cases.example.json"


def test_load_example_mcp_use_json() -> None:
    cases = load_mcp_use_cases_from_json(_EXAMPLES)
    assert len(cases) == 1
    assert cases[0].name == "example_catalog_search"
    assert "revenue" in (cases[0].input or "")
    assert cases[0].mcp_tools_called
    assert cases[0].mcp_tools_called[0].name == "search_catalog_assets"


def test_load_root_array(tmp_path: Path) -> None:
    p = tmp_path / "cases.json"
    p.write_text(
        '[{"input":"hi","actual_output":"ok","mcp_tools_called":[]}]',
        encoding="utf-8",
    )
    cases = load_mcp_use_cases_from_json(p)
    assert len(cases) == 1
    assert cases[0].name == "json_case_0"
