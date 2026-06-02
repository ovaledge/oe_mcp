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
    TOOL_CREATE_GLOSSARY_TERM,
    TOOL_CREATE_TAG,
    TOOL_LOOKUP_DATASTORY,
    TOOL_LOOKUP_DQ_RULE,
    TOOL_LOOKUP_GLOSSARY_TERM,
    TOOL_LOOKUP_TAGS,
    TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
    TOOL_SEARCH_CATALOG,
    TOOL_SEARCH_DOCS,
    TOOL_SOURCE_SYSTEM_ACCESS,
    TOOL_TABLE_ENTITY_RELATIONSHIPS,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
    TOOL_UPDATE_GOVERNANCE_ROLES,
)
from server.mcp_surface import MCP_WORKFLOW_PROMPT_NAMES
from server.prompts.workflows import register as register_workflow_prompts

WORKFLOW_PROMPT_NAMES = tuple(sorted(MCP_WORKFLOW_PROMPT_NAMES))

# Each prompt must reference the tools its instruction text tells the model to call.
_PROMPT_REQUIRED_TOOLS: dict[str, tuple[str, ...]] = {
    "data_discovery": (TOOL_SEARCH_CATALOG, TOOL_LOOKUP_GLOSSARY_TERM, TOOL_LOOKUP_DATASTORY),
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
        TOOL_LOOKUP_DATASTORY,
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
    "organizational_knowledge": (
        TOOL_LOOKUP_DATASTORY,
        TOOL_SEARCH_CATALOG,
        TOOL_SEARCH_DOCS,
    ),
    "platform_help": (TOOL_SEARCH_DOCS,),
    "metadata_drift": (
        TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
        TOOL_SEARCH_CATALOG,
        TOOL_CATALOG_ASSET_DETAILS,
    ),
    "native_source_access": (TOOL_SOURCE_SYSTEM_ACCESS,),
    "explain_tag": (TOOL_LOOKUP_TAGS, TOOL_SEARCH_CATALOG),
    "explain_dq_rule": (TOOL_LOOKUP_DQ_RULE, TOOL_UPDATE_GOVERNANCE_ROLES),
    "create_business_glossary_term": (TOOL_CREATE_GLOSSARY_TERM,),
    "create_governance_tag": (TOOL_CREATE_TAG,),
    "document_asset_descriptions": (
        TOOL_SEARCH_CATALOG,
        TOOL_CATALOG_ASSET_DETAILS,
        TOOL_UPDATE_ASSET_DESCRIPTIONS,
    ),
    "assign_governance_roles": (
        TOOL_LOOKUP_DQ_RULE,
        TOOL_SEARCH_CATALOG,
        TOOL_CATALOG_ASSET_DETAILS,
        TOOL_UPDATE_GOVERNANCE_ROLES,
    ),
}


class TestWorkflowPromptRegistration:
    async def test_register_exposes_all_workflow_prompts(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        for name in WORKFLOW_PROMPT_NAMES:
            assert await mcp.get_prompt(name) is not None


@pytest.mark.parametrize("prompt_name", WORKFLOW_PROMPT_NAMES)
class TestWorkflowPromptBodies:
    async def test_prompt_returns_instruction_message(self, prompt_name: str) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt(prompt_name)
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        if prompt_name in (
            "native_source_access",
            "document_asset_descriptions",
            "assign_governance_roles",
        ):
            messages = prompt.fn("sample-a", "sample-b")
        else:
            messages = prompt.fn("sample-input")
        assert len(messages) == 1
        content = messages[0].content
        assert isinstance(content, TextContent)
        text_lower = content.text.lower()
        prompt_label = prompt_name.replace("_", " ")
        assert (
            "sample-input" in content.text
            or "sample-a" in content.text
            or prompt_label in text_lower
        )

    async def test_prompt_references_expected_tools(self, prompt_name: str) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt(prompt_name)
        assert isinstance(prompt, FunctionPrompt)
        if prompt_name in (
            "native_source_access",
            "document_asset_descriptions",
            "assign_governance_roles",
        ):
            messages = prompt.fn("acme", "details")
        else:
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


class TestMcpServerInstructions:
    def test_instructions_prioritize_data_stories_for_org_knowledge(self) -> None:
        from server.app import create_mcp

        mcp = create_mcp()
        instructions = (mcp.instructions or "").lower()
        assert "lookup_datastory" in instructions
        assert "search_platform_docs" in instructions
        assert "ovaledge://governance/data-story" in instructions
