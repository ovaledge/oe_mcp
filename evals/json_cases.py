"""Load `LLMTestCase` rows for `MCPUseMetric` from user JSON on disk.

DeepEval does not execute JSON by itself: your pipeline reads JSON, builds `LLMTestCase` / tool
calls, then runs metrics (`assert_test` or `metric.measure`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deepeval.test_case import LLMTestCase, MCPToolCall

from evals.mcp_eval_helpers import ovaledge_eval_mcp_server, tool_call_result


def _require_str(obj: dict[str, Any], key: str, *, ctx: str) -> str:
    v = obj.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{ctx}: {key!r} must be a non-empty string")
    return v


def _tool_call_from_obj(obj: Any, *, ctx: str) -> MCPToolCall:
    if not isinstance(obj, dict):
        raise ValueError(f"{ctx}: each mcp_tools_called entry must be a JSON object")
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{ctx}: tool.name must be a non-empty string")
    args = obj.get("args")
    if args is None:
        args_dict: dict[str, Any] = {}
    elif isinstance(args, dict):
        args_dict = args
    else:
        raise ValueError(f"{ctx}: tool.args must be a JSON object if present")
    result_raw = obj.get("result", {})
    if not isinstance(result_raw, dict):
        raise ValueError(
            f"{ctx}: tool.result must be a JSON object "
            "(payload for CallToolResult structured content)"
        )
    return MCPToolCall(name=name, args=args_dict, result=tool_call_result(result_raw))


def _case_from_obj(obj: Any, index: int) -> LLMTestCase:
    ctx = f"mcp_use_cases[{index}]"
    if not isinstance(obj, dict):
        raise ValueError(f"{ctx}: must be a JSON object")
    name = obj.get("name")
    if name is not None and not isinstance(name, str):
        raise ValueError(f"{ctx}: name must be a string if present")
    input_text = _require_str(obj, "input", ctx=ctx)
    actual = _require_str(obj, "actual_output", ctx=ctx)
    tools_raw = obj.get("mcp_tools_called", [])
    if not isinstance(tools_raw, list):
        raise ValueError(f"{ctx}: mcp_tools_called must be a JSON array")
    tools = [
        _tool_call_from_obj(t, ctx=f"{ctx}.mcp_tools_called[{i}]")
        for i, t in enumerate(tools_raw)
    ]
    srv = ovaledge_eval_mcp_server()
    return LLMTestCase(
        name=name or f"json_case_{index}",
        input=input_text,
        actual_output=actual,
        mcp_servers=[srv],
        mcp_tools_called=tools,
    )


def load_mcp_use_cases_from_json(path: Path) -> list[LLMTestCase]:
    """Parse JSON into `LLMTestCase` instances for `MCPUseMetric`.

    **Root shape** (either):

    - A JSON array of case objects.
    - A JSON object with key ``mcp_use_cases`` (preferred) or ``cases`` — array of case objects.

    **Each case object** (MCP tool use only in v1):

    - ``name`` (optional string)
    - ``input`` (required) — user prompt
    - ``actual_output`` (required) — assistant reply text
    - ``mcp_tools_called`` (array) — objects with ``name``, optional ``args`` (object), optional
      ``result`` (object; becomes the structured tool payload, same as in ``golden_cases.py``)
    """
    text = path.read_text(encoding="utf-8")
    raw: Any = json.loads(text)
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        if "mcp_use_cases" in raw:
            items = raw["mcp_use_cases"]
        elif "cases" in raw:
            items = raw["cases"]
        else:
            raise ValueError(
                "JSON root object must contain array key 'mcp_use_cases' or 'cases'"
            )
    else:
        raise ValueError("JSON root must be an array or an object with mcp_use_cases/cases")

    if not isinstance(items, list):
        raise ValueError("mcp_use_cases (or cases) must be a JSON array")

    return [_case_from_obj(item, i) for i, item in enumerate(items)]


__all__ = ["load_mcp_use_cases_from_json"]
