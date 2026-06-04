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
TOOL_UPDATE_GOVERNANCE_ROLES = "update_governance_roles"
TOOL_LOOKUP_DQ_RULE = "lookup_dq_rule"
TOOL_SOURCE_SYSTEM_ACCESS = "source_system_access"
TOOL_ASSESS_CDE_DQ = "assess_cde_dq"
TOOL_ASSOCIATE_DQ_RULE_OBJECTS = "associate_dq_rule_objects"
TOOL_CREATE_DQ_RULES = "create_dq_rules"

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
    "(or Instance DAA on its parent instance). No separate DAA check endpoint is required."
)

# Optional on glossary-terms and tags (Spring default 20).
MCP_GLOSSARY_TAGS_LIMIT_DEFAULT = 20
MCP_GLOSSARY_TAGS_LIMIT_MAX = 100
MCP_PATH_UPDATE_ASSET_DESCRIPTIONS = "/api/v1/mcp/update-asset-descriptions"
MCP_PATH_UPDATE_GOVERNANCE_ROLES = "/api/v1/mcp/update-governance-roles"

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
MCP_QUERY_DIRECTIONS = frozenset({"user_to_objects", "object_to_users"})
MCP_QUERY_DIRECTIONS_DOC = "user_to_objects | object_to_users"

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
    "- Tableau project: `Project Name`; report: `Project/Report Name`."
)
MCP_OBJECT_PATH_PARTIAL_DOC = (
    "Redshift/Snowflake: level is inferred by `.` segment count, optionally after a "
    "leading `connectionName.` prefix (e.g. `BUSINESS` = database, "
    "`snowflake.BUSINESS` = connection + database, `BUSINESS.BANKING.ALERTS` = table). "
    "Tableau: project vs report by `/`."
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
