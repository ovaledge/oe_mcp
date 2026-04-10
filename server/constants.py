"""
Canonical tool and resource names.
Prompts reference these constants — rename here, not in prompt strings.
"""

# ── Tool names ───────────────────────────────────────────────────
TOOL_SEARCH_CATALOG = "search_catalog_assets"
TOOL_GET_ASSET = "get_asset_details"
TOOL_COUNT_CATALOG = "count_catalog_assets"
TOOL_LOOKUP_TERM = "lookup_business_term"
TOOL_GET_LINEAGE = "get_asset_lineage"
TOOL_GET_RELATIONSHIPS = "get_entity_relationships"
TOOL_SEARCH_DOCS = "search_platform_docs"

# ── Object type enum values ──────────────────────────────────────
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

# ── OvalEdge auth constants ───────────────────────────────────────
# Based on validated token exchange endpoint.
OVALEDGE_TOKEN_EXCHANGE_PATH = "/api/user/token/generate"

# Refresh local JWT before hard expiry to avoid mid-call failures.
JWT_REFRESH_LEEWAY_SECONDS = 120
