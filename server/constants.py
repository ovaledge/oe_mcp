"""
Canonical tool and resource names.
Prompts reference these constants — rename here, not in prompt strings.
"""

# ── Tool names ───────────────────────────────────────────────────
TOOL_SEARCH_CATALOG = "search_catalog_assets"
TOOL_CATALOG_ASSET_DETAILS = "catalog_asset_details"
TOOL_COLUMN_PROFILE = "column_profile_statistics"
TOOL_TABLE_ENTITY_RELATIONSHIPS = "table_entity_relationships"
TOOL_ASSET_LINEAGE = "asset_lineage"
TOOL_LOOKUP_GLOSSARY_TERM = "lookup_glossary_term"
TOOL_LOOKUP_TAGS = "lookup_tags"
TOOL_SEARCH_DOCS = "search_platform_docs"

# ── Object type labels (catalog / UI) ────────────────────────────
OBJECT_TYPES = [
    "TABLE",
    "VIEW",
    "COLUMN",
    "SCHEMA",
    "DATABASE",
    "REPORT",
    "FILE",
    "FILE_COLUMN",
    "REPORT_COLUMN",
    "API",
    "API_ATTRIBUTE",
    "CODE",
]

# ── Certification statuses ───────────────────────────────────────
CERT_STATUSES = ["certified", "cautioned", "violated", "inactive"]

# ── Sort options ─────────────────────────────────────────────────
SORT_OPTIONS = ["RELEVANCE", "POPULARITY", "DQ_SCORE", "CURATION_SCORE", "NAME"]

# ── OvalEdge MCP HTTP paths (appended to OVALEDGE_BASE_URL) ──────
MCP_PATH_SEARCH_CATALOG = "/v1/mcp/search-catalog"
MCP_PATH_OBJECT_DETAILS = "/v1/mcp/object-details"
MCP_PATH_COLUMN_PROFILE = "/v1/mcp/column-profile"
MCP_PATH_ENTITY_RELATIONSHIPS = "/v1/mcp/entity-relationships"
MCP_PATH_LINEAGE = "/v1/mcp/lineage"
MCP_PATH_GLOSSARY_TERMS = "/v1/mcp/glossary-terms"
MCP_PATH_TAGS = "/v1/mcp/tags"
MCP_PATH_SEARCH_PLATFORM_DOCS = "/v1/mcp/search-platform-docs"

# ── MCP resource URI templates (FastMCP @resource) ───────────────
MCP_RESOURCE_CATALOG_TABLE = "ovaledge://catalog/table/{object_id}"
MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM = "ovaledge://governance/glossary-term/{object_id}"

# ── Static doc resources (markdown under server/docs/) ───────────
DOCS_RESOURCE_URI_PREFIX = "docs://ovaledge"

# ── OvalEdge auth constants ───────────────────────────────────────
# Based on validated token exchange endpoint.
OVALEDGE_TOKEN_EXCHANGE_PATH = "/api/user/token/generate"

# Refresh local JWT before hard expiry to avoid mid-call failures.
JWT_REFRESH_LEEWAY_SECONDS = 120
