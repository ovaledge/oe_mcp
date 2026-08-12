#!/usr/bin/env python3
"""Run DeepEval MCP metrics against golden cases (requires `poetry install --with eval`)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evals.config import (
    deepeval_threshold,
    ensure_deepeval_telemetry_opt_out,
    has_openai_key,
    judge_model,
)

ensure_deepeval_telemetry_opt_out()


@dataclass
class MetricReport:
    metric: str
    case_name: str
    score: float | None
    success: bool | None
    error: str | None = None
    reason: str | None = None


def _optional_float(value: float | None) -> float | None:
    """Normalize metric scores for JSON (DeepEval `measure` may return None)."""
    if value is None:
        return None
    return float(value)


def _append_metric_report(
    reports: list[MetricReport],
    *,
    metric: Any,
    metric_name: str,
    case_name: str,
    exc: Exception | None = None,
) -> None:
    if exc is not None:
        reports.append(
            MetricReport(
                metric=metric_name,
                case_name=case_name,
                score=None,
                success=False,
                error=str(exc),
            )
        )
        return
    reports.append(
        MetricReport(
            metric=metric_name,
            case_name=case_name,
            score=_optional_float(getattr(metric, "score", None)),
            success=bool(getattr(metric, "success", None)),
            reason=getattr(metric, "reason", None),
        )
    )


_EVALS_DIR = Path(__file__).resolve().parent
_DEFAULT_EXAMPLE_JSON = (
    _EVALS_DIR / "examples" / "mcp_use_cases.example.json",
    _EVALS_DIR / "examples" / "mcp_red_team_cases.example.json",
)


def dry_run(cases_json: str | None) -> int:
    import evals.golden_cases as golden_cases
    from evals.json_cases import load_mcp_use_cases_from_json

    for fn_name in golden_cases.all_mcp_use_golden_fns():
        getattr(golden_cases, fn_name)()
    for fn_name in golden_cases.all_conversational_golden_fns():
        getattr(golden_cases, fn_name)()

    paths: list[Path] = []
    if cases_json:
        paths.append(Path(cases_json))
    else:
        paths.extend(p for p in _DEFAULT_EXAMPLE_JSON if p.is_file())

    for path in paths:
        loaded = load_mcp_use_cases_from_json(path)
        print(f"dry-run: loaded {len(loaded)} MCP-use case(s) from {path}")
    print("dry-run: golden case objects construct OK")
    return 0


def run_metrics(threshold: float, cases_json: str | None) -> tuple[int, list[MetricReport]]:
    from deepeval.metrics import MCPTaskCompletionMetric, MCPUseMetric, MultiTurnMCPUseMetric

    import evals.golden_cases as golden_cases
    from evals.json_cases import load_mcp_use_cases_from_json

    model = judge_model()
    reports: list[MetricReport] = []

    if cases_json:
        # Skip structural-only rows (llm_score: false), e.g. intentional invalid-arg fixtures.
        mcp_use_cases = load_mcp_use_cases_from_json(Path(cases_json), llm_only=True)
    else:
        mcp_use_cases = [
            getattr(golden_cases, fn_name)() for fn_name in golden_cases.all_mcp_use_golden_fns()
        ]

    for case in mcp_use_cases:
        m_use = MCPUseMetric(threshold=threshold, model=model, verbose_mode=False)
        try:
            # MCPUseMetric.measure(async_mode=True) runs a_measure but does not return
            # self.score (library quirk); read score from the metric instance.
            m_use.measure(case)
            _append_metric_report(
                reports,
                metric=m_use,
                metric_name="MCPUseMetric",
                case_name=case.name or "",
            )
        except Exception as exc:  # noqa: BLE001 — surface eval failures in report
            _append_metric_report(
                reports,
                metric=m_use,
                metric_name="MCPUseMetric",
                case_name=case.name or "",
                exc=exc,
            )

    task_m = MCPTaskCompletionMetric(threshold=threshold, model=model, verbose_mode=False)
    try:
        tc = golden_cases.golden_task_completion_discovery()
        task_m.measure(tc)
        _append_metric_report(
            reports,
            metric=task_m,
            metric_name="MCPTaskCompletionMetric",
            case_name=tc.name or "",
        )
    except Exception as exc:  # noqa: BLE001
        _append_metric_report(
            reports,
            metric=task_m,
            metric_name="MCPTaskCompletionMetric",
            case_name="task_completion_discovery",
            exc=exc,
        )

    for fn_name in golden_cases.all_multi_turn_mcp_use_golden_fns():
        multi_m = MultiTurnMCPUseMetric(threshold=threshold, model=model, verbose_mode=False)
        try:
            tc = getattr(golden_cases, fn_name)()
            multi_m.measure(tc)
            _append_metric_report(
                reports,
                metric=multi_m,
                metric_name="MultiTurnMCPUseMetric",
                case_name=tc.name or fn_name,
            )
        except Exception as exc:  # noqa: BLE001
            _append_metric_report(
                reports,
                metric=multi_m,
                metric_name="MultiTurnMCPUseMetric",
                case_name=fn_name,
                exc=exc,
            )

    failed = [r for r in reports if r.success is False]
    exit_code = 1 if failed else 0
    return exit_code, reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate golden case objects (no LLM calls).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=deepeval_threshold(),
        help="Metric pass threshold (default 0.5 or DEEPEVAL_THRESHOLD).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Write JSON report to this path (e.g. evals/out/report.json).",
    )
    parser.add_argument(
        "--require-key",
        action="store_true",
        help="Exit 2 if OPENAI_API_KEY is missing (default: skip LLM run with exit 0).",
    )
    parser.add_argument(
        "--cases-json",
        type=str,
        default="",
        metavar="PATH",
        help=(
            "JSON file of MCP-use cases for MCPUseMetric (see evals/json_cases.py). "
            "When set, replaces built-in single-turn MCPUse goldens; "
            "task-completion and multi-turn cases still come from golden_cases.py."
        ),
    )
    args = parser.parse_args()
    cases_json = args.cases_json.strip() or None

    if args.dry_run:
        return dry_run(cases_json)

    if not has_openai_key():
        msg = "OPENAI_API_KEY not set; skipping DeepEval LLM metrics."
        print(msg, file=sys.stderr)
        if args.require_key:
            return 2
        return 0

    exit_code, reports = run_metrics(args.threshold, cases_json)
    payload: dict[str, Any] = {
        "judge_model": judge_model(),
        "threshold": args.threshold,
        "cases_json": cases_json,
        "reports": [asdict(r) for r in reports],
    }
    text = json.dumps(payload, indent=2)
    print(text)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
