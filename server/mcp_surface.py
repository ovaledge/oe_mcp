"""
Canonical MCP surface names (tools, workflow prompts, resource templates).

Used by tests and evals so registration stays aligned with expectations.
"""

from __future__ import annotations

from server.constants import (
    MCP_RESOURCE_CATALOG_FILE,
    MCP_RESOURCE_CATALOG_TABLE,
    MCP_RESOURCE_GOVERNANCE_DATA_STORY,
    MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM,
    MCP_RESOURCE_GOVERNANCE_TAG,
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
    TOOL_UPDATE_CDE_ASSOCIATIONS,
    TOOL_UPDATE_CUSTOM_FIELD_VALUE,
    TOOL_UPDATE_GOVERNANCE_ROLES,
)

MCP_TOOL_NAMES: frozenset[str] = frozenset(
    {
        TOOL_ASSET_EXPLORER,
        TOOL_ASSET_DETAILS,
        TOOL_ASSET_LINEAGE,
        TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
        TOOL_CREATE_GLOSSARY_TERM,
        TOOL_CREATE_TAG,
        TOOL_KNOWLEDGE_SEARCH,
        TOOL_UPDATE_ASSET_DESCRIPTIONS,
        TOOL_UPDATE_CDE_ASSOCIATIONS,
        TOOL_UPDATE_GOVERNANCE_ROLES,
        TOOL_UPDATE_CUSTOM_FIELD_VALUE,
        TOOL_DQ_RULE_ADVISOR,
        TOOL_DQ_RULE_MANAGER,
        TOOL_ACCESS_EXPLORER,
    }
)

MCP_WORKFLOW_PROMPT_NAMES: frozenset[str] = frozenset(
    {
        "data_discovery",
        "explain_business_term",
        "trust_assessment",
        "explore_data_domain",
        "trace_data_lineage",
        "find_related_assets",
        "organizational_knowledge",
        "platform_help",
        "metadata_drift",
        "resolve_object_access",
        "native_source_access",
        "dam_object_browse",
        "catalog_object_access",
        "explain_tag",
        "explain_dq_rule",
        "create_business_glossary_term",
        "create_governance_tag",
        "document_asset_descriptions",
        "assign_governance_roles",
        "assess_cde_dq_coverage",
        "create_custom_sql_dq_workflow",
    }
)

MCP_OVALEDGE_RESOURCE_TEMPLATES: frozenset[str] = frozenset(
    {
        MCP_RESOURCE_CATALOG_TABLE,
        MCP_RESOURCE_CATALOG_FILE,
        MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM,
        MCP_RESOURCE_GOVERNANCE_DATA_STORY,
        MCP_RESOURCE_GOVERNANCE_TAG,
    }
)
