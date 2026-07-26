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

from evals import golden_cases_coverage
from evals.mcp_eval_helpers import ovaledge_eval_mcp_server, tool_call_result
from server.constants import (
    DOCS_RESOURCE_URI_PREFIX,
    TOOL_ASSET_DETAILS,
    TOOL_ASSET_EXPLORER,
    TOOL_ASSET_LINEAGE,
    TOOL_GET_USER_OBJECT_ACCESS,
    TOOL_KNOWLEDGE_SEARCH,
    TOOL_SOURCE_SYSTEM_ACCESS,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
)
from server.docs.loader import read_doc_markdown
from server.tools.common.confirm_gate import compute_confirmation_token

_MCP_WORKFLOWS_RESOURCE_URI = AnyUrl(f"{DOCS_RESOURCE_URI_PREFIX}/mcp_workflows")

# Compatibility variable names keep the golden case structure concise while all
# expected MCP calls resolve to the consolidated read-tool names.
TOOL_SEARCH_CATALOG = TOOL_ASSET_EXPLORER
TOOL_CATALOG_ASSET_DETAILS = TOOL_ASSET_DETAILS
TOOL_LOOKUP_DATASTORY = TOOL_KNOWLEDGE_SEARCH
TOOL_SEARCH_DOCS = TOOL_KNOWLEDGE_SEARCH

_DATA_DISCOVERY_PROMPT_TEXT = (
    "Help me find data for: 'churn metrics'\n\n"
    "Please follow this sequence:\n"
    "1. Extract search keywords from the query\n"
    "2. Call asset_explorer with search_terms and context_query set to the query\n"
    "3. Present the top recommended assets with governance context"
)

_ORG_KNOWLEDGE_PROMPT_TEXT = (
    "Answer using our organization's data stories.\n\n"
    "Steps:\n"
    "1. Call knowledge_search(query=...) first.\n"
    "2. Present formattedResponse; lead with storyCitation verbatim.\n"
    "3. Knowledge search covers both corpora."
)

_PLATFORM_HELP_PROMPT_TEXT = (
    "Help the user with OvalEdge product documentation.\n\n"
    "Question: How do I create a data quality rule in OvalEdge?\n\n"
    "Steps:\n"
    "1. Call knowledge_search with the user's question.\n"
    "2. Summarize the documentation hits.\n"
    "3. Knowledge search covers product and organizational knowledge."
)

_CATALOG_OBJECT_ACCESS_PROMPT_TEXT = (
    "Check OvalEdge catalog ACL access.\n\n"
    "User: john.doe\n"
    "Object: payroll_fact (oetable)\n\n"
    "Steps:\n"
    "1. Call get_user_object_access with query_direction=user_to_object.\n"
    "2. Do not use source_system_access (native DB grants).\n"
    "3. Optionally asset_explorer only to resolve object_id if needed."
)

_DOCUMENT_ASSET_DESCRIPTIONS_PROMPT_TEXT = (
    "Document an asset description with human confirmation.\n\n"
    "Target: customer_revenue_daily (oetable)\n"
    "New business description: Quarterly revenue summary for finance analysts.\n\n"
    "Steps:\n"
    "1. asset_explorer or asset_details to resolve object_id.\n"
    "2. Call update_asset_descriptions WITHOUT write_confirmed_by_user for preview.\n"
    "3. Show confirmationToken; wait for explicit user approval.\n"
    "4. Re-call with write_confirmed_by_user=true and confirmation_token from preview."
)

_GOVERNED_WRITE_POST_BODY: dict[str, object] = {
    "target": {"objectId": 42, "objectType": "oetable"},
    "descriptions": {
        "description": "Quarterly revenue summary for finance analysts.",
        "descriptionField": "businessDescription",
    },
}
_GOVERNED_WRITE_CONFIRMATION_TOKEN = compute_confirmation_token(_GOVERNED_WRITE_POST_BODY)


def golden_mcp_use_catalog_search() -> LLMTestCase:
    """Single-turn: agent used catalog search with structured args."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_SEARCH_CATALOG, TOOL_CATALOG_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_search",
        input="Find certified tables for customer revenue reporting.",
        actual_output=(
            "I used asset_explorer (not knowledge_search or platform docs) because "
            "you asked for certified physical tables. I passed search_terms "
            "['customer', 'revenue'], object_type=oetable, and context_query with your "
            "full sentence for semantic ranking. I did not call asset_details yet "
            "because search was the correct first step to discover candidates."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name="asset_explorer",
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
                        name="asset_explorer",
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
                        name="asset_explorer",
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
            "asset_explorer with search_terms and context_query. I then executed "
            "that search exactly as the prompt specified (not organizational_knowledge or "
            "knowledge_search, which are for narrative content)."
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
                name="asset_explorer",
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
    """Single-turn: organizational knowledge via knowledge_search."""
    srv = ovaledge_eval_mcp_server(tool_names=frozenset({TOOL_LOOKUP_DATASTORY}))
    return LLMTestCase(
        name="mcp_use_datastory",
        input="What is our policy on customer PII retention?",
        actual_output=(
            "This is organizational narrative content, so I used knowledge_search with "
            "query (dual corpus: data stories + platform docs; not asset_explorer for "
            "tables). I am presenting formattedResponse with storyCitation as the "
            "first line."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_LOOKUP_DATASTORY,
                args={"query": "customer PII retention policy"},
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
    """Agent used organizational_knowledge prompt then knowledge_search."""
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
            "Per the organizational_knowledge prompt I called knowledge_search with "
            "query='revenue recognition playbook'. The tool returned "
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
                args={"query": "revenue recognition playbook"},
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
            "connector. I did not use asset_explorer, which indexes governance metadata "
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


def golden_mcp_use_routing_guide_resource() -> LLMTestCase:
    """Agent reads mcp_workflows resource before native source access (RDAM routing)."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_SOURCE_SYSTEM_ACCESS}),
    )
    workflows_text = read_doc_markdown("mcp_workflows")
    resource_result = ReadResourceResult(
        contents=[
            TextResourceContents(
                uri=_MCP_WORKFLOWS_RESOURCE_URI,
                mimeType="text/markdown",
                text=workflows_text,
            )
        ]
    )
    return LLMTestCase(
        name="mcp_use_routing_guide_resource",
        input="Who has native SELECT on prod_db.public.orders in Snowflake?",
        actual_output=(
            "I read docs://ovaledge/mcp_workflows first for RDAM routing, then called "
            "source_system_access with query_direction=object_to_users, source_system=snowflake, "
            "object_path=prod_db.public.orders, and object_type=table. I did not use "
            "asset_explorer or get_user_object_access — native grants are RDAM-only."
        ),
        mcp_servers=[srv],
        mcp_resources_called=[
            MCPResourceCall(uri=_MCP_WORKFLOWS_RESOURCE_URI, result=resource_result),
        ],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_SOURCE_SYSTEM_ACCESS,
                args={
                    "source_system": "snowflake",
                    "query_direction": "object_to_users",
                    "object_path": "prod_db.public.orders",
                    "object_type": "table",
                    "connection_id": 1000,
                },
                result=tool_call_result(
                    {
                        "grants": [
                            {
                                "objectPath": "prod_db.public.orders",
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


def golden_mcp_use_platform_help() -> LLMTestCase:
    """Single-turn: platform_help prompt → knowledge_search (not data stories)."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_SEARCH_DOCS}),
        prompt_names=frozenset({"platform_help"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_PLATFORM_HELP_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_platform_help",
        input="How do I create a data quality rule in OvalEdge?",
        actual_output=(
            "This is OvalEdge product documentation, so I invoked the platform_help MCP "
            "prompt and called knowledge_search with query='create data quality rule'. "
            "I did not use asset_explorer (catalog metadata) for product how-to."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[MCPPromptCall(name="platform_help", result=prompt_result)],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_SEARCH_DOCS,
                args={"query": "create data quality rule", "limit": 7},
                result=tool_call_result(
                    {
                        "hits": [
                            {
                                "title": "Create DQ rules",
                                "snippet": "Use the DQ rules workspace to define functions.",
                                "url": "https://docs.ovaledge.com/dq/create",
                            }
                        ],
                        "total": 1,
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_catalog_object_access() -> LLMTestCase:
    """Single-turn: catalog_object_access prompt → get_user_object_access."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_GET_USER_OBJECT_ACCESS, TOOL_SEARCH_CATALOG}),
        prompt_names=frozenset({"catalog_object_access"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_CATALOG_OBJECT_ACCESS_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_catalog_object_access",
        input="Can john.doe read the payroll_fact table in OvalEdge?",
        actual_output=(
            "Catalog ACL checks use get_user_object_access with query_direction=user_to_object, "
            "username=john.doe, object_id=101, object_type=oetable. I did not call "
            "source_system_access because that returns native database grants, not OvalEdge "
            "catalog permissions."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[
            MCPPromptCall(name="catalog_object_access", result=prompt_result),
        ],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_GET_USER_OBJECT_ACCESS,
                args={
                    "query_direction": "user_to_object",
                    "username": "john.doe",
                    "object_id": 101,
                    "object_type": "oetable",
                },
                result=tool_call_result(
                    {
                        "ok": True,
                        "data": {
                            "queryDirection": "user_to_object",
                            "username": "john.doe",
                            "objectId": 101,
                            "objectType": "oetable",
                            "accessLevel": "read",
                        },
                    }
                ),
            ),
        ],
    )


def golden_governed_write_confirm_two_step() -> ConversationalTestCase:
    """Multi-turn: preview update_asset_descriptions, then confirm with bound token."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({
            TOOL_SEARCH_CATALOG,
            TOOL_CATALOG_ASSET_DETAILS,
            TOOL_UPDATE_ASSET_DESCRIPTIONS,
        }),
        prompt_names=frozenset({"document_asset_descriptions"}),
    )
    doc_prompt = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=_DOCUMENT_ASSET_DESCRIPTIONS_PROMPT_TEXT,
                ),
            )
        ],
    )
    preview_result = tool_call_result(
        {
            "workflowPhase": "confirm_update",
            "doNotUpdate": True,
            "writeConfirmedByUser": False,
            "confirmationToken": _GOVERNED_WRITE_CONFIRMATION_TOKEN,
            "formattedResponse": (
                "**Confirm description update**\n\n"
                "- **Object:** customer_revenue_daily (oetable id 42)\n"
                "- **Field:** business description\n\n"
                "Ask the user to confirm before POST."
            ),
        }
    )
    post_result = tool_call_result(
        {
            "status": "success",
            "updatedFields": ["businessDescription"],
            "target": {
                "objectId": 42,
                "objectType": "oetable",
                "redirectUrl": "https://mock.ovaledge.com/#nav/table?id=42",
            },
        }
    )
    return ConversationalTestCase(
        name="governed_write_confirm_two_step",
        scenario=(
            "User requests a governed business-description update and explicitly confirms "
            "after the preview step."
        ),
        expected_outcome=(
            "Agent calls update_asset_descriptions for preview without POST, surfaces "
            "confirmationToken, waits for user approval, then re-calls with "
            "write_confirmed_by_user=true and the same confirmation_token."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(
                role="user",
                content=(
                    "Set the business description on customer_revenue_daily to "
                    "'Quarterly revenue summary for finance analysts.'"
                ),
            ),
            Turn(
                role="assistant",
                content=(
                    "Loading document_asset_descriptions workflow and resolving the table."
                ),
                mcp_prompts_called=[
                    MCPPromptCall(name="document_asset_descriptions", result=doc_prompt),
                ],
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_SEARCH_CATALOG,
                        args={
                            "search_terms": ["customer", "revenue", "daily"],
                            "object_type": "oetable",
                        },
                        result=tool_call_result(
                            {
                                "total": 1,
                                "results": [
                                    {
                                        "objectId": 42,
                                        "name": "customer_revenue_daily",
                                        "objectType": "oetable",
                                    }
                                ],
                            }
                        ),
                    ),
                ],
            ),
            Turn(
                role="assistant",
                content=(
                    "Preview only: update_asset_descriptions returned confirm_update with "
                    "doNotUpdate=true. I am showing the preview and waiting — no POST yet."
                ),
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_UPDATE_ASSET_DESCRIPTIONS,
                        args={
                            "object_id": 42,
                            "object_type": "oetable",
                            "description_field": "business_description",
                            "description_text": (
                                "Quarterly revenue summary for finance analysts."
                            ),
                            "write_confirmed_by_user": False,
                        },
                        result=preview_result,
                    ),
                ],
            ),
            Turn(role="user", content="Yes, apply that description."),
            Turn(
                role="assistant",
                content=(
                    "User approved. POSTing with write_confirmed_by_user=true and "
                    "confirmation_token from the preview (payload unchanged)."
                ),
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_UPDATE_ASSET_DESCRIPTIONS,
                        args={
                            "object_id": 42,
                            "object_type": "oetable",
                            "description_field": "business_description",
                            "description_text": (
                                "Quarterly revenue summary for finance analysts."
                            ),
                            "write_confirmed_by_user": True,
                            "confirmation_token": _GOVERNED_WRITE_CONFIRMATION_TOKEN,
                        },
                        result=post_result,
                    ),
                ],
            ),
            Turn(
                role="assistant",
                content=(
                    "Business description updated on customer_revenue_daily (object_id=42)."
                ),
            ),
        ],
    )


COVERAGE_MCP_USE_GOLDEN_FNS = golden_cases_coverage.COVERAGE_MCP_USE_GOLDEN_FNS
COVERAGE_CONVERSATIONAL_GOLDEN_FNS = golden_cases_coverage.COVERAGE_CONVERSATIONAL_GOLDEN_FNS

for _golden_name in (
    COVERAGE_MCP_USE_GOLDEN_FNS + COVERAGE_CONVERSATIONAL_GOLDEN_FNS
):
    globals()[_golden_name] = getattr(golden_cases_coverage, _golden_name)


def all_mcp_use_golden_fns() -> list[str]:
    """Names of single-turn LLMTestCase goldens for MCPUseMetric."""
    return [
        "golden_mcp_use_catalog_search",
        "golden_mcp_use_prompt_workflow",
        "golden_mcp_use_datastory",
        "golden_mcp_use_organizational_knowledge_prompt",
        "golden_mcp_use_native_source_access",
        "golden_mcp_use_routing_guide_resource",
        "golden_mcp_use_platform_help",
        "golden_mcp_use_catalog_object_access",
        *COVERAGE_MCP_USE_GOLDEN_FNS,
    ]


def all_conversational_golden_fns() -> list[str]:
    """Names of multi-turn ConversationalTestCase goldens."""
    return [
        "golden_task_completion_discovery",
        "golden_multi_turn_lineage_followup",
        "golden_governed_write_confirm_two_step",
        *COVERAGE_CONVERSATIONAL_GOLDEN_FNS,
    ]


_TASK_COMPLETION_GOLDEN = "golden_task_completion_discovery"


def all_multi_turn_mcp_use_golden_fns() -> list[str]:
    """Conversational goldens scored with MultiTurnMCPUseMetric (excludes task-completion)."""
    return [name for name in all_conversational_golden_fns() if name != _TASK_COMPLETION_GOLDEN]


__all__ = [
    "all_conversational_golden_fns",
    "all_mcp_use_golden_fns",
    "all_multi_turn_mcp_use_golden_fns",
    "golden_governed_write_confirm_two_step",
    "golden_mcp_use_catalog_object_access",
    "golden_mcp_use_catalog_search",
    "golden_mcp_use_datastory",
    "golden_mcp_use_native_source_access",
    "golden_mcp_use_organizational_knowledge_prompt",
    "golden_mcp_use_platform_help",
    "golden_mcp_use_routing_guide_resource",
    "golden_mcp_use_prompt_workflow",
    "golden_multi_turn_lineage_followup",
    "golden_task_completion_discovery",
    *COVERAGE_MCP_USE_GOLDEN_FNS,
    *COVERAGE_CONVERSATIONAL_GOLDEN_FNS,
]
