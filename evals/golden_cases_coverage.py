"""Additional eval goldens so every MCP tool appears in at least one golden case."""

from __future__ import annotations

from deepeval.test_case import (
    ConversationalTestCase,
    LLMTestCase,
    MCPPromptCall,
    MCPToolCall,
    Turn,
)
from mcp.types import GetPromptResult, PromptMessage, TextContent

from evals.mcp_eval_helpers import ovaledge_eval_mcp_server, tool_call_result
from server.constants import (
    MCP_DQ_ASSESS_LIMIT_DEFAULT,
    TOOL_ACCESS_EXPLORER,
    TOOL_ASSET_DETAILS,
    TOOL_ASSET_EXPLORER,
    TOOL_CREATE_GLOSSARY_TERM,
    TOOL_CREATE_SERVICE_REQUEST,
    TOOL_CREATE_TAG,
    TOOL_DQ_RULE_ADVISOR,
    TOOL_DQ_RULE_MANAGER,
    TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
    TOOL_UPDATE_CDE_ASSOCIATIONS,
    TOOL_UPDATE_CUSTOM_FIELD_VALUE,
    TOOL_UPDATE_GOVERNANCE_ROLES,
)
from server.tools.common.confirm_gate import compute_confirmation_token

_TRUST_ASSESSMENT_PROMPT_TEXT = (
    "Assess trust in a certified table.\n\n"
    "Table: customer_revenue_daily\n\n"
    "Steps:\n"
    "1. asset_explorer to resolve object_id.\n"
    "2. asset_details for governance metadata.\n"
    "3. asset_details for data quality signals.\n"
    "4. Do not use knowledge_search for physical table trust."
)

_EXPLAIN_TERM_PROMPT_TEXT = (
    "Explain a business glossary term.\n\n"
    "Term: Revenue Recognition\n\n"
    "Call asset_explorer with name and object_type=glossary."
)

_EXPLAIN_TAG_PROMPT_TEXT = (
    "Explain a governance tag.\n\n"
    "Tag: PII\n\n"
    "Call asset_explorer with name and object_type=oetag."
)

_EXPLAIN_DQ_RULE_PROMPT_TEXT = (
    "Explain a data quality rule.\n\n"
    "Rule: Null Data Density Check\n\n"
    "Call dq_rule_advisor step=lookup with rule_name."
)

_METADATA_DRIFT_PROMPT_TEXT = (
    "Summarize metadata drift.\n\n"
    "Question: What changed in CUSTOMER schema after the latest crawl?\n\n"
    "Call metadata_changes_between_crawls."
)

_FIND_RELATED_PROMPT_TEXT = (
    "Find related catalog assets.\n\n"
    "Table: orders_fact (object_id=88)\n\n"
    "Call asset_details, then asset_details for context."
)

_CREATE_GLOSSARY_PROMPT_TEXT = (
    "Create a glossary term with human confirmation.\n\n"
    "Term: Revenue Recognition, domain_id=12, description=ASC 606 policy.\n"
    "Preview with write_confirmed_by_user=false, then confirm with confirmation_token."
)

_CREATE_TAG_PROMPT_TEXT = (
    "Create a governance tag with human confirmation.\n\n"
    "Tag: Logistics (open mode, no parent).\n"
    "Complete parent step, preview, then confirm with confirmation_token."
)

_ASSIGN_ROLES_PROMPT_TEXT = (
    "Assign governance roles with human confirmation.\n\n"
    "Table id 99: Owner=mike, Steward=john.\n"
    "Preview update_governance_roles, then confirm with confirmation_token."
)

_ASSESS_CDE_DQ_PROMPT_TEXT = (
    "Assess CDE DQ coverage.\n\n"
    "Steps:\n"
    "1. dq_rule_advisor step=assess for CDE columns on target tables.\n"
    "2. dq_rule_advisor step=lookup for matching rules.\n"
    "3. dq_rule_manager step=associate or step=create_standard with confirm gate "
    "(preview, then write_confirmed_by_user=true + confirmation_token)."
)

_CUSTOM_SQL_DQ_PROMPT_TEXT = (
    "Custom SQL DQ workflow for CDE column.\n\n"
    "Steps:\n"
    "1. dq_rule_advisor step=generate_query for the column (custom_sql path)\n"
    "2. dq_rule_advisor step=validate_query with confirm gate "
    "using connection_id/schema_id from context\n"
    "3. dq_rule_manager step=create_custom_sql with confirm gate when canCreateRule is true"
)

_GLOSSARY_CREATE_POST_BODY: dict[str, object] = {
    "termName": "Revenue Recognition",
    "domainId": 12,
    "description": "ASC 606 revenue recognition policy.",
    "category1Id": 0,
    "category2Id": 0,
    "publish": False,
}
_GLOSSARY_CREATE_TOKEN = compute_confirmation_token(_GLOSSARY_CREATE_POST_BODY)

_TAG_CREATE_POST_BODY: dict[str, object] = {
    "tagName": "Logistics",
    "description": "<p>Logistics</p>",
}
_TAG_CREATE_TOKEN = compute_confirmation_token(_TAG_CREATE_POST_BODY)

_SERVICE_REQUEST_POST_BODY: dict[str, object] = {
    "ticketTemplateId": 1005,
    "summary": "Need access to tickettemplate",
    "objectId": 3337,
    "objectType": "oetable",
}
_SERVICE_REQUEST_TOKEN = compute_confirmation_token(_SERVICE_REQUEST_POST_BODY)

_CREATE_SERVICE_REQUEST_PROMPT_TEXT = (
    "Create a service request with human confirmation.\n\n"
    "Intent: access on tickettemplate table.\n"
    "Resolve the table, look up the template, preview, then confirm with confirmation_token."
)

_ROLES_POST_BODY: dict[str, object] = {
    "target": {"objectId": 99, "objectType": "oetable"},
    "roleUpdates": {"owner": "mike", "steward": "john"},
    "clientContext": {
        "prompt": "Assign John as Steward and Mike as Owner",
        "reason": "Ownership update",
    },
}
_ROLES_CONFIRM_TOKEN = compute_confirmation_token(_ROLES_POST_BODY)

_CDE_POST_BODY: dict[str, object] = {
    "targets": [{"objectId": 3337, "objectType": "oeschema"}],
    "action": "Yes",
    "cdeJustification": "Critical data element for finance reporting",
}
_CDE_CONFIRM_TOKEN = compute_confirmation_token(_CDE_POST_BODY)

_CUSTOM_FIELD_POST_BODY: dict[str, object] = {
    "target": {"objectId": 99, "objectType": "oetable"},
    "fieldUpdates": [{"fieldName": "Data Owner", "value": "John Smith"}],
    "clientContext": {"prompt": "Update Data Owner to John Smith"},
}
_CUSTOM_FIELD_CONFIRM_TOKEN = compute_confirmation_token(_CUSTOM_FIELD_POST_BODY)

_ASSOCIATE_DQ_POST_BODY: dict[str, object] = {
    "dqruleId": 42,
    "skipAlreadyAssociated": True,
    "objects": [{"objectId": 101, "objectType": "oecolumn"}],
}
_ASSOCIATE_DQ_CONFIRM_TOKEN = compute_confirmation_token(_ASSOCIATE_DQ_POST_BODY)

_CREATE_DQ_POST_BODY: dict[str, object] = {
    "discoverCdeColumns": True,
    "preferExistingRule": True,
    "skipDuplicateFunctionOnObject": True,
    "limit": MCP_DQ_ASSESS_LIMIT_DEFAULT,
}
_CREATE_DQ_CONFIRM_TOKEN = compute_confirmation_token(_CREATE_DQ_POST_BODY)

_VALIDATE_DQ_QUERIES_POST_BODY: dict[str, object] = {
    "connectionId": 1,
    "schemaId": 2,
    "ruleQuery": "SELECT COUNT(*) FROM sales.revenue WHERE amount IS NULL",
    "statsQuery": "SELECT COUNT(*) FROM sales.revenue",
    "failedValuesQuery": (
        "SELECT amount FROM sales.revenue WHERE amount IS NULL LIMIT 1"
    ),
}
_VALIDATE_DQ_QUERIES_CONFIRM_TOKEN = compute_confirmation_token(
    _VALIDATE_DQ_QUERIES_POST_BODY
)

_CREATE_SQL_DQ_RULE_POST_BODY: dict[str, object] = {
    "objectId": 101,
    "objectType": "oecolumn",
    "ruleName": "revenue_null_check",
    "ruleQuery": "SELECT COUNT(*) FROM sales.revenue WHERE amount IS NULL",
    "statsQuery": "SELECT COUNT(*) FROM sales.revenue",
    "failedValuesQuery": (
        "SELECT amount FROM sales.revenue WHERE amount IS NULL LIMIT 1"
    ),
    "connectionId": 1,
    "schemaId": 2,
}
_CREATE_SQL_DQ_RULE_CONFIRM_TOKEN = compute_confirmation_token(
    _CREATE_SQL_DQ_RULE_POST_BODY
)


def golden_mcp_use_trust_assessment() -> LLMTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({
            TOOL_ASSET_EXPLORER,
            TOOL_ASSET_DETAILS,
            TOOL_ASSET_DETAILS,
        }),
        prompt_names=frozenset({"trust_assessment"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_TRUST_ASSESSMENT_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_trust_assessment",
        input="How trustworthy is customer_revenue_daily for executive reporting?",
        actual_output=(
            "Per trust_assessment I resolved the table via asset_explorer, loaded "
            "governance metadata with asset_details, then asset_details "
            "for column-level stats. I did not use knowledge_search because this is physical "
            "catalog trust, not organizational narrative."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[MCPPromptCall(name="trust_assessment", result=prompt_result)],
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
                            {"objectId": 42, "name": "customer_revenue_daily"},
                        ],
                    }
                ),
            ),
            MCPToolCall(
                name=TOOL_ASSET_DETAILS,
                args={"object_id": 42, "object_type": "oetable"},
                result=tool_call_result(
                    {
                        "objectId": 42,
                        "name": "customer_revenue_daily",
                        "certified": True,
                        "steward": "finance-team",
                    }
                ),
            ),
            MCPToolCall(
                name=TOOL_ASSET_DETAILS,
                args={"object_id": 42, "object_type": "oetable"},
                result=tool_call_result(
                    {"columns": [{"name": "revenue_amt", "nullPct": 0.01}]}
                ),
            ),
        ],
    )


def golden_mcp_use_explain_business_term() -> LLMTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER}),
        prompt_names=frozenset({"explain_business_term"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_EXPLAIN_TERM_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_explain_business_term",
        input="What does Revenue Recognition mean in our glossary?",
        actual_output=(
            "I called asset_explorer with name='Revenue Recognition' and "
            "object_type=glossary per the explain_business_term workflow."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[
            MCPPromptCall(name="explain_business_term", result=prompt_result),
        ],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={"name": "Revenue Recognition", "object_type": "glossary"},
                result=tool_call_result(
                    {
                        "termName": "Revenue Recognition",
                        "definition": "ASC 606 five-step revenue model.",
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_explain_tag() -> LLMTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_ASSET_EXPLORER}),
        prompt_names=frozenset({"explain_tag"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_EXPLAIN_TAG_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_explain_tag",
        input="What is our PII tag used for?",
        actual_output=(
            "I used asset_explorer with name='PII' and object_type=oetag as directed "
            "by explain_tag."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[MCPPromptCall(name="explain_tag", result=prompt_result)],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={"name": "PII", "object_type": "oetag"},
                result=tool_call_result(
                    {"tagName": "PII", "description": "Personally identifiable information"}
                ),
            ),
        ],
    )


def golden_mcp_use_explain_dq_rule() -> LLMTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_DQ_RULE_ADVISOR, TOOL_UPDATE_GOVERNANCE_ROLES}),
        prompt_names=frozenset({"explain_dq_rule"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_EXPLAIN_DQ_RULE_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_explain_dq_rule",
        input="Explain our Null Data Density Check DQ rule.",
        actual_output=(
            "I called dq_rule_advisor step=lookup with "
            "rule_name='Null Data Density Check'. I did not "
            "POST update_governance_roles because the user asked for an explanation only."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[MCPPromptCall(name="explain_dq_rule", result=prompt_result)],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_DQ_RULE_ADVISOR,
                args={"step": "lookup", "rule_name": "Null Data Density Check"},
                result=tool_call_result(
                    {
                        "objectId": 42,
                        "objectName": "Null Data Density Check",
                        "objectType": "dqrule",
                    }
                ),
            ),
        ],
    )


def golden_mcp_use_metadata_drift() -> LLMTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({
            TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
            TOOL_ASSET_EXPLORER,
        }),
        prompt_names=frozenset({"metadata_drift"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_METADATA_DRIFT_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_metadata_drift",
        input="What changed in CUSTOMER schema after the latest crawl?",
        actual_output=(
            "I called metadata_changes_between_crawls with schema_names=['CUSTOMER'] per "
            "the metadata_drift workflow."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[MCPPromptCall(name="metadata_drift", result=prompt_result)],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
                args={
                    "question": "What changed in CUSTOMER schema after the latest crawl?",
                    "schema_names": ["CUSTOMER"],
                },
                result=tool_call_result(
                    {"ok": True, "data": {"changeSummary": "2 tables added"}},
                ),
            ),
        ],
    )


def golden_mcp_use_find_related_assets() -> LLMTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({
            TOOL_ASSET_DETAILS,
            TOOL_ASSET_DETAILS,
            TOOL_ASSET_EXPLORER,
        }),
        prompt_names=frozenset({"find_related_assets"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_FIND_RELATED_PROMPT_TEXT),
            )
        ],
    )
    return LLMTestCase(
        name="mcp_use_find_related_assets",
        input="What assets are related to orders_fact?",
        actual_output=(
            "Per find_related_assets I called asset_details for graph edges, "
            "then asset_details for related object metadata."
        ),
        mcp_servers=[srv],
        mcp_prompts_called=[
            MCPPromptCall(name="find_related_assets", result=prompt_result),
        ],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_DETAILS,
                args={"object_id": 88},
                result=tool_call_result(
                    {
                        "relationships": [
                            {"relatedObjectId": 90, "name": "customers_dim"},
                        ],
                    }
                ),
            ),
            MCPToolCall(
                name=TOOL_ASSET_DETAILS,
                args={"object_id": 90, "object_type": "oetable"},
                result=tool_call_result(
                    {"objectId": 90, "name": "customers_dim", "objectType": "oetable"},
                ),
            ),
        ],
    )


def golden_governed_glossary_create_two_step() -> ConversationalTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_CREATE_GLOSSARY_TERM}),
        prompt_names=frozenset({"create_business_glossary_term"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_CREATE_GLOSSARY_PROMPT_TEXT),
            )
        ],
    )
    preview = tool_call_result(
        {
            "workflowPhase": "confirm_create",
            "doNotCreate": True,
            "confirmationToken": _GLOSSARY_CREATE_TOKEN,
            "formattedResponse": "**Confirm glossary term creation**",
        }
    )
    post = tool_call_result(
        {
            "ok": True,
            "data": {"businessGlossaryId": 1001, "termName": "Revenue Recognition"},
        }
    )
    return ConversationalTestCase(
        name="governed_glossary_create_two_step",
        scenario="User creates a glossary term with explicit confirmation.",
        expected_outcome=(
            "Preview create_glossary_term without POST, then confirm with matching token."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(
                role="user",
                content="Create glossary term Revenue Recognition under domain 12.",
            ),
            Turn(
                role="assistant",
                content="Loading create_business_glossary_term workflow.",
                mcp_prompts_called=[
                    MCPPromptCall(name="create_business_glossary_term", result=prompt_result),
                ],
            ),
            Turn(
                role="assistant",
                content="Preview only — doNotCreate=true, showing confirmationToken.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_CREATE_GLOSSARY_TERM,
                        args={
                            "term_name": "Revenue Recognition",
                            "domain_id": 12,
                            "description": "ASC 606 revenue recognition policy.",
                            "skip_category": True,
                            "category_skip_confirmed": True,
                            "write_confirmed_by_user": False,
                        },
                        result=preview,
                    ),
                ],
            ),
            Turn(role="user", content="Yes, create it."),
            Turn(
                role="assistant",
                content="POSTing with write_confirmed_by_user=true and preview token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_CREATE_GLOSSARY_TERM,
                        args={
                            "term_name": "Revenue Recognition",
                            "domain_id": 12,
                            "description": "ASC 606 revenue recognition policy.",
                            "skip_category": True,
                            "category_skip_confirmed": True,
                            "write_confirmed_by_user": True,
                            "confirmation_token": _GLOSSARY_CREATE_TOKEN,
                        },
                        result=post,
                    ),
                ],
            ),
            Turn(role="assistant", content="Glossary term Revenue Recognition created."),
        ],
    )


def golden_governed_tag_create_two_step() -> ConversationalTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_CREATE_TAG}),
        prompt_names=frozenset({"create_governance_tag"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_CREATE_TAG_PROMPT_TEXT),
            )
        ],
    )
    preview = tool_call_result(
        {
            "workflowPhase": "confirm_create",
            "doNotCreateTag": True,
            "confirmationToken": _TAG_CREATE_TOKEN,
            "formattedResponse": "**Confirm tag creation**",
        }
    )
    post = tool_call_result(
        {"ok": True, "data": {"tagId": 77, "tagName": "Logistics"}},
    )
    return ConversationalTestCase(
        name="governed_tag_create_two_step",
        scenario="User creates an open-mode tag with explicit confirmation.",
        expected_outcome="Preview create_tag, then POST with matching confirmation_token.",
        mcp_servers=[srv],
        turns=[
            Turn(role="user", content="Create tag Logistics with no parent."),
            Turn(
                role="assistant",
                content="Using create_governance_tag workflow; parent step completed.",
                mcp_prompts_called=[
                    MCPPromptCall(name="create_governance_tag", result=prompt_result),
                ],
            ),
            Turn(
                role="assistant",
                content="Preview create_tag — waiting for user approval.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_CREATE_TAG,
                        args={
                            "tag_name": "Logistics",
                            "create_directly_under_master": True,
                            "parent_step_completed_by_user": True,
                            "write_confirmed_by_user": False,
                        },
                        result=preview,
                    ),
                ],
            ),
            Turn(role="user", content="Confirm."),
            Turn(
                role="assistant",
                content="POSTing tag with bound confirmation_token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_CREATE_TAG,
                        args={
                            "tag_name": "Logistics",
                            "create_directly_under_master": True,
                            "parent_step_completed_by_user": True,
                            "write_confirmed_by_user": True,
                            "confirmation_token": _TAG_CREATE_TOKEN,
                        },
                        result=post,
                    ),
                ],
            ),
            Turn(role="assistant", content="Tag Logistics created."),
        ],
    )


def golden_governed_service_request_create_two_step() -> ConversationalTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_ASSET_EXPLORER, TOOL_CREATE_SERVICE_REQUEST}),
        prompt_names=frozenset({"create_service_desk_request"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_CREATE_SERVICE_REQUEST_PROMPT_TEXT),
            )
        ],
    )
    lookup = tool_call_result(
        {
            "workflowPhase": "collect_fields",
            "formattedResponse": "**Service request template**",
            "data": {"ticketTemplateId": 1005, "ticketTemplateName": "Table Access"},
        }
    )
    preview = tool_call_result(
        {
            "workflowPhase": "confirm_create",
            "doNotCreate": True,
            "confirmationToken": _SERVICE_REQUEST_TOKEN,
            "formattedResponse": "**Confirm service request creation**",
        }
    )
    post = tool_call_result(
        {"ok": True, "data": {"ticketId": 88, "displayTicketId": "SR-88"}},
    )
    return ConversationalTestCase(
        name="governed_service_request_create_two_step",
        scenario="User requests table access; agent files a service request after confirmation.",
        expected_outcome=(
            "Resolve the table, look up the template, preview create_service_request, "
            "then POST with matching confirmation_token."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(role="user", content="I want access to Loan_Data table"),
            Turn(
                role="assistant",
                content="Using create_service_desk_request workflow.",
                mcp_prompts_called=[
                    MCPPromptCall(name="create_service_desk_request", result=prompt_result),
                ],
            ),
            Turn(
                role="assistant",
                content="Resolving Loan_Data via asset_explorer.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_ASSET_EXPLORER,
                        args={"search_terms": ["Loan_Data"], "object_type": "oetable"},
                        result=tool_call_result(
                            {
                                "total": 1,
                                "results": [
                                    {
                                        "objectId": 3337,
                                        "name": "Loan_Data",
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
                content="Looking up the Published and Active access template.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_CREATE_SERVICE_REQUEST,
                        args={
                            "request_type": "access",
                            "object_type": "oetable",
                            "object_id": 3337,
                        },
                        result=lookup,
                    ),
                ],
            ),
            Turn(
                role="assistant",
                content="Preview create_service_request — waiting for user approval.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_CREATE_SERVICE_REQUEST,
                        args={
                            "ticket_template_id": 1005,
                            "summary": "Need access to tickettemplate",
                            "object_id": 3337,
                            "object_type": "oetable",
                            "write_confirmed_by_user": False,
                        },
                        result=preview,
                    ),
                ],
            ),
            Turn(role="user", content="Confirm."),
            Turn(
                role="assistant",
                content="POSTing service request with bound confirmation_token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_CREATE_SERVICE_REQUEST,
                        args={
                            "ticket_template_id": 1005,
                            "summary": "Need access to tickettemplate",
                            "object_id": 3337,
                            "object_type": "oetable",
                            "write_confirmed_by_user": True,
                            "confirmation_token": _SERVICE_REQUEST_TOKEN,
                        },
                        result=post,
                    ),
                ],
            ),
            Turn(role="assistant", content="Service request SR-88 created."),
        ],
    )


def golden_mcp_use_request_access_not_access_explorer() -> LLMTestCase:
    """First-person access request files a ticket; it does not query grants."""
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset(
            {TOOL_ASSET_EXPLORER, TOOL_ACCESS_EXPLORER, TOOL_CREATE_SERVICE_REQUEST}
        ),
    )
    return LLMTestCase(
        name="mcp_use_request_access_not_access_explorer",
        input="I want access to Loan_Data table",
        actual_output=(
            "This is a request to obtain access, not a who-has-access question. "
            "I resolved Loan_Data with asset_explorer and called create_service_request "
            "to look up the access template. I did not call access_explorer."
        ),
        mcp_servers=[srv],
        mcp_tools_called=[
            MCPToolCall(
                name=TOOL_ASSET_EXPLORER,
                args={"search_terms": ["Loan_Data"], "object_type": "oetable"},
                result=tool_call_result(
                    {
                        "total": 1,
                        "results": [
                            {
                                "objectId": 3337,
                                "name": "Loan_Data",
                                "objectType": "oetable",
                            }
                        ],
                    }
                ),
            ),
            MCPToolCall(
                name=TOOL_CREATE_SERVICE_REQUEST,
                args={
                    "request_type": "access",
                    "object_type": "oetable",
                    "object_id": 3337,
                },
                result=tool_call_result(
                    {
                        "workflowPhase": "collect_fields",
                        "formattedResponse": "**Service request template**",
                    }
                ),
            ),
        ],
    )


def golden_governed_roles_confirm_two_step() -> ConversationalTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_UPDATE_GOVERNANCE_ROLES}),
        prompt_names=frozenset({"assign_governance_roles"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_ASSIGN_ROLES_PROMPT_TEXT),
            )
        ],
    )
    preview = tool_call_result(
        {
            "workflowPhase": "confirm_update",
            "doNotUpdate": True,
            "confirmationToken": _ROLES_CONFIRM_TOKEN,
            "formattedResponse": "**Confirm role updates**",
        }
    )
    post = tool_call_result(
        {"status": "success", "updatedRoles": ["owner", "steward"]},
    )
    return ConversationalTestCase(
        name="governed_roles_confirm_two_step",
        scenario="User assigns Owner and Steward with confirmation gate.",
        expected_outcome=(
            "Preview update_governance_roles, then confirm with matching token."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(
                role="user",
                content="Set Owner to mike and Steward to john on table 99.",
            ),
            Turn(
                role="assistant",
                content="Loading assign_governance_roles workflow.",
                mcp_prompts_called=[
                    MCPPromptCall(name="assign_governance_roles", result=prompt_result),
                ],
            ),
            Turn(
                role="assistant",
                content="Preview role update — no POST yet.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_UPDATE_GOVERNANCE_ROLES,
                        args={
                            "object_id": 99,
                            "object_type": "oetable",
                            "role_updates": {"Owner": "mike", "Steward": "john"},
                            "prompt": "Assign John as Steward and Mike as Owner",
                            "reason": "Ownership update",
                            "write_confirmed_by_user": False,
                        },
                        result=preview,
                    ),
                ],
            ),
            Turn(role="user", content="Approved."),
            Turn(
                role="assistant",
                content="POSTing roles with confirmation_token from preview.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_UPDATE_GOVERNANCE_ROLES,
                        args={
                            "object_id": 99,
                            "object_type": "oetable",
                            "role_updates": {"Owner": "mike", "Steward": "john"},
                            "prompt": "Assign John as Steward and Mike as Owner",
                            "reason": "Ownership update",
                            "write_confirmed_by_user": True,
                            "confirmation_token": _ROLES_CONFIRM_TOKEN,
                        },
                        result=post,
                    ),
                ],
            ),
            Turn(role="assistant", content="Governance roles updated on table 99."),
        ],
    )


def golden_governed_cde_confirm_two_step() -> ConversationalTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_UPDATE_CDE_ASSOCIATIONS}),
    )
    preview = tool_call_result(
        {
            "workflowPhase": "confirm_update",
            "doNotUpdate": True,
            "confirmationToken": _CDE_CONFIRM_TOKEN,
            "formattedResponse": "**Confirm CDE update**",
        }
    )
    post = tool_call_result({"status": "success"})
    return ConversationalTestCase(
        name="governed_cde_confirm_two_step",
        scenario="User marks a schema as CDE with justification and confirms.",
        expected_outcome=(
            "Preview update_cde_associations, then POST with matching confirmation_token."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(
                role="user",
                content="Mark schema 3337 as a CDE with justification for finance reporting.",
            ),
            Turn(
                role="assistant",
                content="Preview CDE association update.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_UPDATE_CDE_ASSOCIATIONS,
                        args={
                            "targets": [
                                {"object_id": 3337, "object_type": "oeschema"},
                            ],
                            "action": "Yes",
                            "cde_justification": (
                                "Critical data element for finance reporting"
                            ),
                            "write_confirmed_by_user": False,
                        },
                        result=preview,
                    ),
                ],
            ),
            Turn(role="user", content="Yes, apply."),
            Turn(
                role="assistant",
                content="POSTing CDE update with preview token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_UPDATE_CDE_ASSOCIATIONS,
                        args={
                            "targets": [
                                {"object_id": 3337, "object_type": "oeschema"},
                            ],
                            "action": "Yes",
                            "cde_justification": (
                                "Critical data element for finance reporting"
                            ),
                            "write_confirmed_by_user": True,
                            "confirmation_token": _CDE_CONFIRM_TOKEN,
                        },
                        result=post,
                    ),
                ],
            ),
            Turn(role="assistant", content="CDE association updated."),
        ],
    )


def golden_governed_custom_field_confirm_two_step() -> ConversationalTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({TOOL_UPDATE_CUSTOM_FIELD_VALUE}),
    )
    preview = tool_call_result(
        {
            "workflowPhase": "confirm_update",
            "doNotUpdate": True,
            "confirmationToken": _CUSTOM_FIELD_CONFIRM_TOKEN,
            "formattedResponse": "**Confirm custom field update**",
        }
    )
    post = tool_call_result(
        {"status": "success", "updatedFields": ["Data Owner"]},
    )
    return ConversationalTestCase(
        name="governed_custom_field_confirm_two_step",
        scenario="User updates a custom field value with confirmation.",
        expected_outcome=(
            "Preview update_custom_field_value, then POST with matching token."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(
                role="user",
                content="Set Data Owner to John Smith on table 99.",
            ),
            Turn(
                role="assistant",
                content="Preview custom field update.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_UPDATE_CUSTOM_FIELD_VALUE,
                        args={
                            "object_id": 99,
                            "object_type": "oetable",
                            "field_updates": [
                                {"field_name": "Data Owner", "value": "John Smith"},
                            ],
                            "prompt": "Update Data Owner to John Smith",
                            "write_confirmed_by_user": False,
                        },
                        result=preview,
                    ),
                ],
            ),
            Turn(role="user", content="Confirm update."),
            Turn(
                role="assistant",
                content="POSTing custom field with preview token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_UPDATE_CUSTOM_FIELD_VALUE,
                        args={
                            "object_id": 99,
                            "object_type": "oetable",
                            "field_updates": [
                                {"field_name": "Data Owner", "value": "John Smith"},
                            ],
                            "prompt": "Update Data Owner to John Smith",
                            "write_confirmed_by_user": True,
                            "confirmation_token": _CUSTOM_FIELD_CONFIRM_TOKEN,
                        },
                        result=post,
                    ),
                ],
            ),
            Turn(role="assistant", content="Custom field Data Owner updated."),
        ],
    )


def golden_dq_coverage_workflow() -> ConversationalTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({
            TOOL_ASSET_EXPLORER,
            TOOL_DQ_RULE_ADVISOR,
            TOOL_DQ_RULE_ADVISOR,
            TOOL_DQ_RULE_MANAGER,
            TOOL_DQ_RULE_MANAGER,
        }),
        prompt_names=frozenset({"assess_cde_dq_coverage"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_ASSESS_CDE_DQ_PROMPT_TEXT),
            )
        ],
    )
    return ConversationalTestCase(
        name="dq_coverage_workflow",
        scenario="Analyst assesses CDE DQ coverage and links rules to columns.",
        expected_outcome=(
            "Agent runs assess_cde_dq, looks up a rule, previews and confirms association, "
            "then previews and confirms create_dq_rules when needed."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(
                role="user",
                content="Assess DQ coverage for CDE columns on customer_profile table.",
            ),
            Turn(
                role="assistant",
                content="Following assess_cde_dq_coverage workflow.",
                mcp_prompts_called=[
                    MCPPromptCall(name="assess_cde_dq_coverage", result=prompt_result),
                ],
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_ASSET_EXPLORER,
                        args={
                            "search_terms": ["customer", "profile"],
                            "object_type": "oetable",
                        },
                        result=tool_call_result(
                            {
                                "total": 1,
                                "results": [{"objectId": 10, "name": "customer_profile"}],
                            }
                        ),
                    ),
                    MCPToolCall(
                        name=TOOL_DQ_RULE_ADVISOR,
                        args={
                            "step": "assess",
                            "objects": [
                                {"object_id": 10, "object_type": "oetable"},
                            ],
                            "description_term_name": "Net Revenue",
                        },
                        result=tool_call_result(
                            {
                                "assessedCount": 3,
                                "rows": [{"objectId": 101, "objectType": "oecolumn"}],
                            }
                        ),
                    ),
                ],
            ),
            Turn(
                role="user",
                content="Link the null-density rule to those columns.",
            ),
            Turn(
                role="assistant",
                content="Looking up DQ rule, then previewing association.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_ADVISOR,
                        args={"step": "lookup", "rule_name": "Null Data Density Check"},
                        result=tool_call_result(
                            {"objectId": 42, "objectName": "Null Data Density Check"},
                        ),
                    ),
                    MCPToolCall(
                        name=TOOL_DQ_RULE_MANAGER,
                        args={
                            "step": "associate",
                            "dqrule_id": 42,
                            "objects": [{"object_id": 101, "object_type": "oecolumn"}],
                            "write_confirmed_by_user": False,
                        },
                        result=tool_call_result(
                            {
                                "workflowPhase": "confirm_update",
                                "doNotUpdate": True,
                                "confirmationToken": _ASSOCIATE_DQ_CONFIRM_TOKEN,
                            },
                        ),
                    ),
                ],
            ),
            Turn(role="user", content="Approved — link the rule."),
            Turn(
                role="assistant",
                content="POSTing association with preview token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_MANAGER,
                        args={
                            "step": "associate",
                            "dqrule_id": 42,
                            "objects": [{"object_id": 101, "object_type": "oecolumn"}],
                            "write_confirmed_by_user": True,
                            "confirmation_token": _ASSOCIATE_DQ_CONFIRM_TOKEN,
                        },
                        result=tool_call_result(
                            {"data": {"associatedCount": 1, "dqruleId": 42}},
                        ),
                    ),
                ],
            ),
            Turn(
                role="user",
                content="Create missing DQ rules for any uncovered CDE columns.",
            ),
            Turn(
                role="assistant",
                content="Previewing create_dq_rules in discover mode.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_MANAGER,
                        args={
                            "step": "create_standard",
                            "discover_cde_columns": True,
                            "prefer_existing_rule": True,
                            "write_confirmed_by_user": False,
                        },
                        result=tool_call_result(
                            {
                                "workflowPhase": "confirm_create",
                                "doNotCreate": True,
                                "confirmationToken": _CREATE_DQ_CONFIRM_TOKEN,
                            },
                        ),
                    ),
                ],
            ),
            Turn(role="user", content="Approved — create rules."),
            Turn(
                role="assistant",
                content="POSTing create_dq_rules with preview token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_MANAGER,
                        args={
                            "step": "create_standard",
                            "discover_cde_columns": True,
                            "prefer_existing_rule": True,
                            "write_confirmed_by_user": True,
                            "confirmation_token": _CREATE_DQ_CONFIRM_TOKEN,
                        },
                        result=tool_call_result(
                            {"rows": [{"status": "created", "dqruleId": 55}]},
                        ),
                    ),
                ],
            ),
            Turn(role="assistant", content="DQ coverage workflow complete."),
        ],
    )


def golden_custom_sql_dq_workflow() -> ConversationalTestCase:
    srv = ovaledge_eval_mcp_server(
        tool_names=frozenset({
            TOOL_DQ_RULE_ADVISOR,
            TOOL_DQ_RULE_ADVISOR,
            TOOL_DQ_RULE_MANAGER,
        }),
        prompt_names=frozenset({"create_custom_sql_dq_workflow"}),
    )
    prompt_result = GetPromptResult(
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=_CUSTOM_SQL_DQ_PROMPT_TEXT),
            )
        ],
    )
    validate_preview = tool_call_result(
        {
            "workflowPhase": "confirm_create",
            "doNotCreate": True,
            "confirmationToken": _VALIDATE_DQ_QUERIES_CONFIRM_TOKEN,
            "formattedResponse": "**Confirm DQ SQL validation**",
        }
    )
    validate_post = tool_call_result(
        {
            "workflowPhase": "validate_queries",
            "canCreateRule": True,
            "formattedResponse": "Can create rule: Yes",
        }
    )
    create_preview = tool_call_result(
        {
            "workflowPhase": "confirm_create",
            "doNotCreate": True,
            "confirmationToken": _CREATE_SQL_DQ_RULE_CONFIRM_TOKEN,
            "formattedResponse": "**Confirm custom SQL DQ rule create**",
        }
    )
    create_post = tool_call_result(
        {
            "workflowPhase": "create_sql_rule",
            "data": {"dqruleId": 9001, "ruleName": "revenue_null_check"},
        }
    )
    return ConversationalTestCase(
        name="custom_sql_dq_workflow",
        scenario="Analyst generates, validates, and creates a custom SQL DQ rule.",
        expected_outcome=(
            "Agent calls generate_dq_queries, previews and confirms validate_dq_queries, "
            "then previews and confirms create_sql_dq_rule when validation allows."
        ),
        mcp_servers=[srv],
        turns=[
            Turn(
                role="user",
                content="Create a custom SQL DQ rule for revenue column 101.",
            ),
            Turn(
                role="assistant",
                content="Following create_custom_sql_dq_workflow.",
                mcp_prompts_called=[
                    MCPPromptCall(
                        name="create_custom_sql_dq_workflow",
                        result=prompt_result,
                    ),
                ],
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_ADVISOR,
                        args={
                            "step": "generate_query",
                            "objects": [{"object_id": 101, "object_type": "oecolumn"}],
                        },
                        result=tool_call_result(
                            {
                                "workflowPhase": "generate_queries",
                                "connectionId": 1,
                                "schemaId": 2,
                                "data": {
                                    "status": "generated",
                                    "ruleQuery": _VALIDATE_DQ_QUERIES_POST_BODY[
                                        "ruleQuery"
                                    ],
                                    "statsQuery": _VALIDATE_DQ_QUERIES_POST_BODY[
                                        "statsQuery"
                                    ],
                                    "failedValuesQuery": _VALIDATE_DQ_QUERIES_POST_BODY[
                                        "failedValuesQuery"
                                    ],
                                    "context": {"connectionId": 1, "schemaId": 2},
                                },
                            },
                        ),
                    ),
                ],
            ),
            Turn(
                role="user",
                content="Validate the SQL on the connection, then create the rule if valid.",
            ),
            Turn(
                role="assistant",
                content="Previewing validate_dq_queries — no execution yet.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_ADVISOR,
                        args={
                            "step": "validate_query",
                            "connection_id": 1,
                            "schema_id": 2,
                            "rule_query": _VALIDATE_DQ_QUERIES_POST_BODY["ruleQuery"],
                            "stats_query": _VALIDATE_DQ_QUERIES_POST_BODY["statsQuery"],
                            "failed_values_query": _VALIDATE_DQ_QUERIES_POST_BODY[
                                "failedValuesQuery"
                            ],
                            "write_confirmed_by_user": False,
                        },
                        result=validate_preview,
                    ),
                ],
            ),
            Turn(role="user", content="Approved — run validation."),
            Turn(
                role="assistant",
                content="Executing validate_dq_queries with preview token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_ADVISOR,
                        args={
                            "step": "validate_query",
                            "connection_id": 1,
                            "schema_id": 2,
                            "rule_query": _VALIDATE_DQ_QUERIES_POST_BODY["ruleQuery"],
                            "stats_query": _VALIDATE_DQ_QUERIES_POST_BODY["statsQuery"],
                            "failed_values_query": _VALIDATE_DQ_QUERIES_POST_BODY[
                                "failedValuesQuery"
                            ],
                            "write_confirmed_by_user": True,
                            "confirmation_token": _VALIDATE_DQ_QUERIES_CONFIRM_TOKEN,
                        },
                        result=validate_post,
                    ),
                ],
            ),
            Turn(
                role="assistant",
                content="Previewing create_sql_dq_rule.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_MANAGER,
                        args={
                            "step": "create_custom_sql",
                            "objects": [{"object_id": 101, "object_type": "oecolumn"}],
                            "rule_name": "revenue_null_check",
                            "rule_query": _CREATE_SQL_DQ_RULE_POST_BODY["ruleQuery"],
                            "stats_query": _CREATE_SQL_DQ_RULE_POST_BODY["statsQuery"],
                            "failed_values_query": _CREATE_SQL_DQ_RULE_POST_BODY[
                                "failedValuesQuery"
                            ],
                            "connection_id": 1,
                            "schema_id": 2,
                            "write_confirmed_by_user": False,
                        },
                        result=create_preview,
                    ),
                ],
            ),
            Turn(role="user", content="Approved — create the data quality rule."),
            Turn(
                role="assistant",
                content="POSTing create_sql_dq_rule with preview token.",
                mcp_tools_called=[
                    MCPToolCall(
                        name=TOOL_DQ_RULE_MANAGER,
                        args={
                            "step": "create_custom_sql",
                            "objects": [{"object_id": 101, "object_type": "oecolumn"}],
                            "rule_name": "revenue_null_check",
                            "rule_query": _CREATE_SQL_DQ_RULE_POST_BODY["ruleQuery"],
                            "stats_query": _CREATE_SQL_DQ_RULE_POST_BODY["statsQuery"],
                            "failed_values_query": _CREATE_SQL_DQ_RULE_POST_BODY[
                                "failedValuesQuery"
                            ],
                            "connection_id": 1,
                            "schema_id": 2,
                            "write_confirmed_by_user": True,
                            "confirmation_token": _CREATE_SQL_DQ_RULE_CONFIRM_TOKEN,
                        },
                        result=create_post,
                    ),
                ],
            ),
            Turn(role="assistant", content="Custom SQL DQ rule created."),
        ],
    )


COVERAGE_MCP_USE_GOLDEN_FNS: list[str] = [
    "golden_mcp_use_trust_assessment",
    "golden_mcp_use_explain_business_term",
    "golden_mcp_use_explain_tag",
    "golden_mcp_use_explain_dq_rule",
    "golden_mcp_use_metadata_drift",
    "golden_mcp_use_find_related_assets",
    "golden_mcp_use_request_access_not_access_explorer",
]

COVERAGE_CONVERSATIONAL_GOLDEN_FNS: list[str] = [
    "golden_governed_glossary_create_two_step",
    "golden_governed_tag_create_two_step",
    "golden_governed_service_request_create_two_step",
    "golden_governed_roles_confirm_two_step",
    "golden_governed_cde_confirm_two_step",
    "golden_governed_custom_field_confirm_two_step",
    "golden_dq_coverage_workflow",
    "golden_custom_sql_dq_workflow",
]

__all__ = [
    *COVERAGE_MCP_USE_GOLDEN_FNS,
    *COVERAGE_CONVERSATIONAL_GOLDEN_FNS,
]
