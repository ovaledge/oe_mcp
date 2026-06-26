"""Ensure every registered MCP tool appears in at least one eval golden."""

from __future__ import annotations

import pytest

pytest.importorskip("deepeval", reason="Install eval extras: poetry install --with eval")

from deepeval.test_case import ConversationalTestCase, LLMTestCase

import evals.golden_cases as golden_cases
from server.mcp_surface import MCP_TOOL_NAMES


def _tool_names_from_case(case: LLMTestCase | ConversationalTestCase) -> set[str]:
    names: set[str] = set()
    for call in getattr(case, "mcp_tools_called", None) or []:
        names.add(call.name)
    for turn in getattr(case, "turns", None) or []:
        for call in turn.mcp_tools_called or []:
            names.add(call.name)
    return names


def _tools_covered_by_all_goldens() -> set[str]:
    covered: set[str] = set()
    for fn_name in (
        golden_cases.all_mcp_use_golden_fns()
        + golden_cases.all_conversational_golden_fns()
    ):
        case = getattr(golden_cases, fn_name)()
        covered |= _tool_names_from_case(case)
    return covered


def test_every_mcp_tool_has_eval_golden() -> None:
    covered = _tools_covered_by_all_goldens()
    missing = MCP_TOOL_NAMES - covered
    assert not missing, (
        "MCP tools missing from eval goldens: "
        f"{sorted(missing)}. Add a golden in evals/golden_cases*.py."
    )


def test_eval_golden_registry_matches_callable_functions() -> None:
    for fn_name in (
        golden_cases.all_mcp_use_golden_fns()
        + golden_cases.all_conversational_golden_fns()
    ):
        fn = getattr(golden_cases, fn_name)
        case = fn()
        assert case.name


def test_multi_turn_registry_excludes_task_completion() -> None:
    conversational = golden_cases.all_conversational_golden_fns()
    multi_turn = golden_cases.all_multi_turn_mcp_use_golden_fns()
    assert "golden_task_completion_discovery" in conversational
    assert "golden_task_completion_discovery" not in multi_turn
    assert len(multi_turn) == len(conversational) - 1
