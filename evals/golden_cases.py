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
    TOOL_ACCESS_EXPLORER,
    TOOL_ASSET_DETAILS,
    TOOL_ASSET_EXPLORER,
    TOOL_ASSET_LINEAGE,
    TOOL_KNOWLEDGE_SEARCH,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
)
from server.docs.loader import read_doc_markdown
from server.tools.common.confirm_gate import compute_confirmation_token

_MCP_WORKFLOWS_RESOURCE_URI = AnyUrl(f"{DOCS_RESOURCE_URI_PREFIX}/mcp_workflows")

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
    "Check OvalEdge catalog permissions.\n\n"
    "User: john.doe\n"
    "Object: payroll_fact (oetable)\n\n"
    "Steps:\n"
    "1. Call access_explorer with operation=catalog_access and "
    "query_direction=user_to_object.\n"
    "2. Do not use operation=source_system_access (native DB grants).\n"
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
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_search",
        input="Find certified tables for customer revenue reporting.",
        actual_output=(
            "I used asset_explorer (not knowledge_search or platform docs) because "
            "you asked for certified physical tables. I passed search_terms "
            "['customer', 'revenue'], object_type=oetable, filters.certification="
            "['certified'], and context_query with your full sentence for semantic "
            "ranking. I did not call asset_details yet "
            "because search was the correct first step to discover candidates."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={
                    "search_terms": ["customer", "revenue"],
                    "object_type": "oetable",
                    "context_query": "Find certified tables for customer revenue reporting.",
                    "filters": {"certification": ["certified"]},
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
    srv = ovaledge_eval_mcp_server(tool_names=frozenset({TOOL_ASSET_EXPLORER}))
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
                        name=TOOL_ASSET_EXPLORER,
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
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_LINEAGE}),
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
                        name=TOOL_ASSET_EXPLORER,
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


def golden_multi_turn_explore_details_lineage() -> ConversationalTestCase:
    """Full consolidated read chain: open search → details on a shortlisted id → lineage."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset(
            {TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS, TOOL_ASSET_LINEAGE}
        ),
    )
    return ConversationalTestCase(
        name="multi_turn_explore_details_lineage",
        scenario="Analyst narrows an open catalog question down to one asset and its origin.",
        expected_outcome=(
            "Agent starts with an open asset_explorer search (no object_type), shortlists a "
            "hit, calls asset_details for that id, then asset_lineage for its upstream "
            "sources — never calling details or lineage before an id is known."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(role="user", content="What do we hold on customer churn?"),
            Turn(
                role="assistant",
                content=(
                    "Searching the catalog with search_terms ['customer', 'churn'] and your "
                    "question as context_query. I am leaving object_type unset so reports and "
                    "glossary terms can match too."
                ),
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_ASSET_EXPLORER,
                        args={
                            "search_terms": ["customer", "churn"],
                            "context_query": "What do we hold on customer churn?",
                        },
                        result=tool_call_result(
                            {
                                "total": 2,
                                "items": [
                                    {
                                        "objectId": 900,
                                        "objectType": "oetable",
                                        "objectName": "customer_churn_monthly",
                                    },
                                    {
                                        "objectId": 901,
                                        "objectType": "glossary",
                                        "objectName": "Churn Rate",
                                    },
                                ],
                            }
                        ),
                    ),
                ],
            ),
            Turn(
                role="user",
                content="Tell me more about customer_churn_monthly.",
            ),
            Turn(
                role="assistant",
                content=(
                    "Calling asset_details with object_id=900 and object_type=oetable — the "
                    "id from the search hit you picked."
                ),
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_ASSET_DETAILS,
                        args={"object_id": 900, "object_type": "oetable"},
                        result=tool_call_result(
                            {
                                "details": {
                                    "objectId": 900,
                                    "objectType": "oetable",
                                    "objectName": "customer_churn_monthly",
                                    "steward": "john.smith",
                                    "certificationStatus": "certified",
                                },
                                "profile": {"columns": [{"name": "churn_rate", "nulls": 0}]},
                            }
                        ),
                    ),
                ],
            ),
            Turn(role="user", content="Where does that data come from?"),
            Turn(
                role="assistant",
                content=(
                    "Calling asset_lineage for object_id=900 (oetable) to trace upstream "
                    "sources."
                ),
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_ASSET_LINEAGE,
                        args={"object_id": 900, "object_type": "oetable", "depth": 2},
                        result=tool_call_result(
                            {
                                "objectId": 900,
                                "nodes": [
                                    {"objectId": 880, "objectName": "customer_events"},
                                    {"objectId": 900, "objectName": "customer_churn_monthly"},
                                ],
                                "edges": [{"from": 880, "to": 900}],
                            }
                        ),
                    ),
                ],
            ),
            Turn(
                role="assistant",
                content=(
                    "customer_churn_monthly is certified, stewarded by john.smith, and is "
                    "built upstream from customer_events."
                ),
            ),
        ],
    )


def golden_mcp_use_catalog_filters_only() -> LLMTestCase:
    """Filter-only catalog search: nested filters, no search_terms (POST body)."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_filters_only",
        input="Show certified database views.",
        actual_output=(
            "I called asset_explorer with object_type=oetable and nested filters "
            "certification=['certified'] and tableType=['VIEW']. I omitted search_terms "
            "because you asked to facet the catalog, not to keyword-search. Backend is "
            "POST /api/v1/mcp/asset-explorer. I did not use glossary/tag lookup mode "
            "and did not call access_explorer."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={
                    "object_type": "oetable",
                    "filters": {
                        "certification": ["certified"],
                        "tableType": ["VIEW"],
                    },
                },
                result=tool_call_result(
                    {
                        "total": 1,
                        "items": [
                            {
                                "objectId": 77,
                                "objectType": "oetable",
                                "objectName": "v_customer",
                            }
                        ],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_catalog_dq_range_filter() -> LLMTestCase:
    """Range + parent-table facets go on nested filters (dqIndex, tableName)."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_dq_range_filter",
        input="Which CUSTOMER tables have a data-quality index of at least 80?",
        actual_output=(
            "I called asset_explorer with nested filters tableName=['CUSTOMER'] and "
            "dqIndex={min:80} rather than stuffing those into search_terms. "
            "I omitted max — 'at least 80' is open-ended; I did not invent dqIndex max 100. "
            "Top-level search_terms stay for keywords; extra global-search facets use "
            "filters. I left object_type unset so columns and tables can both match."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={
                    "filters": {
                        "tableName": ["CUSTOMER"],
                        "dqIndex": {"min": 80},
                    },
                },
                result=tool_call_result(
                    {
                        "total": 2,
                        "items": [
                            {
                                "objectId": 11,
                                "objectType": "oetable",
                                "objectName": "CUSTOMER",
                            },
                            {
                                "objectId": 12,
                                "objectType": "oecolumn",
                                "objectName": "CUSTOMER_ID",
                            },
                        ],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_catalog_rating_min_filter() -> LLMTestCase:
    """Open-ended star rating: nested rating.min only for 'at least 4' — do not invent max=5."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_rating_min_filter",
        input="Find tables rated at least 4.",
        actual_output=(
            "I called asset_explorer with object_type=oetable and nested filters "
            "rating={min:4} only. Catalog rating is 1–5 stars and min is inclusive, "
            "so at least 4 is min:4. I did not set max:5 — you did not ask for an "
            "upper bound. I did not put the rating into search_terms."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={
                    "object_type": "oetable",
                    "filters": {"rating": {"min": 4}},
                },
                result=tool_call_result(
                    {
                        "total": 1,
                        "items": [
                            {
                                "objectId": 23592,
                                "objectType": "oetable",
                                "objectName": "Customer",
                            }
                        ],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_catalog_rating_more_than_filter() -> LLMTestCase:
    """Exclusive 'more than 4' uses inclusive min just above 4 — not min:4 and not max:5."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_rating_more_than_filter",
        input="Find tables whose rating is more than 4.",
        actual_output=(
            "I called asset_explorer with object_type=oetable and nested filters "
            "rating={min:4.01} because more than 4 is exclusive and min is inclusive. "
            "I did not use min:4 (that would include 4-star tables). I omitted max "
            "rather than inventing a 5-star ceiling. I did not put the rating into "
            "search_terms."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={
                    "object_type": "oetable",
                    "filters": {"rating": {"min": 4.01}},
                },
                result=tool_call_result(
                    {
                        "total": 1,
                        "items": [
                            {
                                "objectId": 23592,
                                "objectType": "oetable",
                                "objectName": "Customer",
                            }
                        ],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_catalog_popularity_min_filter() -> LLMTestCase:
    """Open-ended popularity: nested popularity.min only — do not invent an upper bound."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_popularity_min_filter",
        input="Find tables with popularity of at least 70.",
        actual_output=(
            "I called asset_explorer with object_type=oetable and nested filters "
            "popularity={min:70} only. I omitted max — at least 70 is open-ended. "
            "I did not put popularity into search_terms."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={
                    "object_type": "oetable",
                    "filters": {"popularity": {"min": 70}},
                },
                result=tool_call_result(
                    {
                        "total": 1,
                        "items": [
                            {
                                "objectId": 88,
                                "objectType": "oetable",
                                "objectName": "orders_fact",
                            }
                        ],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_catalog_created_date_filter() -> LLMTestCase:
    """createdDate uses from/to ISO dates on nested filters, not min/max."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_catalog_created_date_filter",
        input="Find tables created between 2024-01-01 and 2024-12-31.",
        actual_output=(
            "I called asset_explorer with object_type=oetable and nested filters "
            "createdDate={from:2024-01-01, to:2024-12-31}. createdDate uses from/to "
            "ISO dates, not min/max. I did not put the dates into search_terms."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={
                    "object_type": "oetable",
                    "filters": {
                        "createdDate": {"from": "2024-01-01", "to": "2024-12-31"},
                    },
                },
                result=tool_call_result(
                    {
                        "total": 1,
                        "items": [
                            {
                                "objectId": 91,
                                "objectType": "oetable",
                                "objectName": "new_customers",
                            }
                        ],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_open_catalog_search() -> LLMTestCase:
    """Single-turn: a question that names no asset type must not be narrowed to tables."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_open_catalog_search",
        input="What do we have related to payments?",
        actual_output=(
            "I called asset_explorer with search_terms ['payment'] and context_query set to "
            "your full question. I deliberately left object_type unset because you did not "
            "ask for one kind of asset — narrowing to oetable would have hidden the reports, "
            "columns and glossary terms that matched. The results span several object types, "
            "so I am presenting them grouped by objectType rather than as a flat table list."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={
                    "search_terms": ["payment"],
                    "context_query": "What do we have related to payments?",
                },
                result=tool_call_result(
                    {
                        "total": 4,
                        "items": [
                            {
                                "objectId": 501,
                                "objectType": "oetable",
                                "objectName": "payment_fact",
                            },
                            {
                                "objectId": 502,
                                "objectType": "oecolumn",
                                "objectName": "payment_method",
                            },
                            {
                                "objectId": 503,
                                "objectType": "oechart",
                                "objectName": "Payments Dashboard",
                            },
                            {
                                "objectId": 504,
                                "objectType": "glossary",
                                "objectName": "Payment Terms",
                            },
                        ],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_asset_details_after_shortlist() -> LLMTestCase:
    """Single-turn: asset_details is called only for a shortlisted id, never to discover."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_DETAILS}),
    )
    return LLMTestCase(
        name="mcp_use_asset_details_after_shortlist",
        input="Tell me everything about the payment_fact table.",
        actual_output=(
            "I first called asset_explorer to resolve the name 'payment_fact' to a catalog "
            "id, because asset_details needs object_id plus object_type and does not accept "
            "a fully qualified name. With object_id=501 shortlisted I called asset_details, "
            "which returned the governance metadata plus the column profile and table "
            "relationships. I did not call asset_details before the search — there was no id "
            "to call it with."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={"search_terms": ["payment_fact"], "object_type": "oetable"},
                result=tool_call_result(
                    {
                        "total": 1,
                        "items": [
                            {
                                "objectId": 501,
                                "objectType": "oetable",
                                "objectName": "payment_fact",
                            }
                        ],
                    }
                ),
            ),
            MCPToolCall(
                name=TOOL_ASSET_DETAILS,
                args={"object_id": 501, "object_type": "oetable"},
                result=tool_call_result(
                    {
                        "details": {
                            "objectId": 501,
                            "objectType": "oetable",
                            "objectName": "payment_fact",
                            "owner": "jane.doe",
                            "certificationStatus": "certified",
                        },
                        "profile": {"columns": [{"name": "amount", "nulls": 0}]},
                        "relationships": [{"from": "payment_fact", "to": "customer", "type": "FK"}],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_knowledge_not_catalog_for_policy() -> LLMTestCase:
    """Single-turn: a policy question routes to knowledge_search, never to catalog search."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_KNOWLEDGE_SEARCH}),
    )
    return LLMTestCase(
        name="mcp_use_knowledge_not_catalog_for_policy",
        input="What is our retention policy for customer PII?",
        actual_output=(
            "This asks for an organizational policy, not for physical datasets, so I called "
            "knowledge_search — it covers both our data stories and OvalEdge product "
            "documentation. I did not call asset_explorer: catalog search returns table and "
            "column metadata, which cannot answer what our retention policy says. I led the "
            "answer with the storyCitation verbatim so the source is attributable."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_KNOWLEDGE_SEARCH,
                args={"query": "What is our retention policy for customer PII?"},
                result=tool_call_result(
                    {
                        "dataStories": {
                            "metadata": {"storyName": "PII Retention Policy"},
                            "storyCitation": "Source: PII Retention Policy (Governance)",
                            "content": {
                                "story": "Customer PII is retained for 7 years after closure."
                            },
                        }
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_prompt_workflow() -> LLMTestCase:
    """Agent fetched the packaged discovery prompt then searched."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER}),
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
                name=TOOL_ASSET_EXPLORER,
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
    srv = ovaledge_eval_mcp_server(tool_names=frozenset({TOOL_KNOWLEDGE_SEARCH}))
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
                name=TOOL_KNOWLEDGE_SEARCH,
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
        tool_names=frozenset({TOOL_KNOWLEDGE_SEARCH}),
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
                name=TOOL_KNOWLEDGE_SEARCH,
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
    """Single-turn: native Redshift grants via access_explorer source_system_access."""
    srv = ovaledge_eval_mcp_server(tool_names=frozenset({TOOL_ACCESS_EXPLORER}))
    return LLMTestCase(
        name="mcp_use_native_source_access",
        input="What tables can svc_analytics query in Redshift?",
        actual_output=(
            "This asks for native database grants (not OvalEdge catalog permissions), so I used "
            "access_explorer with operation=source_system_access, source_system=redshift, "
            "query_direction=user_to_objects, username=svc_analytics, "
            "object_path=prod, object_type=database, and connection_id for the Redshift "
            "connector. I did not use asset_explorer, which indexes governance metadata "
            "rather than Redshift privilege tables."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ACCESS_EXPLORER,
                args={
                    "operation": "source_system_access",
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


def golden_mcp_use_first_person_catalog_inventory() -> LLMTestCase:
    """Generic first-person see/access inventory → asset_explorer, not access_explorer."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER}),
        prompt_names=frozenset({"data_discovery"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        "Help me find data for: 'What tables can I see?'\n\n"
                        "Please follow this sequence:\n"
                        "1. Extract search keywords from the query\n"
                        "2. Call asset_explorer with search_terms and context_query\n"
                    ),
                ),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_first_person_catalog_inventory",
        input="What tables can I see?",
        actual_output=(
            "This is first-person catalog inventory without a named principal or source, "
            "so I used data_discovery / asset_explorer — not access_explorer (which is for "
            "named-principal grants or who-has-access). I searched the catalog with "
            "search_terms and context_query set to your question."
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
                name=TOOL_ASSET_EXPLORER,
                args={
                    "search_terms": ["tables"],
                    "context_query": "What tables can I see?",
                },
                result=tool_call_result(
                    {
                        "total": 2,
                        "items": [
                            {
                                "objectId": 101,
                                "objectType": "oetable",
                                "objectName": "orders",
                            },
                            {
                                "objectId": 102,
                                "objectType": "oetable",
                                "objectName": "customers",
                            },
                        ],
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_routing_guide_resource() -> LLMTestCase:
    """Agent reads mcp_workflows resource before native source access (RDAM routing)."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ACCESS_EXPLORER}),
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
            "access_explorer with operation=source_system_access, "
            "query_direction=object_to_users, source_system=snowflake, "
            "object_path=prod_db.public.orders, and object_type=table. I did not use "
            "asset_explorer or catalog_access — native grants are RDAM-only."
        ),
        mcp_servers=[srv],
        mcp_resources_called=[
            MCPResourceCall(uri=_MCP_WORKFLOWS_RESOURCE_URI, result=resource_result),
        ],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ACCESS_EXPLORER,
                args={
                    "operation": "source_system_access",
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
        tool_names=frozenset({TOOL_KNOWLEDGE_SEARCH}),
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
                name=TOOL_KNOWLEDGE_SEARCH,
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
    """Single-turn: catalog_object_access prompt → access_explorer catalog_access."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ACCESS_EXPLORER, TOOL_ASSET_EXPLORER}),
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
            "Catalog permissions checks use access_explorer with operation=catalog_access, "
            "query_direction=user_to_object, username=john.doe, object_id=101, "
            "object_type=oetable. I did not call operation=source_system_access because "
            "that returns native database grants, not OvalEdge catalog permissions."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[
            MCPPromptCall(name="catalog_object_access", result=prompt_result),
        ],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ACCESS_EXPLORER,
                args={
                    "operation": "catalog_access",
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
            TOOL_ASSET_EXPLORER,
            TOOL_ASSET_DETAILS,
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
                        name=TOOL_ASSET_EXPLORER,
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
        "golden_mcp_use_catalog_filters_only",
        "golden_mcp_use_catalog_dq_range_filter",
        "golden_mcp_use_catalog_rating_min_filter",
        "golden_mcp_use_catalog_rating_more_than_filter",
        "golden_mcp_use_catalog_popularity_min_filter",
        "golden_mcp_use_catalog_created_date_filter",
        "golden_mcp_use_open_catalog_search",
        "golden_mcp_use_asset_details_after_shortlist",
        "golden_mcp_use_knowledge_not_catalog_for_policy",
        "golden_mcp_use_prompt_workflow",
        "golden_mcp_use_datastory",
        "golden_mcp_use_organizational_knowledge_prompt",
        "golden_mcp_use_native_source_access",
        "golden_mcp_use_first_person_catalog_inventory",
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
        "golden_multi_turn_explore_details_lineage",
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
    "golden_mcp_use_asset_details_after_shortlist",
    "golden_mcp_use_catalog_dq_range_filter",
    "golden_mcp_use_catalog_rating_min_filter",
    "golden_mcp_use_catalog_rating_more_than_filter",
    "golden_mcp_use_catalog_popularity_min_filter",
    "golden_mcp_use_catalog_created_date_filter",
    "golden_mcp_use_catalog_filters_only",
    "golden_mcp_use_catalog_object_access",
    "golden_mcp_use_catalog_search",
    "golden_mcp_use_datastory",
    "golden_mcp_use_knowledge_not_catalog_for_policy",
    "golden_mcp_use_native_source_access",
    "golden_mcp_use_first_person_catalog_inventory",
    "golden_mcp_use_open_catalog_search",
    "golden_mcp_use_organizational_knowledge_prompt",
    "golden_mcp_use_platform_help",
    "golden_mcp_use_routing_guide_resource",
    "golden_mcp_use_prompt_workflow",
    "golden_multi_turn_explore_details_lineage",
    "golden_multi_turn_lineage_followup",
    "golden_task_completion_discovery",
    *COVERAGE_MCP_USE_GOLDEN_FNS,
    *COVERAGE_CONVERSATIONAL_GOLDEN_FNS,
]
