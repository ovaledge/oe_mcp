"""Register all MCP tools, resources, prompts, and static documentation."""

from __future__ import annotations

from fastmcp import FastMCP

from server.docs import register as register_doc_resources
from server.prompts import register as register_prompts
from server.resources import register as register_mcp_resources
from server.tools import access, catalog, dataquality, docs, governance, rdam, servicedesk


def register_all(mcp: FastMCP) -> None:
    catalog.register(mcp)
    access.register(mcp)
    rdam.register(mcp)
    governance.register(mcp)
    docs.register(mcp)
    register_mcp_resources(mcp)
    register_prompts(mcp)
    register_doc_resources(mcp)
    dataquality.register(mcp)
    servicedesk.register(mcp)
