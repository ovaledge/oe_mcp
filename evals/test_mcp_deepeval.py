"""Pytest + DeepEval `assert_test` over golden MCP cases.

Requires `poetry install --with eval`. Default repo `pytest` only collects `tests/`; run this file
explicitly:

    poetry run pytest evals/test_mcp_deepeval.py -v

With API key, metrics run as LLM-as-judge; without key, tests are skipped.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from evals.config import (
    deepeval_threshold,
    ensure_deepeval_telemetry_opt_out,
    has_openai_key,
    judge_model,
)

ensure_deepeval_telemetry_opt_out()

pytest.importorskip("deepeval", reason="Install eval extras: poetry install --with eval")

from deepeval.evaluate import assert_test  # noqa: E402
from deepeval.metrics.base_metric import BaseConversationalMetric, BaseMetric  # noqa: E402
from deepeval.test_case import ConversationalTestCase, LLMTestCase  # noqa: E402

from evals.golden_cases import (  # noqa: E402
    all_mcp_use_golden_fns,
    all_multi_turn_mcp_use_golden_fns,
)


@pytest.fixture
def _skip_without_openai_key() -> None:
    if not has_openai_key():
        pytest.skip("Set OPENAI_API_KEY or DEEPEVAL_OPENAI_API_KEY for DeepEval MCP metrics")


@pytest.mark.parametrize(
    "golden_fn",
    [
        pytest.param(name, id=name.removeprefix("golden_"))
        for name in all_mcp_use_golden_fns()
    ],
)
def test_mcp_use_metric(
    golden_fn: str,
    _skip_without_openai_key: None,
) -> None:
    from deepeval.metrics import MCPUseMetric

    from evals import golden_cases

    fn: Callable[[], LLMTestCase] = getattr(golden_cases, golden_fn)
    case = fn()
    metric: BaseMetric = MCPUseMetric(
        threshold=deepeval_threshold(),
        model=judge_model(),
        verbose_mode=False,
    )
    assert_test(case, [metric], run_async=True)


@pytest.mark.parametrize(
    "golden_fn",
    [
        pytest.param("golden_task_completion_discovery", id="task_completion_discovery"),
    ],
)
def test_mcp_task_completion_metric(
    golden_fn: str,
    _skip_without_openai_key: None,
) -> None:
    from deepeval.metrics import MCPTaskCompletionMetric

    from evals import golden_cases

    fn: Callable[[], ConversationalTestCase] = getattr(golden_cases, golden_fn)
    case = fn()
    metric: BaseConversationalMetric = MCPTaskCompletionMetric(
        threshold=deepeval_threshold(),
        model=judge_model(),
        verbose_mode=False,
    )
    assert_test(case, [metric], run_async=True)


@pytest.mark.parametrize(
    "golden_fn",
    [
        pytest.param(name, id=name.removeprefix("golden_"))
        for name in all_multi_turn_mcp_use_golden_fns()
    ],
)
def test_multi_turn_mcp_use_metric(
    golden_fn: str,
    _skip_without_openai_key: None,
) -> None:
    from deepeval.metrics import MultiTurnMCPUseMetric

    from evals import golden_cases

    fn: Callable[[], ConversationalTestCase] = getattr(golden_cases, golden_fn)
    case = fn()
    metric: BaseConversationalMetric = MultiTurnMCPUseMetric(
        threshold=deepeval_threshold(),
        model=judge_model(),
        verbose_mode=False,
    )
    assert_test(case, [metric], run_async=True)


def test_mcp_use_metric_from_user_json_file(
    _skip_without_openai_key: None,
) -> None:
    """Set ``DEEPEVAL_MCP_USE_CASES_JSON`` to your cases file (see ``evals/examples/``)."""
    path_str = os.environ.get("DEEPEVAL_MCP_USE_CASES_JSON", "").strip()
    if not path_str:
        pytest.skip("Set DEEPEVAL_MCP_USE_CASES_JSON to run MCPUseMetric on your JSON cases")
    from deepeval.metrics import MCPUseMetric

    from evals.json_cases import load_mcp_use_cases_from_json

    path = Path(path_str)
    for case in load_mcp_use_cases_from_json(path):
        metric: BaseMetric = MCPUseMetric(
            threshold=deepeval_threshold(),
            model=judge_model(),
            verbose_mode=False,
        )
        assert_test(case, [metric], run_async=True)
