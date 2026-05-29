"""
Canonical tool and resource names, MCP paths, and catalog objectType allow-lists.
Prompts reference tool name constants — rename here, not in prompt strings.
"""

# ── Tool names ───────────────────────────────────────────────────
TOOL_SEARCH_CATALOG = "search_catalog_assets"
TOOL_CATALOG_ASSET_DETAILS = "catalog_asset_details"
TOOL_COLUMN_PROFILE = "column_profile_statistics"
TOOL_TABLE_ENTITY_RELATIONSHIPS = "table_entity_relationships"
TOOL_ASSET_LINEAGE = "asset_lineage"
TOOL_METADATA_CHANGES_BETWEEN_CRAWLS = "get_metadata_changes_between_crawls"
TOOL_LOOKUP_GLOSSARY_TERM = "lookup_glossary_term"
TOOL_LOOKUP_TAGS = "lookup_tags"
TOOL_CREATE_TAG = "create_tag"
TOOL_LOOKUP_DATASTORY = "lookup_datastory"
TOOL_SEARCH_DOCS = "search_platform_docs"
TOOL_GET_SOURCE_SYSTEM_ACCESS = "get_source_system_access"

# Lowercase objectType for MCP search-catalog and object-details (matches OvalEdge API).
MCP_CATALOG_OBJECT_TYPES = frozenset(
    {
        "oeschema",
        "oetable",
        "oecolumn",
        "oefile",
        "filecolumn",
        "oechart",
        "chartchild",
        "oeapi",
        "oeapicolumn",
        "oequery",
        "dp_product",
        "glossary",
        "oetag",
        "oestory",
    }
)
MCP_CATALOG_OBJECT_TYPES_DOC = ", ".join(sorted(MCP_CATALOG_OBJECT_TYPES))

# ── OvalEdge MCP HTTP paths (appended to OVALEDGE_BASE_URL) ──────
MCP_PATH_SEARCH_CATALOG = "/api/v1/mcp/search-catalog"
MCP_PATH_OBJECT_DETAILS = "/api/v1/mcp/object-details"
MCP_PATH_COLUMN_PROFILE = "/api/v1/mcp/column-profile"
MCP_PATH_ENTITY_RELATIONSHIPS = "/api/v1/mcp/entity-relationships"
MCP_PATH_LINEAGE = "/api/v1/mcp/lineage"
MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS = (
    "/api/v1/mcp/metadata-changes-between-crawls"
)
MCP_PATH_GLOSSARY_TERMS = "/api/v1/mcp/glossary-terms"
MCP_PATH_TAGS = "/api/v1/mcp/tags"
MCP_PATH_TAGS_CREATE_OPTIONS = "/api/v1/mcp/tags/create-options"
MCP_PATH_TAGS_PARENT_OPTIONS = "/api/v1/mcp/tags/parent-options"
MCP_PATH_SEARCH_PLATFORM_DOCS = "/api/v1/mcp/search-platform-docs"
MCP_PATH_SOURCE_SYSTEM_ACCESS = "/api/v1/mcp/source-system-access"
MCP_PATH_LOOKUP_DATASTORY = "/api/v1/mcp/lookup-datastory"

# Secure-mode create_tag wizard phases (matches OvalEdge UI).
SELECTION_PHASE_MASTER_REQUIRED = "MASTER_REQUIRED"
SELECTION_PHASE_PARENT_OPTIONAL = "PARENT_OPTIONAL"
# create_tag guidance (not an error — tag not created yet).
STATUS_AWAITING_USER_SELECTION = "awaiting_user_selection"
# Optional on glossary-terms and tags (Spring default 20).
MCP_GLOSSARY_TAGS_LIMIT_DEFAULT = 20
MCP_GLOSSARY_TAGS_LIMIT_MAX = 100

# get_source_system_access — must match backend McpSourceSystemAccessReadService.
MCP_SOURCE_SYSTEMS = frozenset({"redshift", "snowflake", "tableau"})
MCP_SOURCE_SYSTEMS_DOC = ", ".join(sorted(MCP_SOURCE_SYSTEMS))
MCP_QUERY_DIRECTIONS = frozenset({"user_to_objects", "object_to_users"})
MCP_QUERY_DIRECTIONS_DOC = "user_to_objects | object_to_users"
MCP_GRANT_MECHANISMS = frozenset({"direct", "group", "role"})

# search-catalog: optional query param for full NL user text / context (vector search, etc.).
MCP_SEARCH_CONTEXT_QUERY_PARAM = "contextQuery"
MCP_SEARCH_TERMS_PARAM = "searchTerms"

# ── MCP resource URI templates (FastMCP @resource) ───────────────
MCP_RESOURCE_CATALOG_TABLE = "ovaledge://catalog/table/{object_id}"
MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM = "ovaledge://governance/glossary-term/{object_id}"

# ── Static doc resources (markdown under server/docs/) ───────────
DOCS_RESOURCE_URI_PREFIX = "docs://ovaledge"

# ── OvalEdge auth constants ───────────────────────────────────────
OVALEDGE_TOKEN_EXCHANGE_PATH = "/api/user/token/generate"
JWT_REFRESH_LEEWAY_SECONDS = 120

# ── AUTH_MODE=remote_credentials (per-user headers) ─────────────
HEADER_OE_USER_TOKEN = "X-OvalEdge-Token"
HEADER_OE_USER_SECRET = "X-OvalEdge-Secret"
HEADER_OE_USER_COMBINED = "X-OvalEdge-Credentials"
CREDENTIALS_COMBINED_SEPARATOR = "::"
CREDENTIALS_REFRESH_LEEWAY_SECONDS = 60
CREDENTIALS_CACHE_MAX_ENTRIES = 10_000
NEGATIVE_CREDENTIALS_CACHE_TTL_SECONDS = 30
NEGATIVE_CREDENTIALS_CACHE_MAX_ENTRIES = 10_000
CREDENTIALS_CACHE_POST_EXP_GRACE_SECONDS = 0
CREDENTIALS_HEADER_MAX_LEN = 2048
CREDENTIALS_COMBINED_MAX_LEN = (
    2 * CREDENTIALS_HEADER_MAX_LEN + len(CREDENTIALS_COMBINED_SEPARATOR)
)
