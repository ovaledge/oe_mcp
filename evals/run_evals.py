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

# Opt out before importing deepeval (reads env at import time in some versions).
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")


@dataclass
class MetricReport:
    metric: str
    case_name: str
    score: float | None
    success: bool | None
    error: str | None = None
    reason: str | None = None


def _judge_model() -> str:
    return os.environ.get("DEEPEVAL_JUDGE_MODEL", "gpt-4o-mini")


def _has_openai_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPEVAL_OPENAI_API_KEY"))


def _optional_float(value: float | None) -> float | None:
    """Normalize metric scores for JSON (DeepEval `measure` may return None)."""
    if value is None:
        return None
    return float(value)


def dry_run(cases_json: str | None) -> int:
    import evals.golden_cases as golden_cases

    for fn_name in golden_cases.all_mcp_use_golden_fns():
        getattr(golden_cases, fn_name)()
    golden_cases.golden_task_completion_discovery()
    golden_cases.golden_multi_turn_lineage_followup()
    if cases_json:
        from evals.json_cases import load_mcp_use_cases_from_json

        path = Path(cases_json)
        loaded = load_mcp_use_cases_from_json(path)
        print(f"dry-run: loaded {len(loaded)} MCP-use case(s) from {path}")
    print("dry-run: golden case objects construct OK")
    return 0


def run_metrics(threshold: float, cases_json: str | None) -> tuple[int, list[MetricReport]]:
    from deepeval.metrics import MCPTaskCompletionMetric, MCPUseMetric, MultiTurnMCPUseMetric

    import evals.golden_cases as golden_cases
    from evals.json_cases import load_mcp_use_cases_from_json

    model = _judge_model()
    reports: list[MetricReport] = []

    if cases_json:
        mcp_use_cases = load_mcp_use_cases_from_json(Path(cases_json))
    else:
        mcp_use_cases = [
            getattr(golden_cases, fn_name)() for fn_name in golden_cases.all_mcp_use_golden_fns()
        ]

    for case in mcp_use_cases:
        m_use = MCPUseMetric(threshold=threshold, model=model, verbose_mode=False)
        try:
            # MCPUseMetric.measure(async_mode=True) runs a_measure but does not return
            # self.score (library quirk); read score from the metric instance.
            m_use.measure(case, _log_metric_to_confident=False)
            reports.append(
                MetricReport(
                    metric="MCPUseMetric",
                    case_name=case.name or "",
                    score=_optional_float(getattr(m_use, "score", None)),
                    success=bool(getattr(m_use, "success", None)),
                    reason=getattr(m_use, "reason", None),
                )
            )
        except Exception as exc:  # noqa: BLE001 — surface eval failures in report
            reports.append(
                MetricReport(
                    metric="MCPUseMetric",
                    case_name=case.name or "",
                    score=None,
                    success=False,
                    error=str(exc),
                )
            )

    task_m = MCPTaskCompletionMetric(threshold=threshold, model=model, verbose_mode=False)
    try:
        tc = golden_cases.golden_task_completion_discovery()
        task_m.measure(tc, _log_metric_to_confident=False)
        reports.append(
            MetricReport(
                metric="MCPTaskCompletionMetric",
                case_name=tc.name or "",
                score=_optional_float(getattr(task_m, "score", None)),
                success=bool(getattr(task_m, "success", None)),
                reason=getattr(task_m, "reason", None),
            )
        )
    except Exception as exc:  # noqa: BLE001
        reports.append(
            MetricReport(
                metric="MCPTaskCompletionMetric",
                case_name="task_completion_discovery",
                score=None,
                success=False,
                error=str(exc),
            )
        )

    multi_m = MultiTurnMCPUseMetric(threshold=threshold, model=model, verbose_mode=False)
    try:
        tc2 = golden_cases.golden_multi_turn_lineage_followup()
        multi_m.measure(tc2, _log_metric_to_confident=False)
        reports.append(
            MetricReport(
                metric="MultiTurnMCPUseMetric",
                case_name=tc2.name or "",
                score=_optional_float(getattr(multi_m, "score", None)),
                success=bool(getattr(multi_m, "success", None)),
                reason=getattr(multi_m, "reason", None),
            )
        )
    except Exception as exc:  # noqa: BLE001
        reports.append(
            MetricReport(
                metric="MultiTurnMCPUseMetric",
                case_name="multi_turn_lineage_followup",
                score=None,
                success=False,
                error=str(exc),
            )
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
        default=float(os.environ.get("DEEPEVAL_THRESHOLD", "0.5")),
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
            "When set, replaces the two built-in single-turn MCPUse goldens; "
            "task-completion and multi-turn cases still come from golden_cases.py."
        ),
    )
    args = parser.parse_args()
    cases_json = args.cases_json.strip() or None

    if args.dry_run:
        return dry_run(cases_json)

    if not _has_openai_key():
        msg = "OPENAI_API_KEY not set; skipping DeepEval LLM metrics."
        print(msg, file=sys.stderr)
        if args.require_key:
            return 2
        return 0

    exit_code, reports = run_metrics(args.threshold, cases_json)
    payload: dict[str, Any] = {
        "judge_model": _judge_model(),
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
