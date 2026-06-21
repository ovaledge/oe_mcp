"""MCP registration for static platform documentation resources."""

from __future__ import annotations

from fastmcp import FastMCP

from server.docs.loader import register_markdown_resources


def register(mcp: FastMCP) -> None:
    register_markdown_resources(mcp)
