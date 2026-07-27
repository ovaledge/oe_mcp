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

    async def test_every_tool_exposes_a_human_readable_title(self, mcp_client) -> None:
        """Business users see title in MCP clients — keep the surface consistent."""
        async with Client(mcp_client) as client:
            tools = await client.list_tools()
        missing = sorted(t.name for t in tools if not (t.title or "").strip())
        assert not missing, f"tools without a title: {missing}"
        snake_cased = sorted(t.name for t in tools if (t.title or "") == t.name)
        assert not snake_cased, f"title must be human-readable, not the tool name: {snake_cased}"
        titles = [t.title for t in tools]
        assert len(set(titles)) == len(titles), f"duplicate tool titles: {sorted(titles)}"

    async def test_side_effect_annotations_match_the_confirm_gate(self, mcp_client) -> None:
        """readOnlyHint must agree with whether the tool is a governed write.

        Clients use these hints to auto-approve reads. A tool behind the
        write_confirmed_by_user gate mutates governance state and must never
        advertise itself as read-only.
        """
        async with Client(mcp_client) as client:
            tools = await client.list_tools()

        wrong: list[str] = []
        for tool in tools:
            assert tool.annotations is not None, f"{tool.name} has no annotations"
            properties = (tool.inputSchema or {}).get("properties", {})
            is_governed_write = "write_confirmed_by_user" in properties
            read_only = bool(tool.annotations.readOnlyHint)
            if is_governed_write == read_only:
                wrong.append(
                    f"{tool.name}: governed_write={is_governed_write} readOnlyHint={read_only}"
                )
        assert not wrong, "side-effect annotations disagree with the confirm gate:\n" + "\n".join(
            wrong
        )

        for tool in tools:
            if tool.annotations.readOnlyHint:
                assert tool.annotations.destructiveHint is False, (
                    f"{tool.name} is read-only but flagged destructive"
                )

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
