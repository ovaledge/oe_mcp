"""Construct DeepEval `MCPServer` / MCP call objects compatible with `mcp.types`."""

from __future__ import annotations

from typing import Any

from deepeval.test_case import MCPServer
from mcp.types import CallToolResult, Prompt, Resource, TextContent, Tool
from pydantic import AnyUrl

from server.mcp_surface import (
    MCP_OVALEDGE_RESOURCE_TEMPLATES,
    MCP_TOOL_NAMES,
    MCP_WORKFLOW_PROMPT_NAMES,
)


def _tool_input_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "additionalProperties": True}


def _sample_resource_uri(template: str) -> AnyUrl:
    """Fill template placeholders for eval Resource metadata."""
    sample = template
    for key in ("object_id", "object_type"):
        sample = sample.replace(f"{{{key}}}", "1")
    return AnyUrl(sample)


def ovaledge_eval_mcp_server(
    *,
    tool_names: frozenset[str] | None = None,
    prompt_names: frozenset[str] | None = None,
) -> MCPServer:
    """
    Build MCPServer metadata for DeepEval judges.

    Pass ``tool_names`` / ``prompt_names`` subsets per golden case so the judge
    does not recommend unrelated tools (e.g. search_platform_docs for data stories).
    """
    selected_tools = tool_names if tool_names is not None else MCP_TOOL_NAMES
    selected_prompts = prompt_names if prompt_names is not None else MCP_WORKFLOW_PROMPT_NAMES
    tools = [
        Tool(
            name=name,
            description=f"OvalEdge MCP tool: {name}",
            inputSchema=_tool_input_schema(),
        )
        for name in sorted(selected_tools)
    ]
    def _resource_name(template: str) -> str:
        return (
            template.replace("ovaledge://", "")
            .replace("/", "_")
            .replace("{", "")
            .replace("}", "")
        )

    resources = [
        Resource(
            name=_resource_name(template),
            uri=_sample_resource_uri(template),
            description=f"OvalEdge resource template: {template}",
        )
        for template in sorted(MCP_OVALEDGE_RESOURCE_TEMPLATES)
    ]
    prompts = [
        Prompt(name=name, description=f"OvalEdge workflow prompt: {name}")
        for name in sorted(selected_prompts)
    ]
    return MCPServer(
        server_name="ovaledge-local",
        transport="stdio",
        available_tools=tools,
        available_resources=resources,
        available_prompts=prompts,
    )


def tool_call_result(payload: dict[str, Any]) -> CallToolResult:
    """CallToolResult with structuredContent shape expected by MCPTaskCompletionMetric."""
    return CallToolResult(
        content=[TextContent(type="text", text="{}", annotations=None)],
        structuredContent={"result": payload},
        isError=False,
    )


__all__ = [
    "CallToolResult",
    "TextContent",
    "ovaledge_eval_mcp_server",
    "tool_call_result",
]
