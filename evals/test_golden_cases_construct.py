"""Validate golden case objects build without LLM calls."""

from __future__ import annotations

pytest_import = __import__("pytest")
pytest = pytest_import

pytest.importorskip("deepeval", reason="Install eval extras: poetry install --with eval")


def test_all_golden_cases_construct() -> None:
    import evals.golden_cases as golden_cases

    for fn_name in golden_cases.all_mcp_use_golden_fns():
        case = getattr(golden_cases, fn_name)()
        assert (case.input or "").strip()
        assert case.mcp_tools_called

    tc = golden_cases.golden_task_completion_discovery()
    assert tc.turns
    mt = golden_cases.golden_multi_turn_lineage_followup()
    assert mt.turns
