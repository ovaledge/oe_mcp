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
TOOL_LOOKUP_DATASTORY = "lookup_datastory"
TOOL_SEARCH_DOCS = "search_platform_docs"

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
MCP_PATH_LOOKUP_DATASTORY = "/api/v1/mcp/lookup-datastory"
# Optional on glossary-terms and tags (Spring default 20).
MCP_GLOSSARY_TAGS_LIMIT_DEFAULT = 20
MCP_GLOSSARY_TAGS_LIMIT_MAX = 100
MCP_PATH_SEARCH_PLATFORM_DOCS = "/api/v1/mcp/search-platform-docs"

# search-catalog: optional query param for full NL user text / context (vector search, etc.).
# Spring: @RequestParam(value = "contextQuery", required = false) String contextQuery
MCP_SEARCH_CONTEXT_QUERY_PARAM = "contextQuery"

# search-catalog: keywords as one URL query param — JSON array string (URL-encoded by client).
# Example: ?searchTerms=%5B%22a%22%2C%22b%22%5D  →  ["a","b"]
# Spring: @RequestParam(value = "searchTerms", required = false) String searchTerms
#         then parse JSON to List<String> (e.g. ObjectMapper.readValue)
MCP_SEARCH_TERMS_PARAM = "searchTerms"

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

# ── AUTH_MODE=remote_credentials (per-user headers) ─────────────
HEADER_OE_USER_TOKEN = "X-OvalEdge-Token"
HEADER_OE_USER_SECRET = "X-OvalEdge-Secret"
# Single header for clients that allow one API key (e.g. Microsoft Copilot Studio).
# Value: ``<token>::<secret>`` — OvalEdge tokens/secrets do not contain ``::``.
HEADER_OE_USER_COMBINED = "X-OvalEdge-Credentials"
CREDENTIALS_COMBINED_SEPARATOR = "::"

# Regenerate cached OvalEdge JWT this many seconds before ``exp``.
CREDENTIALS_REFRESH_LEEWAY_SECONDS = 60

# In-memory cap for distinct credential-key JWT entries.
CREDENTIALS_CACHE_MAX_ENTRIES = 10_000

# Temporary block after token/generate returns 401 (same credential key).
NEGATIVE_CREDENTIALS_CACHE_TTL_SECONDS = 30

# Cap distinct blocked keys (LRU eviction).
NEGATIVE_CREDENTIALS_CACHE_MAX_ENTRIES = 10_000

# After JWT ``exp``, drop cache entry this many seconds later (0 = at exp boundary).
CREDENTIALS_CACHE_POST_EXP_GRACE_SECONDS = 0

# Max length per header value after trim (before exchange).
CREDENTIALS_HEADER_MAX_LEN = 2048

# Max length for combined header value (token + separator + secret).
CREDENTIALS_COMBINED_MAX_LEN = (
    2 * CREDENTIALS_HEADER_MAX_LEN + len(CREDENTIALS_COMBINED_SEPARATOR)
)
