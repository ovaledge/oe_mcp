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
TOOL_METADATA_CHANGES_BETWEEN_CRAWLS = "metadata_changes_between_crawls"
TOOL_LOOKUP_GLOSSARY_TERM = "lookup_glossary_term"
TOOL_CREATE_GLOSSARY_TERM = "create_glossary_term"
TOOL_LOOKUP_TAGS = "lookup_tags"
TOOL_CREATE_TAG = "create_tag"
TOOL_LOOKUP_DATASTORY = "lookup_datastory"
TOOL_SEARCH_DOCS = "search_platform_docs"
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
MCP_PATH_SEARCH_CATALOG = "/api/v1/mcp/search-catalog"
MCP_PATH_OBJECT_DETAILS = "/api/v1/mcp/object-details"
MCP_PATH_COLUMN_PROFILE = "/api/v1/mcp/column-profile"
MCP_PATH_ENTITY_RELATIONSHIPS = "/api/v1/mcp/entity-relationships"
MCP_PATH_LINEAGE = "/api/v1/mcp/lineage"
MCP_PATH_METADATA_CHANGES_BETWEEN_CRAWLS = (
    "/api/v1/mcp/metadata-changes-between-crawls"
)
MCP_PATH_GLOSSARY_TERMS = "/api/v1/mcp/glossary-terms"
MCP_PATH_DOMAIN_METADATA = "/api/v1/mcp/domain-metadata"
# termCreationTemplate searchOn values (GlobalDomainActivity).
MCP_DOMAIN_METADATA_SEARCH_ON = frozenset({"oeglobaldomain", "category", "subcategory"})
MCP_DOMAIN_METADATA_SIZE_DEFAULT = 100
MCP_DOMAIN_METADATA_SIZE_MAX = 500
# In-app glossary term route (matches AppConstants.NAV_BUSINESS_GLOSSARY_ID).
NAV_GLOSSARY_TERM_HASH = "#nav/glossary?id="
MCP_PATH_TAGS = "/api/v1/mcp/tags"
MCP_PATH_TAGS_CREATE_OPTIONS = "/api/v1/mcp/tags/create-options"
MCP_PATH_TAGS_PARENT_OPTIONS = "/api/v1/mcp/tags/parent-options"
MCP_PATH_SEARCH_PLATFORM_DOCS = "/api/v1/mcp/search-platform-docs"
MCP_PATH_SOURCE_SYSTEM_ACCESS = "/api/v1/mcp/source-system-access"
MCP_PATH_GET_USER_OBJECT_ACCESS = "/api/v1/mcp/get-user-object-access"
MCP_PATH_LOOKUP_DATASTORY = "/api/v1/mcp/lookup-datastory"

# Secure-mode create_tag wizard phases (matches OvalEdge UI).
SELECTION_PHASE_MASTER_REQUIRED = "MASTER_REQUIRED"
SELECTION_PHASE_PARENT_OPTIONAL = "PARENT_OPTIONAL"
# create_tag guidance (not an error — tag not created yet).
STATUS_AWAITING_USER_SELECTION = "awaiting_user_selection"

MCP_DAA_SCOPE_DOC = (
    "**Data Access Admin (DAA)** — enforced server-side on this endpoint (same as DAM UI):\n"
"- **Instance Data Access Admin:** RDAM instance roles; "
"access to connectors on that instance.\n"
    "- **Connector Data Access Admin:** roles on one connection only.\n"
    "The API returns RDAM no-access if the caller lacks Connector DAA on the connection "
    "(or Instance DAA on its parent instance). No separate DAA check endpoint is required.\n"
    "**DAM object scope:** grant rows are limited to databases/schemas/tables/columns visible in "
    "DAM (active catalog objects with RDAM crawl — same as OETP RDAM browse). Harvested privileges "
    "for objects not in DAM (e.g. uncrawled schemas) are excluded."
)

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

# objectType values for update_governance_roles that are NOT in search_catalog_assets.
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
    "only. Never call `search_catalog_assets`, `catalog_asset_details`, or other catalog "
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
MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS_DOC = (
    "native, remote, source system access, source system, source, "
    "data access management, DAM"
)
MCP_ACCESS_DISAMBIGUATION_INSTRUCTION_DOC = (
    "Ambiguous who-has-access: disambiguate via resolve_object_access; "
    "do not call access tools until user picks. "
    "Snowflake/Redshift/Tableau alone are not native signals."
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
    "Your question does not mention native/remote/DAM/source-system access.\n\n"
    "**Which do you want?**\n"
    "1. **Native source access** — database/BI grants from Redshift, Snowflake, or Tableau\n"
    "2. **OvalEdge catalog ACL** — permissions inside OvalEdge on a catalog asset\n\n"
    "Reply with **1** or **2**, then I will call the matching tool."
)
MCP_ACCESS_DISAMBIGUATION_RULE_DOC = (
    "For who-has-access / permission questions: if the user question includes none of these "
    "signals (case-insensitive): "
    + MCP_ACCESS_NATIVE_SIGNAL_KEYWORDS_DOC
    + " — do **not** call source_system_access or get_user_object_access; show the "
    "disambiguation message and wait for the user to pick **1** (native) or **2** (catalog ACL). "
    "Naming Snowflake/Redshift/Tableau alone is not a native signal — still disambiguate. "
    "Workflow prompt: resolve_object_access."
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
MCP_SOURCE_SYSTEM_ACCESS_REQUIRED_DOC = (
    "**Mandatory API fields:** `source_system`, `query_direction` — infer `query_direction` "
    "from the user's question.\n"
    "**browse:** `connection_id` and `object_type` required; `object_path` is optional parent "
    "scope.\n"
    "**user_to_objects:** `username` required.\n"
    "**user_to_objects (scope_mode=descendants):** `username`, `object_path`, and `object_type` "
    "required; returns grants at the scope level and descendants (e.g. schema → tables/columns).\n"
    "**object_to_users (exact):** `object_path` and `object_type` required.\n"
    "**object_to_users (scope_mode=descendants):** `object_type` required; `object_path` or "
    "`connection_id` (connector-wide rollup when path omitted).\n"
    "**Whenever `object_path` is set:** `object_type` required (do not infer from dot segments).\n"
    "**Single value only:** `source_system`, `object_type`, `connection_id`.\n"
    "**Multiple values allowed:** `username` (user_to_objects), `object_path`.\n"
    "Do not guess `connection_id`, `object_type`, or `object_path` — ask the user, then retry."
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
MCP_SOURCE_SYSTEM_ACCESS_CONNECTION_ID_DOC = (
    "**connection_id:** OvalEdge connector id from the user when they provide it. **Do not probe, "
    "enumerate, or discover** connection ids (no scanning id ranges, no catalog search, no "
    "inferring from defaults). Omit when unknown and ask the user for the connector id."
)
MCP_SOURCE_SYSTEM_ACCESS_USERNAME_MATCH_DOC = (
    "**username matching (user_to_objects):** exact remote login only — **case-insensitive**, "
    "not SQL `LIKE` / substring / fuzzy search. Pass the name the user gave (e.g. `SIRISHA`); "
    "do not invent variants (`sirisha_rdam`, `sirisha_sb`, …), catalog-search the name, or "
    "scan principals with partial matches."
)
MCP_SOURCE_SYSTEM_ACCESS_OBJECT_PATH_SCOPE_DOC = (
    "**object_path scope (user_to_objects):** You may infer `object_type` when the user names a "
    "level (e.g. \"tables\" → `table`, \"schemas\" → `schema`). **Never guess a specific table "
    "path** from test data or prior calls.\n"
    "- \"What **tables** can user X access?\" with `connection_id` → **all tables on that "
    "connector**: `object_type=table`, **omit `object_path`**. Do not ask for a database/schema "
    "unless the user narrows scope.\n"
    "- Narrower table listing: `object_type=table`, `object_path=dbName.schema` when the user "
    "names a schema; `object_path=dbName` when they name a database only.\n"
    "- Single table: `object_type=table`, `object_path=dbName.schema.table` — only when the user "
    "named that table (or confirmed schema after disambiguation).\n"
    "- For non-table levels (`schema`, `database`, …), `object_path` is always required. Do not "
    "report \"no access\" from a guessed table path when the user asked for all tables."
)
MCP_SOURCE_SYSTEM_ACCESS_TABLE_SCHEMA_DISAMBIGUATION_DOC = (
    "**Table schema disambiguation (object_to_users + object_type=table):** When the user names "
    "a table without a full `dbName.schema.table` path, pass only what they gave (table name, or "
    "`dbName.table`) — **never invent a schema** (public, sakila, automation, …).\n"
    "- If the response has `ambiguousMatch=true`, `requiresSchemaSelection=true`, or "
    "`matchCandidates` with multiple entries, **stop and ask the user which schema** holds the "
    "table. List schema names or full paths from `matchCandidates` / `advisoryMessage`, wait "
    "for their choice, then retry with `object_path=dbName.schema.table`.\n"
    "- Do not set `resolve_all_matches=true` unless the user explicitly wants combined access "
    "across every match.\n"
    "- Do not present schema/database parent grants as table access when the user did not "
    "specify a schema and table-level grants are missing or ambiguous."
)
MCP_SOURCE_SYSTEM_ACCESS_OBJECT_NAME_DOC = (
    "**object_name** (optional): bare table or report name when scope is in `object_path`. "
    "Composed before the API call: `object_path=prod_db` + `object_name=orders` → "
    "`prod_db.orders`; "
    "`object_path=prod_db.public` + `object_name=orders` → `prod_db.public.orders`; "
    "`object_name=transactions` alone → `transactions`. Use with `object_type=table`.\n"
    "**Prompt parsing:** split database/schema scope from the table name — "
    "\"orders table in prod_db\" → `object_path=prod_db`, `object_name=orders`; "
    "\"who can access `BUSINESS.BANKING.ORDERS`\" → `object_path=BUSINESS.BANKING.ORDERS` "
    "or `object_path=BUSINESS.BANKING`, `object_name=ORDERS`; "
    "bare \"table ORDERS\" / \"ORDERS\" → `object_name=ORDERS` (or `object_path=ORDERS`) "
    "with `object_type=table`. Quotes, backticks, and trailing punctuation are stripped. "
    "When multiple schemas match, wait for the user to pick one before retrying with "
    "`dbName.schema.table`."
)
MCP_SOURCE_SYSTEM_ACCESS_PRIVILEGES_FILTER_DOC = (
    "**privileges** (optional): post-filter response grants to rows whose native privilege list "
    "includes any value you pass (e.g. `INSERT`, `UPDATE` for write-access checks). "
    "Case-insensitive; does not change the API query."
)
MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_DOC = (
    "**Multiple connections:** when the response spans more than one `connectionId` and you did "
    "not pass `connection_id`, tell the user and ask for `connection_id` plus a narrower "
    "`object_path` / `object_name` for best results — do not probe or discover connection ids."
)
MCP_SOURCE_SYSTEM_ACCESS_SAMPLE_PROMPTS_DOC = (
    "**Sample routing (infer `query_direction`; only `source_system` + `query_direction` are "
    "mandatory):**\n"
    "1. \"What Redshift **tables** can svc_analytics access, and how was that granted?\" → "
    "`user_to_objects`, `username=svc_analytics`, `object_type=table`. Present table grants only; "
    "explain `grant_mechanism`, `contributing_role`, `contributing_group`.\n"
    "2. \"Who has access to the **orders** table in prod_db in Redshift?\" → `object_to_users`, "
    "`object_type=table`, `object_path=prod_db`, `object_name=orders` "
    "(or full `prod_db.schema.orders` "
    "when schema is known).\n"
    "3. \"What can john.doe query in Snowflake? Which **roles** give him access?\" → "
    "`user_to_objects`, `username=john.doe`, `object_type=all` "
    "(every database/schema/table level). "
    "Group by `contributing_role`.\n"
    "4. \"Does svc_etl have **write** access to the transactions table in Redshift?\" → "
    "`user_to_objects`, `username=svc_etl`, `object_type=table`, `object_name=transactions`, "
    "`privileges=[\"INSERT\",\"UPDATE\",\"DELETE\"]`; answer yes/no from filtered rows."
)
MCP_SOURCE_SYSTEM_ACCESS_AGENT_RULES_DOC = (
    "**Agent routing rules:**\n"
    "- \"What can **user X** access?\" / \"What permissions does **RACHEL** have?\" → "
    "`user_to_objects` with `username` = that user only. Present **only that user's** grants "
    "from the response — never call `object_to_users` and list all principals.\n"
    "- \"Who has access to **object Y**?\" → `object_to_users` with `object_path` + "
    "`object_type`.\n"
    + MCP_SOURCE_SYSTEM_ACCESS_CONNECTION_ID_DOC
    + "\n"
    + MCP_SOURCE_SYSTEM_ACCESS_OBJECT_PATH_SCOPE_DOC
    + "\n"
    + MCP_SOURCE_SYSTEM_ACCESS_USERNAME_MATCH_DOC
    + "\n"
    + MCP_SOURCE_SYSTEM_ACCESS_TABLE_SCHEMA_DISAMBIGUATION_DOC
    + "\n"
    + MCP_SOURCE_SYSTEM_ACCESS_OBJECT_NAME_DOC
    + "\n"
    + MCP_SOURCE_SYSTEM_ACCESS_PRIVILEGES_FILTER_DOC
    + "\n"
    + MCP_SOURCE_SYSTEM_ACCESS_MULTI_CONNECTION_DOC
    + "\n"
    + MCP_SOURCE_SYSTEM_ACCESS_SAMPLE_PROMPTS_DOC
    + "\n"
    "- When the user gives `username` but not `connection_id`, `object_type`, or `object_path`, "
    "call the tool with what you have — do not infer object level from path segment count or "
    "discover connector ids; ask the user for missing context if the API response is insufficient."
)
MCP_SNOWFLAKE_BUILTIN_OBJECTS_DOC = (
    "**Snowflake built-in objects:**\n"
    "- Always set `object_type` with `object_path` — e.g. `SNOWFLAKE.ALERT` + "
    "`object_type=schema` (built-in **schema** `ALERT` in database `SNOWFLAKE`).\n"
    "- Without `object_type`, the API may infer level from `.` segment count only: "
    "`ALERT` (one segment) → database; `SNOWFLAKE.ALERT` (two) → schema.\n"
    "- Do not confuse schema `ALERT` with table `ALERTS` (`object_type=table`).\n"
    "- Built-in `SNOWFLAKE.*` schemas may be missing from RDAM harvest; grants are often "
    "via Snowflake database roles (e.g. `SNOWFLAKE.ALERT_VIEWER`) — not in catalog/RDAM. "
    "If RDAM has no rows, say so; do not fall back to catalog search."
)
MCP_OBJECT_PATH_PARTIAL_DOC = (
    "When `object_path` is partial, `object_type` still disambiguates the RDAM level "
    "(e.g. `schemaName` + `object_type=schema`, `tableName` + `object_type=table`, "
    "`columnName` + `object_type=column`). "
    "For tables, a full path is `dbName.schema.table` (three dot segments). "
    + MCP_SOURCE_SYSTEM_ACCESS_TABLE_SCHEMA_DISAMBIGUATION_DOC
    + "\n"
    "Tableau: `object_type=project` vs `report` (path uses `/` for reports). "
    "Redshift/Snowflake segment-count hints when `object_type` omitted on the API: "
    "`BUSINESS` = database, `SNOWFLAKE.ALERT` = schema, `BUSINESS.BANKING.ALERTS` = table.\n"
    "**Database paths:** for `object_type=database` and a single-segment path (e.g. "
    "`IBIS_UDFS`, `BUSINESS`), the backend must resolve from `rdam_dbprivilege` without "
    "requiring a catalog hit. If resolution returns not-found but the database exists in "
    "Snowflake, verify crawl/RDAM harvest — uncrawled databases are a backend resolution "
    "bug when RDAM rows exist."
)

# search-catalog query params (GET /api/v1/mcp/search-catalog).
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
MCP_SEARCH_SUBCATEGORY_ID_PARAM = "subCategoryId"
MCP_SEARCH_SUBCATEGORY_NAME_PARAM = "subCategoryName"
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
