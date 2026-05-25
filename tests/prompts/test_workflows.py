"""Workflow prompts: registration, tool references, and MCP exposure."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.prompts.function_prompt import FunctionPrompt
from mcp.types import TextContent

from server.constants import (
    TOOL_ASSET_LINEAGE,
    TOOL_CATALOG_ASSET_DETAILS,
    TOOL_COLUMN_PROFILE,
    TOOL_LOOKUP_GLOSSARY_TERM,
    TOOL_LOOKUP_TAGS,
    TOOL_SEARCH_CATALOG,
    TOOL_SEARCH_DOCS,
    TOOL_TABLE_ENTITY_RELATIONSHIPS,
)
from server.prompts import workflows

WORKFLOW_PROMPT_NAMES = (
    "data_discovery",
    "explain_business_term",
    "trust_assessment",
    "explore_data_domain",
    "trace_data_lineage",
    "find_related_assets",
    "platform_help",
)

# Each prompt must reference the tools its instruction text tells the model to call.
_PROMPT_REQUIRED_TOOLS: dict[str, tuple[str, ...]] = {
    "data_discovery": (TOOL_SEARCH_CATALOG, TOOL_LOOKUP_GLOSSARY_TERM),
    "explain_business_term": (TOOL_LOOKUP_GLOSSARY_TERM, TOOL_CATALOG_ASSET_DETAILS),
    "trust_assessment": (
        TOOL_SEARCH_CATALOG,
        TOOL_CATALOG_ASSET_DETAILS,
        TOOL_ASSET_LINEAGE,
        TOOL_COLUMN_PROFILE,
    ),
    "explore_data_domain": (
        TOOL_SEARCH_CATALOG,
        TOOL_LOOKUP_GLOSSARY_TERM,
        TOOL_LOOKUP_TAGS,
    ),
    "trace_data_lineage": (
        TOOL_SEARCH_CATALOG,
        TOOL_ASSET_LINEAGE,
        TOOL_CATALOG_ASSET_DETAILS,
    ),
    "find_related_assets": (
        TOOL_SEARCH_CATALOG,
        TOOL_TABLE_ENTITY_RELATIONSHIPS,
        TOOL_CATALOG_ASSET_DETAILS,
        TOOL_LOOKUP_GLOSSARY_TERM,
        TOOL_LOOKUP_TAGS,
    ),
    "platform_help": (TOOL_SEARCH_DOCS,),
}


class TestWorkflowPromptRegistration:
    async def test_register_exposes_all_seven_prompts(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        workflows.register(mcp)
        for name in WORKFLOW_PROMPT_NAMES:
            assert await mcp.get_prompt(name) is not None


@pytest.mark.parametrize("prompt_name", WORKFLOW_PROMPT_NAMES)
class TestWorkflowPromptBodies:
    async def test_prompt_returns_instruction_message(self, prompt_name: str) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        workflows.register(mcp)
        prompt = await mcp.get_prompt(prompt_name)
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        messages = prompt.fn("sample-input")
        assert len(messages) == 1
        content = messages[0].content
        assert isinstance(content, TextContent)
        text_lower = content.text.lower()
        prompt_label = prompt_name.replace("_", " ")
        assert "sample-input" in content.text or prompt_label in text_lower

    async def test_prompt_references_expected_tools(self, prompt_name: str) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        workflows.register(mcp)
        prompt = await mcp.get_prompt(prompt_name)
        assert isinstance(prompt, FunctionPrompt)
        messages = prompt.fn("acme")
        text = messages[0].content.text
        for tool_name in _PROMPT_REQUIRED_TOOLS[prompt_name]:
            assert tool_name in text, f"{prompt_name} should mention {tool_name}"


class TestWorkflowPromptsOnFullApp:
    async def test_create_mcp_lists_all_workflow_prompts(self, mock_oe_client: object) -> None:  # noqa: ARG001
        from server.app import create_mcp

        mcp = create_mcp()
        async with Client(mcp) as client:
            listed = await client.list_prompts()
        names = {p.name for p in listed}
        assert set(WORKFLOW_PROMPT_NAMES) <= names
