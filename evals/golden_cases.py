"""Golden LLM / conversational cases for OvalEdge MCP DeepEval metrics."""

from __future__ import annotations

from deepeval.test_case import (
    ConversationalTestCase,
    LLMTestCase,
    MCPPromptCall,
    MCPResourceCall,
    MCPToolCall,
    Turn,
)
from mcp.types import (
    GetPromptResult,
    PromptMessage,
    ReadResourceResult,
    TextContent,
    TextResourceContents,
)
from pydantic import AnyUrl

from evals.mcp_eval_helpers import ovaledge_eval_mcp_server, tool_call_result
from server.constants import (
    TOOL_ASSET_LINEAGE,
    TOOL_CATALOG_ASSET_DETAILS,
    TOOL_LOOKUP_DATASTORY,
    TOOL_SEARCH_CATALOG,
    TOOL_SOURCE_SYSTEM_ACCESS,
)

_DATA_DISCOVERY_PROMPT_TEXT = (
    "Help me find data for: 'churn metrics'\n\n"
    "Please follow this sequence:\n"
    "1. Extract search keywords from the query\n"
    "2. Call search_catalog_assets with search_terms and context_query set to the query\n"
    "3. Present the top recommended assets with governance context"
)

_ORG_KNOWLEDGE_PROMPT_TEXT = (
    "Answer using our organization's data stories.\n\n"
    "Steps:\n"
    "1. Call lookup_datastory(content_query=...) first.\n"
    "2. Present formattedResponse; lead with storyCitation verbatim.\n"
    "3. Do not use search_platform_docs for org narrative content."
)


def golden_mcp_use_catalog_search() -> LLMTestCase:
    """Single-turn: agent used catalog search with structured args."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_SEARCH_CATALOG, TOOL_CATALOG_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_search",
        input="Find certified tables for customer revenue reporting.",
        actual_output=(
            "I used search_catalog_assets (not lookup_datastory or platform docs) because "
            "you asked for certified physical tables. I passed search_terms "
            "['customer', 'revenue'], object_type=oetable, and context_query with your "
            "full sentence for semantic ranking. I did not call catalog_asset_details yet "
            "because search was the correct first step to discover candidates."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name="search_catalog_assets",
                args={
                    "search_terms": ["customer", "revenue"],
                    "object_type": "oetable",
                    "context_query": "Find certified tables for customer revenue reporting.",
                },
                result=tool_call_result(
                    {
                        "total": 2,
                        "results": [
                            {"objectId": 101, "name": "customer_revenue_daily"},
                            {"objectId": 102, "name": "revenue_fact"},
                        ],
                    }
                ),
            ),
        ],
    )


def golden_task_completion_discovery() -> ConversationalTestCase:
    """Multi-turn unit ending in assistant: search then summary."""
    srv = ovaledge_eval_mcp_server(tool_names=frozenset({TOOL_SEARCH_CATALOG}))
    return ConversationalTestCase(
        name="task_completion_discovery",
        scenario="Analyst discovers a certified payroll table.",
        expected_outcome="Agent searches the catalog and summarizes at least one hit.",
        mcp_servers=[srv],
        turns=[
            Turn(
                role="user",
                content="Where is our payroll fact table?",
            ),
            Turn(
                role="assistant",
                content="Searching the catalog for payroll-related tables.",
                mcp_tools_called=[
                    MCPToolCall(
                        name="search_catalog_assets",
                        args={"search_terms": ["payroll"], "object_type": "oetable"},
                        result=tool_call_result(
                            {
                                "total": 1,
                                "results": [{"objectId": "obj-001", "name": "payroll_fact"}],
                            }
                        ),
                    ),
                ],
            ),
            Turn(
                role="assistant",
                content="The catalog lists payroll_fact as a certified oetable.",
            ),
        ],
    )


def golden_multi_turn_lineage_followup() -> ConversationalTestCase:
    """User follow-up: search, then asset_lineage tool for upstream context."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_SEARCH_CATALOG, TOOL_ASSET_LINEAGE}),
    )
    table_uri = AnyUrl("ovaledge://catalog/table/1")
    return ConversationalTestCase(
        name="multi_turn_lineage_followup",
        scenario="User refines request to include upstream lineage.",
        expected_outcome=(
            "Agent searches for customer_transactions, then calls asset_lineage or reads "
            "the catalog table resource and summarizes upstream nodes."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(role="user", content="Show me customer transaction tables."),
            Turn(
                role="assistant",
                content="Running catalog search for customer transaction tables.",
                mcp_tools_called=[
                    MCPToolCall(
                        name="search_catalog_assets",
                        args={
                            "search_terms": ["customer", "transactions"],
                            "object_type": "oetable",
                        },
                        result=tool_call_result(
                            {
                                "total": 1,
                                "results": [
                                    {
                                        "objectId": 1,
                                        "name": "customer_transactions",
                                        "objectType": "oetable",
                                    }
                                ],
                            }
                        ),
                    ),
                ],
            ),
            Turn(role="user", content="What feeds customer_transactions upstream?"),
            Turn(
                role="assistant",
                content=(
                    "Calling asset_lineage on customer_transactions (object_id=1, oetable) "
                    "and reading the catalog table resource for graph context."
                ),
                mcp_tools_called=[
                    MCPToolCall(
                        name="asset_lineage",
                        args={
                            "object_id": 1,
                            "object_type": "oetable",
                            "depth": 3,
                        },
                        result=tool_call_result(
                            {
                                "rootObjectId": "1",
                                "nodes": [
                                    {
                                        "id": "raw_events",
                                        "name": "raw_events",
                                        "direction": "UPSTREAM",
                                    }
                                ],
                            }
                        ),
                    ),
                ],
                mcp_resources_called=[
                    MCPResourceCall(
                        uri=table_uri,
                        result=ReadResourceResult(
                            contents=[
                                TextResourceContents(
                                    uri=table_uri,
                                    mimeType="application/json",
                                    text=(
                                        '{"objectId": 1, "name": "customer_transactions", '
                                        '"lineage": {"upstream": ["raw_events"]}}'
                                    ),
                                )
                            ]
                        ),
                    ),
                ],
            ),
            Turn(
                role="assistant",
                content=(
                    "Upstream source raw_events feeds customer_transactions per the "
                    "lineage graph returned by asset_lineage."
                ),
            ),
        ],
    )


def golden_mcp_use_prompt_workflow() -> LLMTestCase:
    """Agent fetched the packaged discovery prompt then searched."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_SEARCH_CATALOG}),
        prompt_names=frozenset({"data_discovery"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_DATA_DISCOVERY_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_prompt_then_search",
        input="Follow our governance discovery workflow for churn metrics.",
        actual_output=(
            "I invoked the data_discovery MCP prompt first; its instructions require "
            "search_catalog_assets with search_terms and context_query. I then executed "
            "that search exactly as the prompt specified (not organizational_knowledge or "
            "lookup_datastory, which are for narrative content)."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[
            MCPPromptCall(
                name="data_discovery",
                result=prompt_result,
            )
        ],
        mcp_tools_called=[
            MCPToolCall(
                name="search_catalog_assets",
                args={
                    "search_terms": ["churn", "metrics"],
                    "object_type": "oetable",
                    "context_query": "churn metrics",
                },
                result=tool_call_result(
                    {
                        "total": 1,
                        "results": [{"objectId": 55, "name": "churn_scores"}],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_datastory() -> LLMTestCase:
    """Single-turn: organizational knowledge via lookup_datastory."""
    srv = ovaledge_eval_mcp_server(tool_names=frozenset({TOOL_LOOKUP_DATASTORY}))
    return LLMTestCase(
        name="mcp_use_datastory",
        input="What is our policy on customer PII retention?",
        actual_output=(
            "This is organizational narrative content, so I used lookup_datastory with "
            "content_query (not search_platform_docs, which is for OvalEdge product "
            "documentation, and not search_catalog_assets). I am presenting "
            "formattedResponse with storyCitation as the first line."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_LOOKUP_DATASTORY,
                args={"content_query": "customer PII retention policy"},
                result=tool_call_result(
                    {
                        "ok": True,
                        "storyCitation": "[Customer PII Retention Policy](#nav/story?id=1)",
                        "formattedResponse": (
                            "[Customer PII Retention Policy](#nav/story?id=1) "
                            "(story zone: Privacy)\n\n"
                            "Retention period is 7 years for customer identifiers."
                        ),
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_organizational_knowledge_prompt() -> LLMTestCase:
    """Agent used organizational_knowledge prompt then lookup_datastory."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_LOOKUP_DATASTORY}),
        prompt_names=frozenset({"organizational_knowledge"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_ORG_KNOWLEDGE_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_organizational_knowledge_prompt",
        input="Summarize our revenue recognition playbook from data stories.",
        actual_output=(
            "Per the organizational_knowledge prompt I called lookup_datastory with "
            "content_query='revenue recognition playbook'. The tool returned "
            "formattedResponse and storyCitation; I summarized the ASC 606 playbook "
            "section for the user."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[
            MCPPromptCall(name="organizational_knowledge", result=prompt_result),
        ],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_LOOKUP_DATASTORY,
                args={"content_query": "revenue recognition playbook"},
                result=tool_call_result(
                    {
                        "ok": True,
                        "storyCitation": (
                            "[Revenue Recognition Playbook](#nav/story?id=42)"
                        ),
                        "formattedResponse": (
                            "[Revenue Recognition Playbook](#nav/story?id=42) "
                            "(story zone: Finance)\n\n"
                            "ASC 606 five-step model summary for revenue recognition."
                        ),
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_native_source_access() -> LLMTestCase:
    """Single-turn: native Redshift grants via source_system_access."""
    srv = ovaledge_eval_mcp_server(tool_names=frozenset({TOOL_SOURCE_SYSTEM_ACCESS}))
    return LLMTestCase(
        name="mcp_use_native_source_access",
        input="What tables can svc_analytics query in Redshift?",
        actual_output=(
            "This asks for native database grants (not OvalEdge catalog ACLs), so I used "
            "source_system_access with source_system=redshift, "
            "query_direction=user_to_objects, username=svc_analytics, "
            "object_path=prod, object_type=database, and connection_id for the Redshift "
            "connector. I did not use search_catalog_assets, which indexes governance metadata "
            "rather than Redshift privilege tables."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_SOURCE_SYSTEM_ACCESS,
                args={
                    "source_system": "redshift",
                    "query_direction": "user_to_objects",
                    "username": "svc_analytics",
                    "object_path": "prod",
                    "object_type": "database",
                    "connection_id": 1000,
                },
                result=tool_call_result(
                    {
                        "grants": [
                            {
                                "objectPath": "prod.public.orders",
                                "privileges": ["SELECT"],
                                "grantMechanism": "role",
                            }
                        ],
                        "summary": {"totalGrants": 1},
                    }
                ),
            ),
        ],
    )


def all_mcp_use_golden_fns() -> list[str]:
    """Names of single-turn LLMTestCase goldens for MCPUseMetric."""
    return [
        "golden_mcp_use_catalog_search",
        "golden_mcp_use_prompt_workflow",
        "golden_mcp_use_datastory",
        "golden_mcp_use_organizational_knowledge_prompt",
        "golden_mcp_use_native_source_access",
    ]


__all__ = [
    "all_mcp_use_golden_fns",
    "golden_mcp_use_catalog_search",
    "golden_mcp_use_datastory",
    "golden_mcp_use_native_source_access",
    "golden_mcp_use_organizational_knowledge_prompt",
    "golden_mcp_use_prompt_workflow",
    "golden_multi_turn_lineage_followup",
    "golden_task_completion_discovery",
]
