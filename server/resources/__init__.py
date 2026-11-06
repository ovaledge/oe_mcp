"""MCP resources (deep-link URIs to catalog/governance documents)."""

from fastmcp import FastMCP

from server.resources import apps, catalog, governance


def register(mcp: FastMCP) -> None:
    catalog.register(mcp)
    governance.register(mcp)
    apps.register(mcp)


__all__ = ["register", "apps", "catalog", "governance"]
