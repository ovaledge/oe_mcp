"""Shared DeepEval runner configuration (pytest + CLI)."""

from __future__ import annotations

import os


def ensure_deepeval_telemetry_opt_out() -> None:
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")


def has_openai_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPEVAL_OPENAI_API_KEY"))


def judge_model() -> str:
    return os.environ.get("DEEPEVAL_JUDGE_MODEL", "gpt-4o-mini")


def deepeval_threshold() -> float:
    return float(os.environ.get("DEEPEVAL_THRESHOLD", "0.5"))
