"""
OvalEdge MCP server package.

- ``server.app`` — FastMCP factory and shared ``mcp`` instance
- ``server.mcp`` — register tools, resources, prompts, and static docs
- ``server.tools`` — MCP tool domains (catalog, governance, docs, rdam, common)
- ``server.resources`` — MCP URI resources (deep links)
- ``server.prompts`` — workflow prompts
- ``server.docs`` — static markdown doc resources (``docs://ovaledge/...``)
- ``server.config`` — typed settings (``.env``)
- ``server.client`` — OvalEdge HTTP transport
"""
