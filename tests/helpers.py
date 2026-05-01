"""Stable helpers for invoking FastMCP-registered components in tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools.base import Tool
from fastmcp.tools.function_tool import FunctionTool


async def get_tool_fn(mcp: FastMCP, name: str) -> Callable[..., Awaitable[Any]]:
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} not registered"
    assert isinstance(tool, FunctionTool), f"tool {name!r} must be a @tool function wrapper"
    return tool.fn


async def get_tool_object(mcp: FastMCP, name: str) -> Tool:
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} not registered"
    return tool
