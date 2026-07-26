"""
Canonical tool and resource names, MCP paths, and catalog objectType allow-lists.
Prompts reference tool name constants — rename here, not in prompt strings.
"""

# ── Tool names ───────────────────────────────────────────────────
TOOL_ASSET_EXPLORER = "asset_explorer"
TOOL_ASSET_DETAILS = "asset_details"
TOOL_ASSET_LINEAGE = "asset_lineage"
TOOL_KNOWLEDGE_SEARCH = "knowledge_search"
TOOL_METADATA_CHANGES_BETWEEN_CRAWLS = "metadata_changes_between_crawls"
TOOL_CREATE_GLOSSARY_TERM = "create_glossary_term"
TOOL_CREATE_TAG = "create_tag"
TOOL_UPDATE_ASSET_DESCRIPTIONS = "update_asset_descriptions"
TOOL_UPDATE_CDE_ASSOCIATIONS = "update_cde_associations"
TOOL_UPDATE_GOVERNANCE_ROLES = "update_governance_roles"
TOOL_UPDATE_CUSTOM_FIELD_VALUE = "update_custom_field_value"
TOOL_LOOKUP_DQ_RULE = "lookup_dq_rule"
TOOL_SOURCE_SYSTEM_ACCESS = "source_system_access"
TOOL_GET_USER_OBJECT_ACCESS = "get_user_object_access"
TOOL_ASSESS_CDE_DQ = "assess_cde_dq"
TOOL_ASSOCIATE_DQ_RULE_OBJECTS = "associate_dq_rule_objects"
TOOL_CREATE_DQ_RULES = "create_dq_rules"
TOOL_GENERATE_DQ_QUERIES = "generate_dq_queries"
TOOL_VALIDATE_DQ_QUERIES = "validate_dq_queries"
TOOL_CREATE_SQL_DQ_RULE = "create_sql_dq_rule"

# MCP tool data classification (appended to every _DESC_* via classify_tool_desc).
MCP_TOOL_CLASSIFICATION_INTERNAL = (
    "Data classification: INTERNAL (OvalEdge governance metadata; RBAC enforced server-side)."
)
MCP_TOOL_CLASSIFICATION_CONFIDENTIAL = (
    "Data classification: CONFIDENTIAL (access grants, principals, or native privileges; "
    "RBAC/DAA enforced server-side)."
)

# Lowercase objectType for MCP search-catalog and object-details (matches OvalEdge API).
MCP_CATALOG_OBJECT_TYPES = frozenset(
    {
        "oeschema",
        "oetable",
        "oecolumn",
        "oefile",
        "filecolumn",
        "oefilecolumn",
        "oechart",
        "chartchild",
        "oeapi",
        "oeapicolumn",
        "oequery",
        "code",
        "oecode",
        "dp_product",
        "glossary",
        "businessglossary",
        "oetag",
        "mastertag",
        "oeglobaldomain",
        "storyzone",
        "dp_domain",
        "oedomain",
        "oestory",
    }
)
MCP_CATALOG_OBJECT_TYPES_DOC = ", ".join(sorted(MCP_CATALOG_OBJECT_TYPES))

# BRD object types for update_asset_descriptions (oestory excluded — no description slots).
MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES = frozenset(
    {
        "oeschema",
        "oetable",
        "oecolumn",
        "oefile",
        "filecolumn",
        "oefilecolumn",
        "oechart",
        "chartchild",
        "oeapi",
        "oeapicolumn",
        "oequery",
        "code",
        "oecode",
        "oeglobaldomain",
        "glossary",
        "businessglossary",
        "oetag",
        "mastertag",
        "dp_domain",
        "dp_product",
    }
)
MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES_DOC = ", ".join(
    sorted(MCP_UPDATE_ASSET_DESCRIPTION_OBJECT_TYPES)
)

# CDE write tool: catalog assets with criticaldataelement columns (v7.2 schema).
MCP_UPDATE_CDE_OBJECT_TYPES = frozenset(
    {
        "oeschema",
        "oetable",
        "oecolumn",
        "oefile",
        "oefilecolumn",
        "oechart",
        "chartchild",
        "oeapi",
        "oeapicolumn",
        "oequery",
        "apiobject",
        "apicolumn",
        "filecolumn",
        "code",
    }
)
MCP_CDE_ACTIONS = frozenset({"Yes", "No", "None"})
_CDE_OBJECT_TYPE_ALIASES = frozenset({"apiobject", "apicolumn", "filecolumn", "code"})
MCP_UPDATE_CDE_OBJECT_TYPES_DOC = ", ".join(
    sorted(t for t in MCP_UPDATE_CDE_OBJECT_TYPES if t not in _CDE_OBJECT_TYPE_ALIASES)
)

# ── OvalEdge MCP HTTP paths (appended to OVALEDGE_BASE_URL) ──────
MCP_PATH_ASSET_EXPLORER = "/api/v1/mcp/asset-explorer"
MCP_PATH_ASSET_DETAILS = "/api/v1/mcp/asset-details"
MCP_PATH_ASSET_LINEAGE = "/api/v1/mcp/asset-lineage"
MCP_PATH_KNOWLEDGE_SEARCH = "/api/v1/mcp/knowledge-search"
MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS = (
    "/api/v1/mcp/metadata-changes-between-crawls"
)
MCP_PATH_GLOSSARY_TERMS = "/api/v1/mcp/glossary-terms"  # POST create only
MCP_PATH_DOMAIN_METADATA = "/api/v1/mcp/domain-metadata"
# termCreationTemplate searchOn values (GlobalDomainActivity).
MCP_DOMAIN_METADATA_SEARCH_ON = frozenset({"oeglobaldomain", "category", "subcategory"})
MCP_DOMAIN_METADATA_SIZE_DEFAULT = 100
MCP_DOMAIN_METADATA_SIZE_MAX = 500
# In-app glossary term route (matches AppConstants.NAV_BUSINESS_GLOSSARY_ID).
NAV_GLOSSARY_TERM_HASH = "#nav/glossary?id="
MCP_PATH_TAGS = "/api/v1/mcp/tags"  # POST create only
MCP_PATH_TAGS_CREATE_OPTIONS = "/api/v1/mcp/tags/create-options"
MCP_PATH_TAGS_PARENT_OPTIONS = "/api/v1/mcp/tags/parent-options"
MCP_PATH_SOURCE_SYSTEM_ACCESS = "/api/v1/mcp/source-system-access"
MCP_PATH_GET_USER_OBJECT_ACCESS = "/api/v1/mcp/get-user-object-access"

# Secure-mode create_tag wizard phases (matches OvalEdge UI).
SELECTION_PHASE_MASTER_REQUIRED = "MASTER_REQUIRED"
SELECTION_PHASE_PARENT_OPTIONAL = "PARENT_OPTIONAL"
# create_tag guidance (not an error — tag not created yet).
STATUS_AWAITING_USER_SELECTION = "awaiting_user_selection"

# Optional on glossary-terms and tags (Spring default 20).
MCP_GLOSSARY_TAGS_LIMIT_DEFAULT = 25
MCP_GLOSSARY_TAGS_LIMIT_MAX = 100
MCP_PATH_UPDATE_ASSET_DESCRIPTIONS = "/api/v1/mcp/update-asset-descriptions"
MCP_PATH_UPDATE_CDE_ASSOCIATIONS = "/api/v1/mcp/update-cde-associations"
MCP_PATH_UPDATE_GOVERNANCE_ROLES = "/api/v1/mcp/update-governance-roles"
MCP_PATH_CUSTOM_FIELDS = "/api/v1/mcp/custom-fields"
MCP_PATH_UPDATE_CUSTOM_FIELD_VALUES = "/api/v1/mcp/update-custom-field-values"

# Custom field read/write (matches McpCustomFieldObjectTypes in oe-next-gen-commons).
MCP_CUSTOM_FIELD_OBJECT_TYPES = frozenset(
    {
        "oeschema",
        "oetable",
        "oecolumn",
        "oefile",
        "oefilecolumn",
        "oechart",
        "chartchild",
        "apiobject",
        "apicolumn",
        "oequery",
        "glossary",
        "oetag",
        "dqrule",
        "dp_product",
        "code",
    }
)
MCP_CUSTOM_FIELD_OBJECT_TYPES_DOC = ", ".join(sorted(MCP_CUSTOM_FIELD_OBJECT_TYPES))

# objectType values for update_governance_roles that are NOT in asset_explorer.
MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES = frozenset(
    {
        "dqrule",
        "dqscheme",
        "dag",
        "policy",
        "oeglobaldomain",
        "processing_activity",
        "ropa_report",
        "category",
        "subcategory",
    }
)
# Steward-only governance updates (UI parity).
MCP_GOVERNANCE_STEWARD_ONLY_OBJECT_TYPES = frozenset({"dqrule", "dqscheme"})
MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES_DOC = ", ".join(
    sorted(MCP_GOVERNANCE_NON_CATALOG_OBJECT_TYPES)
)

# Native source-system access (source_system_access).
# Must match backend McpSourceSystemAccessReadService.
MCP_SOURCE_SYSTEMS = frozenset({"redshift", "snowflake", "tableau"})
MCP_SOURCE_SYSTEMS_DOC = ", ".join(sorted(MCP_SOURCE_SYSTEMS))
MCP_QUERY_DIRECTIONS = frozenset({"user_to_objects", "object_to_users", "browse"})
MCP_QUERY_DIRECTIONS_DOC = "user_to_objects | object_to_users | browse"

# RDAM native object levels for source_system_access (wire: objectType).
# Must match backend McpSourceSystemAccessReadService.
MCP_RDAM_OBJECT_TYPES = frozenset(
    {"database", "schema", "table", "column", "project", "report"}
)
# MCP-only: omit API objectType filter and return every harvested object level.
MCP_RDAM_OBJECT_TYPE_ALL = "all"
MCP_RDAM_SCOPE_MODE_EXACT = "exact"
MCP_RDAM_SCOPE_MODE_DESCENDANTS = "descendants"
MCP_RDAM_SCOPE_MODES_DOC = f"{MCP_RDAM_SCOPE_MODE_EXACT} | {MCP_RDAM_SCOPE_MODE_DESCENDANTS}"
MCP_RDAM_OBJECT_TYPES_DOC = (
    ", ".join(sorted(MCP_RDAM_OBJECT_TYPES)) + f", {MCP_RDAM_OBJECT_TYPE_ALL}"
)
# Max schema probes when discovering table locations for incomplete object_path.
MCP_TABLE_SCHEMA_DISCOVERY_MAX_PROBES = 30
# Parallel OvalEdge calls per discovery batch (keeps Lambda under ~30s timeout).
MCP_TABLE_SCHEMA_DISCOVERY_PROBE_CONCURRENCY = 8
# Stop probing once this many table-level matches are found (disambiguation).
MCP_TABLE_SCHEMA_DISCOVERY_EARLY_EXIT_CANDIDATES = 2

MCP_SOURCE_SYSTEM_ACCESS_JAVA_BACKEND_DOC = (
    "**Java backend (McpSourceSystemAccessReadService):** reads all harvested native grants "
    "from RDAM MySQL metadata tables (`rdam_*privilege`) — includes disabled rows and all "
    "roles (custom and built-in) without system/remote filtering. MCP returns the Java "
    "response as-is."
)

# RDAM SQL metadata tables queried by McpSourceSystemAccessReadService (per object_type).
# "metadata table" = OvalEdge DB table storing harvested grants — not a Tableau/Snowflake object.
MCP_RDAM_PRIVILEGE_MAP_DOC = (
    "**RDAM privilege map** (harvested native grants in OvalEdge SQL metadata tables — "
    "not Elasticsearch, not OvalEdge catalog):\n\n"
    "**Redshift / Snowflake** — `object_type` selects which RDAM metadata table to query:\n"
    "| object_type | RDAM metadata table |\n"
    "|-------------|---------------------|\n"
    "| database | `rdam_dbprivilege` |\n"
    "| schema | `rdam_schemaprivilege` |\n"
    "| table | `rdam_tableprivilege` |\n"
    "| column | `rdam_columnprivilege` (Redshift only; `include_columns=true`) |\n\n"
    "**Tableau** — no database/schema/table/column objects; BI assets are **project** "
    "or **report** only:\n"
    "| object_type | RDAM metadata table |\n"
    "|-------------|---------------------|\n"
    "| project | `rdam_reportgroup_privilege` |\n"
    "| report | `rdam_report_privilege` |\n"
    "| group expansion | `rdam_usergroup` (site-group membership for indirect grants) |"
)

# Agents must not fall back to catalog/Elasticsearch when RDAM returns empty or errors.
MCP_RDAM_NO_CATALOG_FALLBACK_DOC = (
    "**No catalog / Elasticsearch fallback:** `source_system_access` reads RDAM SQL metadata "
    "only. Never call `asset_explorer`, `asset_details`, or other catalog "
    "tools as a substitute when RDAM returns empty grants, 4xx/5xx, not-found, or "
    "not-harvested — catalog search cannot answer native Redshift/Snowflake/Tableau grants. "
    "Report the RDAM result (or API error) and suggest RDAM harvest, DAA, object_path / "
    "object_type, or native SQL (e.g. Snowflake `SHOW GRANTS`) — do not invoke catalog search."
)

# RDAM/DAM path + objectType matrix — must match Java McpSourceSystemAccessReadService /
# source-system-access browse path resolution (objectType disambiguates;
# do not infer from segment count alone).
MCP_DAM_OBJECT_PATH_MATRIX_DOC = (
    "**RDAM path + object_type matrix** (Redshift/Snowflake). Scope with **`connection_id`** "
    "(preferred) or optional `connectionName.` prefix on `object_path` when names collide. "
    "Wire to Java as `objectPath` + `objectType` (camelCase). `fully_qualified_name` is an "
    "alias for `object_path` when the user or catalog gives a dotted FQN.\n\n"
    "| Level | fullyQualifiedName / objectPath | object_type |\n"
    "|-------|--------------------------------|-------------|\n"
    "| Connector | — (pass `connection_id` only) | — |\n"
    "| Database | `dbName`, `connectionName.dbName` | `database` |\n"
    "| Schema | `dbName.schemaName`, `schemaName` | `schema` |\n"
    "| Table | `dbName.schemaName.tableName`, `schemaName.tableName`, `tableName` | `table` |\n"
    "| Column | `dbName.schemaName.tableName.columnName`, `schemaName.tableName.columnName`, "
    "`tableName.columnName`, `columnName` | `column` |\n\n"
    "**source_system_access (browse):** `object_path` is the **parent** scope; "
    "`object_type` is the "
    "**child level to list** — omit parent to list databases; `dbName` + `schema` lists schemas; "
    "`dbName.schemaName` + `table` lists tables; `dbName.schemaName.tableName` + `column` "
    "lists columns."
)

# source_system_access objectPath — must match backend path resolution.
MCP_OBJECT_PATH_FORMATS_DOC = (
    "**object_path** formats (Redshift/Snowflake; dot-separated):\n"
    "- Optional OvalEdge **connection name** prefix when multiple connections share a "
    "source type: `connectionName.dbName` (e.g. `snowflake.BUSINESS`), then "
    "`connectionName.dbName.schema`, `connectionName.dbName.schema.table`, "
    "`connectionName.dbName.schema.table.column` (Redshift columns only, with "
    "include_columns=true).\n"
    "- Without connection prefix (prefer **connection_id** to scope instead): "
    "`dbName` (database), `dbName.schema`, `dbName.schema.table` "
    "(e.g. `BUSINESS.BANKING.ALERTS`), `dbName.schema.table.column`.\n"
    "- Partial names (e.g. table `ALERTS`, database `BUSINESS`) are allowed; the API "
    "may return **matchCandidates** — use a full path from candidates or "
    "resolve_all_matches=true.\n"
    "- Tableau project: `Project Name`; report: `Project/Report Name`.\n\n"
    + MCP_DAM_OBJECT_PATH_MATRIX_DOC
)
MCP_SOURCE_SYSTEM_ACCESS_OVERVIEW_DOC = (
    "**Why this tool exists:** `get_user_object_access` resolves effective access at the "
    "OvalEdge **catalog permission** layer. There is no equivalent for access that exists "
    "**natively in the source systems** — Redshift, Snowflake, and Tableau — independent of "
    "OvalEdge grants. Customers need answers like \"What tables can this service account "
    "actually query in Redshift?\" or \"Which users have native access to this table?\" "
    "without navigating each source manually.\n\n"
    "| | get_user_object_access (catalog) | source_system_access (native RDAM) |\n"
    "|---|---|---|\n"
    "| Access layer | OvalEdge catalog permissions | Native source-system grants |\n"
    "| Grant mechanisms | OvalEdge user grants + OvalEdge roles | Redshift (direct / group / "
    "role), Snowflake (role), Tableau (direct / group) |\n"
    "| Permission model | metadata-read/write + data permission levels | Native privileges "
    "(SELECT, INSERT, ALL, …) |\n"
    "| Object scope | All OvalEdge asset types | RS/SF database/schema/table/column; "
    "Tableau project/report |"
)
MCP_CATALOG_OBJECT_ACCESS_OVERVIEW_DOC = (
    "Answers who can see or use a catalog object in OvalEdge (ACL grants), including "
    "metadata-read/write and data permission levels. Effective permission is the highest "
    "across direct user grants and role grants. Use source_system_access for native "
    "database/BI grants only. Connectors (connections) are resolved from the database by "
    "name — they are not in catalog search. Data Domains, Data Products, glossary Domains, "
    "and Story Zones are resolved from the database when Elasticsearch has no document."
)
# Longest phrases first — used by detect_access_intent_from_question (disambiguation.py).
MCP_ACCESS_CATALOG_ACL_SIGNAL_KEYWORDS = (
    "catalog permissions",
    "catalog access",
    "catalog acl",
    "ovaledge security",
    "oe security",
    "acl",
)
MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS = (
    "source system access",
    "data access management",
    "source system",
    "native",
    "remote",
    "dam",
    "source",
)
MCP_ACCESS_PLATFORM_NAME_KEYWORDS = frozenset({"snowflake", "redshift", "tableau"})
MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS_DOC = ", ".join(MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS)
MCP_ACCESS_CATALOG_ACL_SIGNAL_KEYWORDS_DOC = ", ".join(MCP_ACCESS_CATALOG_ACL_SIGNAL_KEYWORDS)
MCP_ACCESS_PLATFORM_NAMES_NOT_SIGNALS_DOC = (
    "Naming Snowflake, Redshift, or Tableau (e.g. \"in Snowflake\", \"on Redshift\") "
    "does **not** skip disambiguation — it only helps pick source_system **after** "
    "intent is confirmed. Examples that still need **1** or **2**: "
    "\"Who has access to BUSINESS.BANKING in Snowflake?\"; "
    "\"Who has access to customer1 in redshift1 in Redshift?\"."
)
MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC = (
    "Ambiguous who-has-access: disambiguate via resolve_object_access; "
    "do not call access tools until user picks. "
    "Skip disambiguation only when native/DAM or catalog ACL/OE security signals "
    "are present. "
    + MCP_ACCESS_PLATFORM_NAMES_NOT_SIGNALS_DOC
)
MCP_ACCESS_DISAMBIGUATION_TOOL_LEAD_DOC = (
    "**Who-has-access:** `resolve_object_access` then `access_intent_confirmed` "
    "(native / catalog_acl). Snowflake/Redshift/Tableau alone do not skip "
    "disambiguation.\n\n"
)
MCP_ACCESS_DISAMBIGUATION_SEARCH_GUARD_DOC = (
    "**Not who-has-access or RDAM** — `resolve_object_access` first; RDAM via "
    "`source_system_access` only.\n\n"
)
MCP_ACCESS_INTENT_NATIVE = "native"
MCP_ACCESS_INTENT_CATALOG_ACL = "catalog_acl"
MCP_ACCESS_INTENT_CONFIRMED_FIELD_DOC = (
    "Who-has-access only: `native` after user picks **1** or when the question names "
    "native/DAM signals (not Snowflake/Redshift/Tableau alone); `catalog_acl` after **2** "
    "or when the question names OE security / ACL / catalog-access signals. "
    "Omit for user_to_objects / user_to_object / browse."
)
MCP_ACCESS_DISAMBIGUATION_USER_MESSAGE = (
    "OvalEdge has **two** different tools for “who has access” questions:\n\n"
    "| Tool | What it answers |\n"
    "|------|------------------|\n"
    f"| **`{TOOL_SOURCE_SYSTEM_ACCESS}`** | **Native / remote** permissions crawled from "
    "Redshift, Snowflake, or Tableau — what you see on the **DAM** (Data Access Management) "
    "screen (e.g. SELECT, roles, groups). |\n"
    f"| **`{TOOL_GET_USER_OBJECT_ACCESS}`** | **OvalEdge catalog ACL** on the **Security** "
    "page — metadata read/write and data permission levels for OvalEdge users and roles. |\n\n"
    "Your question does not mention native/remote/DAM/source-system access or OvalEdge "
    "catalog ACL / OE security signals.\n\n"
    "**Which do you want?**\n"
    "1. **Native source access** — database/BI grants from Redshift, Snowflake, or Tableau\n"
    "2. **OvalEdge catalog ACL** — permissions inside OvalEdge on a catalog asset\n\n"
    "Reply with **1** or **2**, then I will call the matching tool."
)
MCP_ACCESS_DISAMBIGUATION_RULE_DOC = (
    "For who-has-access / permission questions (case-insensitive signals): "
    "native/DAM keywords ("
    + MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS_DOC
    + ") → source_system_access with access_intent_confirmed=native. Catalog ACL keywords ("
    + MCP_ACCESS_CATALOG_ACL_SIGNAL_KEYWORDS_DOC
    + ") → get_user_object_access with access_intent_confirmed=catalog_acl. When **neither** "
    "signal set is present — do **not** call source_system_access or get_user_object_access; "
    "show the disambiguation message and wait for **1** (native) or **2** (catalog ACL). "
    + MCP_ACCESS_PLATFORM_NAMES_NOT_SIGNALS_DOC
    + " Workflow prompt: resolve_object_access."
)
MCP_CATALOG_OBJECT_ACCESS_DIRECTIONS = (
    "`user_to_object` — what access does user X have on object Y? "
    "`object_to_principals` — which users and roles have access on object Y?"
)
MCP_CATALOG_OBJECT_ACCESS_OBJECT_TYPES = frozenset(
    {
        "connection",
        "oeschema",
        "oetable",
        "oecolumn",
        "oefile",
        "filefolder",
        "oedomain",
        "oechart",
        "chartchild",
        "oeapi",
        "oeapicolumn",
        "oequery",
        "code",
        "oecode",
        "oeglobaldomain",
        "storyzone",
        "glossary",
        "oetag",
        "mastertag",
        "oestory",
        "dp_domain",
        "dp_product",
    }
)
MCP_CATALOG_OBJECT_ACCESS_OBJECT_TYPES_DOC = ", ".join(
    sorted(MCP_CATALOG_OBJECT_ACCESS_OBJECT_TYPES)
)
MCP_SOURCE_SYSTEM_ACCESS_GRANT_MODELS_DOC = (
    "**Access grant models by source system** (each grant row includes `grant_mechanism` so "
    "the bot can explain lineage):\n\n"
    "**Redshift** — three mechanisms, all supported:\n"
    "- **direct** — grant to user\n"
    "- **group** — grant to a group → user is a member of that group "
    "(see `contributing_group`)\n"
    "- **role** — grant to a role → role is assigned to the user "
    "(see `contributing_role`)\n\n"
    "**Snowflake** — single mechanism:\n"
    "- **role** — grant to a role → role is assigned to the user (no direct user grants, "
    "no groups)\n\n"
    "**Tableau** — two mechanisms:\n"
    "- **direct** — grant to a user or service account on a project/report\n"
    "- **group** — grant to a site group → user is a member (`contributing_group`; expanded "
    "via `rdam_usergroup`)"
)
MCP_RDAM_OBJECT_TYPE_HIERARCHY_DOC = (
    "**Parent hierarchy — object_to_users only (Redshift/Snowflake):** `column` includes "
    "column + table + schema + database; `table` includes table + schema + database; "
    "`schema` includes schema + database; `database` is database only. "
    "**user_to_objects** returns grants at the requested `object_type` level only — no "
    "ancestor levels."
)
MCP_RDAM_OBJECT_TYPE_DOC = (
    "**object_type** (required): RDAM native object level — "
    + MCP_RDAM_OBJECT_TYPES_DOC
    + ". Sent to the API as `objectType`. Always pass explicitly (do not rely on `.` "
    "segment count alone). Examples: `object_path=SNOWFLAKE.ALERT` + `object_type=schema`; "
    "`object_path=BUSINESS` + `object_type=database`; "
    "`object_path=BUSINESS.BANKING.ACCOUNTSCHEDULE` + `object_type=table`; "
    "Tableau report `Project/Report` + `object_type=report`. "
    "Catalog aliases accepted: `oeschema`→schema, `oetable`→table, `oecolumn`→column. "
    + MCP_RDAM_OBJECT_TYPE_HIERARCHY_DOC
)
MCP_SOURCE_SYSTEM_ACCESS_MULTI_SOURCE_ERROR = (
    "Multiple source_system values are not supported in a single API request. "
    "Pass one platform only (redshift, snowflake, or tableau)."
)
MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_ERROR = (
    "Multiple connection_id values are not supported in a single API request. "
    "Pass one OvalEdge connection id."
)
MCP_SOURCE_SYSTEM_ACCESS_MULTI_OBJECT_TYPE_ERROR = (
    "Multiple object_type values are not supported in a single API request. "
    "Pass one RDAM object level (database, schema, table, column, project, or report)."
)
MCP_SOURCE_SYSTEM_USERNAME_REQUIRED_ERROR = (
    "Query parameter username is required for user_to_objects."
)
MCP_SOURCE_SYSTEM_OBJECT_PATH_REQUIRED_ERROR = (
    "Query parameter object_path is required for object_to_users (exact scope)."
)
MCP_SOURCE_SYSTEM_OBJECT_TYPE_REQUIRED_ERROR = (
    "Query parameter objectType is required whenever objectPath is set "
    "(database, schema, table, column, project, or report)."
)
MCP_SOURCE_SYSTEM_DESCENDANTS_CONNECTION_REQUIRED_ERROR = (
    "Query parameter connectionId is required when objectPath is omitted with "
    "scope_mode=descendants."
)

# asset-explorer query params (GET /api/v1/mcp/asset-explorer).
# Some OvalEdge builds return HTTP 500 when limit is very high (e.g. >= 95 on localhost).
MCP_SEARCH_CATALOG_MAX_LIMIT = 50
MCP_SEARCH_CONTEXT_QUERY_PARAM = "contextQuery"
# Lexical search — each value is a JSON array string on the wire.
MCP_SEARCH_TERMS_PARAM = "searchTerms"
MCP_SEARCH_TAGS_PARAM = "tags"
MCP_SEARCH_GLOSSARY_TERMS_PARAM = "terms"
MCP_SEARCH_CUSTOM_FIELDS_PARAM = "customFields"
MCP_SEARCH_DATA_PRODUCTS_PARAM = "dataProducts"
MCP_SEARCH_CLASSIFICATIONS_PARAM = "classifications"
MCP_SEARCH_DOMAIN_ID_PARAM = "domainId"
MCP_SEARCH_DOMAIN_NAME_PARAM = "domainName"
MCP_SEARCH_CATEGORY_ID_PARAM = "categoryId"
MCP_SEARCH_CATEGORY_NAME_PARAM = "categoryName"
MCP_SEARCH_SUBCATEGORY_ID_PARAM = "subcategoryId"
MCP_SEARCH_SUBCATEGORY_NAME_PARAM = "subcategoryName"
MCP_SEARCH_CRITICAL_DATA_ELEMENT_PARAM = "criticalDataElement"
MCP_SEARCH_SERVER_TYPE_PARAM = "serverType"

# connectionInfo.serverType values (OvalEdge connector types).
MCP_SERVER_TYPES = frozenset(
    {
        "allscripts",
        "api",
        "Athena",
        "awsDynamoDb",
        "awsappflow",
        "adl",
        "azuredevops",
        "azuredevopsrepo",
        "bigquery",
        "box",
        "cassandra",
        "clickhouse",
        "cloudera_navigator",
        "db2",
        "db2as400",
        "db2odbc",
        "denodo",
        "dremio",
        "dsefs",
        "informix",
        "elasticSearch",
        "elasticSearchOnPremise",
        "esri",
        "eventhub",
        "gcs",
        "github",
        "githubfiles",
        "googledrive",
        "greenplum",
        "greenhouse",
        "hbase",
        "hdfs",
        "hive",
        "qubolehive",
        "ibmcognos",
        "impala",
        "kafka",
        "linux",
        "looker",
        "manual",
        "mongodb",
        "mysql",
        "mariadb",
        "mavenlink",
        "microstrategy",
        "nfs",
        "onedrive",
        "oracle",
        "oracleservicecloud",
        "postgres",
        "powerbi",
        "qlikview",
        "qlik sense",
        "redshift",
        "s3",
        "sapbods",
        "sapbo",
        "sapsuccessfactors",
        "sftp",
        "sisense",
        "sqlserver",
        "ssas",
        "ssas_onprem",
        "ssis",
        "ssrs",
        "salesforce",
        "sapbo_universe",
        "saptables",
        "sharepoint",
        "snowflake",
        "spline",
        "sigma",
        "tableau",
        "teradata",
        "vertica",
        "other",
        "odbcsqlserver",
        "exasol",
        "adf",
        "adb",
        "airflow",
        "dbt",
        "azuresqlmanagedinstance",
        "azuresynapse",
        "couchdb",
        "saphana",
        "domo",
        "quickbase",
        "atlas",
        "DeltaLake",
        "alteryx",
        "talend",
        "matillion",
        "InterSystemsCache",
        "MSAccess",
        "arangodb",
        "pentaho",
        "awsglueetl",
        "ODataExt",
        "netsuitecrm",
        "informatica_powercenter",
        "informatica_ics",
        "informatica_bdm",
        "hubspot",
        "dynamics365",
        "dynamics365reports",
        "documentdb",
        "cosmosdb",
        "okta",
        "azuread",
        "avm",
        "ldap",
        "DELLBOOMI",
        "secretsmanager",
        "hashicorp",
        "webfocus",
        "couchbase",
        "workday",
        "hopsworks",
        "ADP",
        "structuredfileconnector",
        "azurekeyvault",
        "dbtcore",
        "cifs",
        "erwincsvimport",
        "gitlab",
        "zendesk",
        "schemaregistry",
        "azureml",
        "oraclefusionhcm",
        "sybasease",
        "salesforcereports",
        "datapipeline",
        "fme",
        "db2zos",
        "sybaseiq",
        "datastage",
        "apachepulsar",
        "netsuitecrmjdbc",
        "quicksight",
        "awsdms",
        "oraclebi",
        "obieerpd",
        "obieepublisher",
        "awsaurora",
        "dremioiceberg",
        "filecloud",
        "obieeoas",
        "cartovista",
        "oracleebstable",
        "qliktalend",
        "googleclouddatafusion",
        "oracleanalytics",
        "akamaiidentitycloud",
        "sapanalyticscloud",
        "salesforcecommercecloud",
        "microstrategycloud",
        "quickbooks-desktop",
        "quickbooks-online",
        "tally",
    }
)
# Case-insensitive lookup → canonical serverType value.
MCP_SERVER_TYPES_BY_LOWER: dict[str, str] = {v.lower(): v for v in MCP_SERVER_TYPES}

# ── MCP resource URI templates (FastMCP @resource) ───────────────
MCP_RESOURCE_CATALOG_TABLE = "ovaledge://catalog/table/{object_id}"
MCP_RESOURCE_CATALOG_FILE = "ovaledge://catalog/file/{object_id}"
MCP_RESOURCE_GOVERNANCE_GLOSSARY_TERM = "ovaledge://governance/glossary-term/{object_id}"
MCP_RESOURCE_GOVERNANCE_DATA_STORY = "ovaledge://governance/data-story/{object_id}"
MCP_RESOURCE_GOVERNANCE_TAG = "ovaledge://governance/tag/{object_id}"

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

# ── AUTH_MODE=remote (OAuth) per-request validation cache ────────
# Bounds the in-process cache of validated access-token claims so repeated MCP calls
# in a short burst do not re-introspect / re-verify on every request. TTL is always
# capped by the token's own ``exp`` (minus the leeway below); see OAUTH validation cache
# TTL setting in server.config.
OAUTH_VALIDATION_CACHE_MAX_ENTRIES = 10_000
OAUTH_VALIDATION_REFRESH_LEEWAY_SECONDS = 30
NEGATIVE_CREDENTIALS_CACHE_TTL_SECONDS = 30
NEGATIVE_CREDENTIALS_CACHE_MAX_ENTRIES = 10_000
CREDENTIALS_CACHE_POST_EXP_GRACE_SECONDS = 0
CREDENTIALS_HEADER_MAX_LEN = 2048
CREDENTIALS_COMBINED_MAX_LEN = (
    2 * CREDENTIALS_HEADER_MAX_LEN + len(CREDENTIALS_COMBINED_SEPARATOR)
)

# assess_cde_dq — must match backend McpDqApplicableObjectTypes.
MCP_DQ_APPLICABLE_OBJECT_TYPES = frozenset(
    {"oetable", "oecolumn", "oefile", "oefilecolumn"}
)
MCP_DQ_APPLICABLE_OBJECT_TYPES_DOC = ", ".join(
    sorted(MCP_DQ_APPLICABLE_OBJECT_TYPES)
)
MCP_DQ_OBJECT_TYPE_ALIASES: dict[str, str] = {
    "table": "oetable",
    "oetable": "oetable",
    "column": "oecolumn",
    "tablecolumn": "oecolumn",
    "table_column": "oecolumn",
    "oecolumn": "oecolumn",
    "file": "oefile",
    "oefile": "oefile",
    "filecolumn": "oefilecolumn",
    "file_column": "oefilecolumn",
    "oefilecolumn": "oefilecolumn",
}
MCP_DQ_ASSESS_LIMIT_DEFAULT = 50
MCP_DQ_ASSESS_LIMIT_MAX = 100
MCP_PATH_LOOKUP_DQ_RULES = "/api/v1/mcp/lookup-dq-rules"
MCP_PATH_ASSESS_CDE_DQ = "/api/v1/mcp/dq-intelligence/assess-cde"
MCP_PATH_ASSOCIATE_DQ_RULE_OBJECTS = "/api/v1/mcp/dq-intelligence/associate-rule-objects"
MCP_PATH_CREATE_DQ_RULES = "/api/v1/mcp/dq-intelligence/create-rules"
MCP_PATH_GENERATE_DQ_QUERIES = "/api/v1/mcp/dq-intelligence/generate-queries"
MCP_PATH_VALIDATE_DQ_QUERIES = "/api/v1/mcp/dq-intelligence/validate-queries"
MCP_PATH_CREATE_SQL_DQ_RULE = "/api/v1/mcp/dq-intelligence/create-sql-rule"
