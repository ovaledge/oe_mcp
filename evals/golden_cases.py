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


def golden_mcp_use_catalog_search() -> LLMTestCase:
    """Single-turn: agent used catalog search with structured args."""
    srv = ovaledge_eval_mcp_server()
    return LLMTestCase(
        name="mcp_use_catalog_search",
        input="Find certified tables for customer revenue reporting.",
        actual_output=(
            "I ran a catalog search for customer and revenue keywords on oetable "
            "and summarized certified results for you."
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
                result=tool_call_result({"total": 2, "results": []}),
            ),
        ],
    )


def golden_task_completion_discovery() -> ConversationalTestCase:
    """Multi-turn unit ending in assistant: search then summary."""
    srv = ovaledge_eval_mcp_server()
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
    """User follow-up: first search, then lineage-style resource read."""
    srv = ovaledge_eval_mcp_server()
    table_uri = AnyUrl("ovaledge://catalog/table/1")
    return ConversationalTestCase(
        name="multi_turn_lineage_followup",
        scenario="User refines request to include upstream lineage.",
        expected_outcome="Agent searches then inspects catalog resource or lineage.",
        mcp_servers=[srv],
        turns=[
            Turn(role="user", content="Show me customer transaction tables."),
            Turn(
                role="assistant",
                content="Running catalog search.",
                mcp_tools_called=[
                    MCPToolCall(
                        name="search_catalog_assets",
                        args={"search_terms": ["customer", "transactions"]},
                        result=tool_call_result({"total": 1, "results": [{"objectId": 1}]}),
                    ),
                ],
            ),
            Turn(role="user", content="What feeds customer_transactions upstream?"),
            Turn(
                role="assistant",
                content="Fetching catalog document for lineage context.",
                mcp_resources_called=[
                    MCPResourceCall(
                        uri=table_uri,
                        result=ReadResourceResult(
                            contents=[
                                TextResourceContents(
                                    uri=table_uri,
                                    mimeType="application/json",
                                    text='{"rootObjectId": "1", "nodes": []}',
                                )
                            ]
                        ),
                    ),
                ],
            ),
            Turn(
                role="assistant",
                content="Upstream sources are listed in the lineage graph.",
            ),
        ],
    )


def golden_mcp_use_prompt_workflow() -> LLMTestCase:
    """Agent fetched the packaged discovery prompt then searched."""
    srv = ovaledge_eval_mcp_server()
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text="Use search_catalog_assets first."),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_prompt_then_search",
        input="Follow our governance discovery workflow for churn metrics.",
        actual_output=(
            "Loaded the data_discovery prompt and executed catalog search per instructions."
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
                args={"search_terms": ["churn"], "context_query": "churn metrics"},
                result=tool_call_result({"total": 0, "results": []}),
            ),
        ],
    )


__all__ = [
    "golden_mcp_use_catalog_search",
    "golden_mcp_use_prompt_workflow",
    "golden_multi_turn_lineage_followup",
    "golden_task_completion_discovery",
]
