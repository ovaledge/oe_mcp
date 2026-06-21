"""MCP resources (deep-link URIs to catalog/governance documents)."""

from fastmcp import FastMCP

from server.resources import catalog, governance


def register(mcp: FastMCP) -> None:
    catalog.register(mcp)
    governance.register(mcp)


__all__ = ["register", "catalog", "governance"]
