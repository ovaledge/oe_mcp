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
    TOOL_TABLE_ENTITY_RELATIONSHIPS,
    TOOL_UPDATE_ASSET_DESCRIPTIONS,
    TOOL_UPDATE_GOVERNANCE_ROLES,
    TOOL_USER_OBJECT_ACCESS,
)

MCP_TOOL_NAMES: frozenset[str] = frozenset(
    {
        TOOL_SEARCH_CATALOG,
        TOOL_CATALOG_ASSET_DETAILS,
        TOOL_COLUMN_PROFILE,
        TOOL_TABLE_ENTITY_RELATIONSHIPS,
        TOOL_ASSET_LINEAGE,
        TOOL_METADATA_CHANGES_BETWEEN_CRAWLS,
        TOOL_LOOKUP_GLOSSARY_TERM,
        TOOL_CREATE_GLOSSARY_TERM,
        TOOL_LOOKUP_TAGS,
        TOOL_CREATE_TAG,
        TOOL_LOOKUP_DATASTORY,
        TOOL_SEARCH_DOCS,
        TOOL_UPDATE_ASSET_DESCRIPTIONS,
        TOOL_UPDATE_GOVERNANCE_ROLES,
        TOOL_LOOKUP_DQ_RULE,
        TOOL_USER_OBJECT_ACCESS,
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
        "native_source_access",
        "explain_tag",
        "explain_dq_rule",
        "create_business_glossary_term",
        "create_governance_tag",
        "document_asset_descriptions",
        "assign_governance_roles",
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
