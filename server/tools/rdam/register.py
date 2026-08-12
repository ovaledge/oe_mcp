"""RDAM has no standalone MCP tool — surface is access_explorer."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """No standalone RDAM tool — surface is access_explorer (registered under access)."""
    del mcp
