"""Full MCP surface inventory via in-process Client."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.client import Client

from server.app import create_mcp
from server.constants import DOCS_RESOURCE_URI_PREFIX
from server.docs.loader import DOCS_DIR
from server.mcp_surface import (
    MCP_OVALEDGE_RESOURCE_TEMPLATES,
    MCP_TOOL_NAMES,
    MCP_WORKFLOW_PROMPT_NAMES,
)


@pytest.fixture
def mcp_client(mock_oe_client: AsyncMock):  # noqa: ARG001
    return create_mcp()


class TestMcpSurfaceInventory:
    async def test_list_tools_matches_expected_set(self, mcp_client) -> None:
        async with Client(mcp_client) as client:
            tools = await client.list_tools()
        names = {t.name for t in tools}
        assert names == MCP_TOOL_NAMES

    async def test_list_prompts_matches_expected_set(self, mcp_client) -> None:
        async with Client(mcp_client) as client:
            prompts = await client.list_prompts()
        names = {p.name for p in prompts}
        assert names == MCP_WORKFLOW_PROMPT_NAMES

    async def test_list_resources_includes_ovaledge_and_docs(self, mcp_client) -> None:
        async with Client(mcp_client) as client:
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
        uris = {str(r.uri) for r in resources}
        template_uris = {str(t.uriTemplate) for t in templates}
        for template in MCP_OVALEDGE_RESOURCE_TEMPLATES:
            prefix = template.split("{")[0]
            assert any(u.startswith(prefix) for u in uris) or template in template_uris, (
                f"missing resource family for {template}"
            )
        for md in DOCS_DIR.glob("*.md"):
            doc_uri = f"{DOCS_RESOURCE_URI_PREFIX}/{md.stem}"
            assert doc_uri in uris
