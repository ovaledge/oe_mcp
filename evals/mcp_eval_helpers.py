"""Construct DeepEval `MCPServer` / MCP call objects compatible with `mcp.types`."""

from __future__ import annotations

from typing import Any

from deepeval.test_case import MCPServer
from mcp.types import CallToolResult, Prompt, Resource, TextContent, Tool
from pydantic import AnyUrl


def _tool_input_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "additionalProperties": True}


def ovaledge_eval_mcp_server() -> MCPServer:
    """Subset of OvalEdge MCP primitives for eval metrics (names must match the live server)."""
    tools = [
        Tool(
            name="search_catalog_assets",
            description="Catalog search",
            inputSchema=_tool_input_schema(),
        ),
        Tool(
            name="catalog_asset_details",
            description="Catalog document",
            inputSchema=_tool_input_schema(),
        ),
        Tool(
            name="lookup_glossary_term",
            description="Glossary lookup",
            inputSchema=_tool_input_schema(),
        ),
    ]
    table_uri = AnyUrl("ovaledge://catalog/table/1")
    resources = [
        Resource(
            name="catalog_table",
            uri=table_uri,
            description="Catalog table by id",
        ),
    ]
    prompts = [
        Prompt(name="data_discovery", description="Discovery workflow"),
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
