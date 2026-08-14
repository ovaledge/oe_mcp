"""Workflow prompts: registration, tool references, and MCP exposure."""

from __future__ import annotations

import re

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.prompts.function_prompt import FunctionPrompt
from mcp.types import TextContent

from server.constants import (
    TOOL_ACCESS_EXPLORER,
    TOOL_ASSET_DETAILS,
    TOOL_ASSET_EXPLORER,
    TOOL_ASSET_LINEAGE,
    TOOL_CREATE_GLOSSARY_TERM,
    TOOL_CREATE_TAG,
    TOOL_DQ_RULE_ADVISOR,
    TOOL_DQ_RULE_MANAGER,
    TOOL_KNOWLEDGE_SEARCH,
    TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
    TOOL_UPDATE_GOVERNANCE_ROLES,
)
from server.mcp_surface import MCP_WORKFLOW_PROMPT_NAMES
from server.prompts.workflows import register as register_workflow_prompts

WORKFLOW_PROMPT_NAMES = tuple(sorted(MCP_WORKFLOW_PROMPT_NAMES))

# Each prompt must reference the tools its instruction text tells the model to call.
_PROMPT_REQUIRED_TOOLS: dict[str, tuple[str, ...]] = {
    "data_discovery": (TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS, TOOL_KNOWLEDGE_SEARCH),
    "explain_business_term": (TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS),
    "trust_assessment": (
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
        TOOL_ASSET_LINEAGE,
    ),
    "explore_data_domain": (
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
        TOOL_KNOWLEDGE_SEARCH,
    ),
    "trace_data_lineage": (
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_LINEAGE,
        TOOL_ASSET_DETAILS,
    ),
    "find_related_assets": (
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
    ),
    "organizational_knowledge": (
        TOOL_KNOWLEDGE_SEARCH,
        TOOL_ASSET_EXPLORER,
    ),
    "native_source_access": (TOOL_ACCESS_EXPLORER,),
    "resolve_object_access": (
        TOOL_ACCESS_EXPLORER,
        TOOL_ASSET_EXPLORER,
    ),
    "dam_object_browse": (TOOL_ACCESS_EXPLORER,),
    "catalog_object_access": (TOOL_ACCESS_EXPLORER, TOOL_ASSET_EXPLORER),
    "platform_help": (TOOL_KNOWLEDGE_SEARCH,),
    "metadata_drift": (
        TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
    ),
    "explain_tag": (TOOL_ASSET_EXPLORER,),
    "explain_dq_rule": (TOOL_DQ_RULE_ADVISOR, TOOL_UPDATE_GOVERNANCE_ROLES),
    "create_business_glossary_term": (TOOL_CREATE_GLOSSARY_TERM,),
    "create_governance_tag": (TOOL_CREATE_TAG,),
    "document_asset_descriptions": (
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
        TOOL_UPDATE_ASSET_DESCRIPTIONS,
    ),
    "assign_governance_roles": (
        TOOL_DQ_RULE_ADVISOR,
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
        TOOL_UPDATE_GOVERNANCE_ROLES,
    ),
    "assess_cde_dq_coverage": (
        TOOL_ASSET_EXPLORER,
        TOOL_DQ_RULE_ADVISOR,
        TOOL_DQ_RULE_MANAGER,
    ),
    "create_custom_sql_dq_workflow": (
        TOOL_ASSET_EXPLORER,
        TOOL_DQ_RULE_ADVISOR,
        TOOL_DQ_RULE_MANAGER,
    ),
}


class TestWorkflowPromptRegistration:
    async def test_register_exposes_all_workflow_prompts(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        for name in WORKFLOW_PROMPT_NAMES:
            assert await mcp.get_prompt(name) is not None

    async def test_custom_sql_prompt_preserves_set_membership_function(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt("create_custom_sql_dq_workflow")
        assert isinstance(prompt, FunctionPrompt)

        text = prompt.fn("version must be in (2,3,4,5)")[0].content.text

        assert "recommendedFunction" in text
        assert "IN/NOT IN set-membership is SQL Values Contains" in text
        assert "auto-retry" in text.lower() or "ask the user" in text.lower()
        assert "stop" in text.lower()


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
        elif prompt_name == "dam_object_browse":
            messages = prompt.fn(1000, "sample-scope")
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
            or "sample-scope" in content.text
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
        elif prompt_name == "dam_object_browse":
            messages = prompt.fn(1000, "BUSINESS.BANKING")
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
        from server.app import MCP_SERVER_INSTRUCTION_TOOL_NAMES, create_mcp
        from server.constants import (
            TOOL_ACCESS_EXPLORER,
            TOOL_ASSET_DETAILS,
            TOOL_ASSET_EXPLORER,
            TOOL_KNOWLEDGE_SEARCH,
        )
        from server.mcp_surface import MCP_TOOL_NAMES

        mcp = create_mcp()
        instructions = (mcp.instructions or "").lower()
        assert TOOL_KNOWLEDGE_SEARCH in instructions
        assert TOOL_ASSET_EXPLORER in instructions
        assert TOOL_ASSET_DETAILS in instructions
        assert TOOL_ACCESS_EXPLORER in instructions
        assert "write_confirmed_by_user" in instructions
        assert "never show ovaledge://" in instructions
        assert "find data assets" in instructions
        assert "omit object_type" in instructions
        assert "blanket" not in instructions
        navlink = "navlink" in instructions or "redirecturl" in instructions
        assert navlink
        assert MCP_SERVER_INSTRUCTION_TOOL_NAMES <= MCP_TOOL_NAMES

    def test_instructions_platform_name_alone_does_not_skip_disambiguation(self) -> None:
        from server.app import create_mcp

        mcp = create_mcp()
        instructions = (mcp.instructions or "").lower()
        assert "business.banking" in instructions
        assert "snowflake" in instructions
        assert "redshift" in instructions
        assert "1" in instructions and "2" in instructions

    def test_instructions_have_no_duplicated_guidance(self) -> None:
        """Always-on instructions are pure context cost — no sentence may repeat."""
        from server.app import create_mcp

        mcp = create_mcp()
        sentences = [
            s.strip().lower()
            for s in re.split(r"(?<=[.!?])\s+", mcp.instructions or "")
            if len(s.strip()) > 25
        ]
        repeated = sorted({s for s in sentences if sentences.count(s) > 1})
        assert not repeated, f"duplicated instruction sentences: {repeated}"

    def test_instructions_require_mcp_workflows_resource(self) -> None:
        from server.app import create_mcp
        from server.constants import DOCS_RESOURCE_URI_PREFIX

        mcp = create_mcp()
        instructions = (mcp.instructions or "").lower()
        assert f"{DOCS_RESOURCE_URI_PREFIX}/mcp_workflows" in instructions
        assert "session start" in instructions
        assert "routing guide" in instructions
        assert "what tables can i see/access" in instructions
        assert "for ambiguous who-has-access only" in instructions


class TestDiscoveryPromptsOpenCatalogSearch:
    async def test_data_discovery_omits_object_type_by_default(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt("data_discovery")
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        text = prompt.fn("Find all assets related to payment")[0].content.text.lower()
        assert "find related assets" in text
        assert "omit object_type" in text
        assert TOOL_ASSET_DETAILS in text
        assert "blanket" not in text

    async def test_find_related_assets_starts_with_open_catalog_search(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt("find_related_assets")
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        text = prompt.fn("payment")[0].content.text.lower()
        assert "find related assets" in text
        assert "omit object_type" in text
        assert "blanket" not in text
        assert "oetable-only" in text
        assert TOOL_ASSET_DETAILS in text


class TestResolveObjectAccessPrompt:
    async def test_prompt_includes_platform_not_signal_examples(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt("resolve_object_access")
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        messages = prompt.fn("Who has access to BUSINESS.BANKING in Snowflake?")
        text = messages[0].content.text.lower()
        assert "business.banking" in text
        assert "snowflake" in text
        assert "customer1" in text
        assert "access_intent_confirmed" in text
        assert "what tables/schemas/columns can i see/view/access" in text
        assert "named principal" in text
        assert TOOL_ASSET_EXPLORER in messages[0].content.text

    async def test_prompt_docstring_excludes_first_person_inventory(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt("resolve_object_access")
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        doc = (prompt.fn.__doc__ or "").lower()
        assert "what tables can i see/access" in doc
        assert "data_discovery" in doc
        assert "not:" in doc


class TestDataDiscoveryFirstPersonTriggers:
    async def test_data_discovery_docstring_includes_first_person_see_access(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt("data_discovery")
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        doc = (prompt.fn.__doc__ or "").lower()
        assert "what tables can i see/access" in doc
        assert "what schemas/columns can i view" in doc


class TestNativeAndDamBrowseGuards:
    async def test_native_source_access_guards_generic_first_person(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt("native_source_access")
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        doc = (prompt.fn.__doc__ or "").lower()
        assert "what tables can i access in redshift" in doc
        assert "data_discovery" in doc
        text = prompt.fn("redshift", "What can svc access?")[0].content.text.lower()
        assert "data_discovery" in text
        assert TOOL_ASSET_EXPLORER in prompt.fn("redshift", "What can svc access?")[0].content.text

    async def test_dam_object_browse_guards_generic_inventory(self) -> None:
        mcp = FastMCP(name="test", version="0.0.1")
        register_workflow_prompts(mcp)
        prompt = await mcp.get_prompt("dam_object_browse")
        assert prompt is not None
        assert isinstance(prompt, FunctionPrompt)
        doc = (prompt.fn.__doc__ or "").lower()
        assert "what tables can i see" in doc
        assert "data_discovery" in doc
        text = prompt.fn(1000, "BUSINESS.BANKING")[0].content.text.lower()
        assert "data_discovery" in text
        assert TOOL_ASSET_EXPLORER in prompt.fn(1000, "BUSINESS.BANKING")[0].content.text
