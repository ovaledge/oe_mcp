"""Stable helpers for invoking FastMCP-registered components in tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools.function_tool import FunctionTool


async def get_tool_fn(mcp: FastMCP, name: str) -> Callable[..., Awaitable[Any]]:
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} not registered"
    return tool.fn  # type: ignore[no-any-return]


async def get_tool_object(mcp: FastMCP, name: str) -> FunctionTool:
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} not registered"
    return tool
