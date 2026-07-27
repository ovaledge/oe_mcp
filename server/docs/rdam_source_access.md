# RDAM native source access (`source_system_access`)

Deep routing reference for **`source_system_access`** — native Redshift, Snowflake, and Tableau grants harvested in RDAM SQL metadata. For workflow steps and a parameter cheat sheet, see [mcp_workflows](mcp_workflows#native-source-access-rdam). For DAA enforcement, see [governance](governance#data-access-admin-daa).

## Why this tool exists

`get_user_object_access` resolves effective access at the OvalEdge **catalog permission** layer. There is no equivalent for access that exists **natively in the source systems** — Redshift, Snowflake, and Tableau — independent of OvalEdge grants. Customers need answers like "What tables can this service account actually query in Redshift?" or "Which users have native access to this table?" without navigating each source manually.

| | get_user_object_access (catalog) | source_system_access (native RDAM) |
|---|---|---|
| Access layer | OvalEdge catalog permissions | Native source-system grants |
| Grant mechanisms | OvalEdge user grants + OvalEdge roles | Redshift (direct / group / role), Snowflake (role), Tableau (direct / group) |
| Permission model | metadata-read/write + data permission levels | Native privileges (SELECT, INSERT, ALL, …) |
| Object scope | All OvalEdge asset types | RS/SF database/schema/table/column; Tableau project/report |

## No catalog / Elasticsearch fallback

`source_system_access` reads RDAM SQL metadata only. Never call `asset_explorer`, `asset_details`, or other catalog tools as a substitute when RDAM returns empty grants, 4xx/5xx, not-found, or not-harvested — catalog search cannot answer native Redshift/Snowflake/Tableau grants. Report the RDAM result (or API error) and suggest RDAM harvest, DAA, object_path / object_type, or native SQL (e.g. Snowflake `SHOW GRANTS`) — do not invoke catalog search.

## Mandatory API fields

**Mandatory API fields:** `source_system`, `query_direction` — infer `query_direction` from the user's question.

- **browse:** `connection_id` and `object_type` required; `object_path` is optional parent scope.
- **user_to_objects:** `username` required.
- **user_to_objects (scope_mode=descendants):** `username`, `object_path`, and `object_type` required; returns grants at the scope level and descendants (e.g. schema → tables/columns).
- **object_to_users (exact):** `object_path` and `object_type` required.
- **object_to_users (scope_mode=descendants):** `object_type` required; `object_path` or `connection_id` (connector-wide rollup when path omitted).
- **Whenever `object_path` is set:** `object_type` required (do not infer from dot segments).
- **Single value only:** `source_system`, `object_type`, `connection_id`.
- **Multiple values allowed:** `username` (user_to_objects), `object_path`.

Do not guess `connection_id`, `object_type`, or `object_path` — ask the user, then retry.

## Java backend

**Java backend (McpSourceSystemAccessReadService):** reads all harvested native grants from RDAM MySQL metadata tables (`rdam_*privilege`) — includes disabled rows and all roles (custom and built-in) without system/remote filtering. MCP returns the Java response as-is.

## RDAM privilege map

**RDAM privilege map** (harvested native grants in OvalEdge SQL metadata tables — not Elasticsearch, not OvalEdge catalog):

**Redshift / Snowflake** — `object_type` selects which RDAM metadata table to query:

| object_type | RDAM metadata table |
|-------------|---------------------|
| database | `rdam_dbprivilege` |
| schema | `rdam_schemaprivilege` |
| table | `rdam_tableprivilege` |
| column | `rdam_columnprivilege` (Redshift only; `include_columns=true`) |

**Tableau** — no database/schema/table/column objects; BI assets are **project** or **report** only:

| object_type | RDAM metadata table |
|-------------|---------------------|
| project | `rdam_reportgroup_privilege` |
| report | `rdam_report_privilege` |
| group expansion | `rdam_usergroup` (site-group membership for indirect grants) |

## object_path formats

**object_path** formats (Redshift/Snowflake; dot-separated):

- Optional OvalEdge **connection name** prefix when multiple connections share a source type: `connectionName.dbName` (e.g. `snowflake.BUSINESS`), then `connectionName.dbName.schema`, `connectionName.dbName.schema.table`, `connectionName.dbName.schema.table.column` (Redshift columns only, with `include_columns=true`).
- Without connection prefix (prefer **connection_id** to scope instead): `dbName` (database), `dbName.schema`, `dbName.schema.table` (e.g. `BUSINESS.BANKING.ALERTS`), `dbName.schema.table.column`.
- Partial names (e.g. table `ALERTS`, database `BUSINESS`) are allowed; the API may return **matchCandidates** — use a full path from candidates or `resolve_all_matches=true`.
- Tableau project: `Project Name`; report: `Project/Report Name`.

### RDAM path + object_type matrix (Redshift/Snowflake)

Scope with **`connection_id`** (preferred) or optional `connectionName.` prefix on `object_path` when names collide. Wire to Java as `objectPath` + `objectType` (camelCase). `fully_qualified_name` is an alias for `object_path` when the user or catalog gives a dotted FQN.

| Level | fullyQualifiedName / objectPath | object_type |
|-------|--------------------------------|-------------|
| Connector | — (pass `connection_id` only) | — |
| Database | `dbName`, `connectionName.dbName` | `database` |
| Schema | `dbName.schemaName`, `schemaName` | `schema` |
| Table | `dbName.schemaName.tableName`, `schemaName.tableName`, `tableName` | `table` |
| Column | `dbName.schemaName.tableName.columnName`, `schemaName.tableName.columnName`, `tableName.columnName`, `columnName` | `column` |

**source_system_access (browse):** `object_path` is the **parent** scope; `object_type` is the **child level to list** — omit parent to list databases; `dbName` + `schema` lists schemas; `dbName.schemaName` + `table` lists tables; `dbName.schemaName.tableName` + `column` lists columns.

## object_type

**object_type** (required): RDAM native object level — column, database, project, report, schema, table, all. Sent to the API as `objectType`. Always pass explicitly (do not rely on `.` segment count alone). Examples: `object_path=SNOWFLAKE.ALERT` + `object_type=schema`; `object_path=BUSINESS` + `object_type=database`; `object_path=BUSINESS.BANKING.ACCOUNTSCHEDULE` + `object_type=table`; Tableau report `Project/Report` + `object_type=report`. Catalog aliases accepted: `oeschema`→schema, `oetable`→table, `oecolumn`→column.

**Parent hierarchy — object_to_users only (Redshift/Snowflake):** `column` includes column + table + schema + database; `table` includes table + schema + database; `schema` includes schema + database; `database` is database only. **user_to_objects** returns grants at the requested `object_type` level only — no ancestor levels.

## Access grant models by source system

Each grant row includes `grant_mechanism` so the bot can explain lineage.

**Redshift** — three mechanisms, all supported:

- **direct** — grant to user
- **group** — grant to a group → user is a member of that group (see `contributing_group`)
- **role** — grant to a role → role is assigned to the user (see `contributing_role`)

**Snowflake** — single mechanism:

- **role** — grant to a role → role is assigned to the user (no direct user grants, no groups)

**Tableau** — two mechanisms:

- **direct** — grant to a user or service account on a project/report
- **group** — grant to a site group → user is a member (`contributing_group`; expanded via `rdam_usergroup`)

## Agent routing rules

- "What can **user X** access?" / "What permissions does **RACHEL** have?" → `user_to_objects` with `username` = that user only. Present **only that user's** grants from the response — never call `object_to_users` and list all principals.
- "Who has access to **object Y**?** → `object_to_users` with `object_path` + `object_type`.

### connection_id

**connection_id:** OvalEdge connector id from the user when they provide it. **Do not probe, enumerate, or discover** connection ids (no scanning id ranges, no catalog search, no inferring from defaults). Omit when unknown and ask the user for the connector id.

### object_path scope (user_to_objects)

You may infer `object_type` when the user names a level (e.g. "tables" → `table`, "schemas" → `schema`). **Never guess a specific table path** from test data or prior calls.

- "What **tables** can user X access?" with `connection_id` → **all tables on that connector**: `object_type=table`, **omit `object_path`**. Do not ask for a database/schema unless the user narrows scope.
- Narrower table listing: `object_type=table`, `object_path=dbName.schema` when the user names a schema; `object_path=dbName` when they name a database only.
- Single table: `object_type=table`, `object_path=dbName.schema.table` — only when the user named that table (or confirmed schema after disambiguation).
- For non-table levels (`schema`, `database`, …), `object_path` is always required. Do not report "no access" from a guessed table path when the user asked for all tables.

### username matching

**username matching (user_to_objects):** exact remote login only — **case-insensitive**, not SQL `LIKE` / substring / fuzzy search. Pass the name the user gave (e.g. `SIRISHA`); do not invent variants (`sirisha_rdam`, `sirisha_sb`, …), catalog-search the name, or scan principals with partial matches.

### Table schema disambiguation

**Table schema disambiguation (object_to_users + object_type=table):** When the user names a table without a full `dbName.schema.table` path, pass only what they gave (table name, or `dbName.table`) — **never invent a schema** (public, sakila, automation, …).

- If the response has `ambiguousMatch=true`, `requiresSchemaSelection=true`, or `matchCandidates` with multiple entries, **stop and ask the user which schema** holds the table. List schema names or full paths from `matchCandidates` / `advisoryMessage`, wait for their choice, then retry with `object_path=dbName.schema.table`.
- Do not set `resolve_all_matches=true` unless the user explicitly wants combined access across every match.
- Do not present schema/database parent grants as table access when the user did not specify a schema and table-level grants are missing or ambiguous.

### object_name

**object_name** (optional): bare table or report name when scope is in `object_path`. Composed before the API call: `object_path=prod_db` + `object_name=orders` → `prod_db.orders`; `object_path=prod_db.public` + `object_name=orders` → `prod_db.public.orders`; `object_name=transactions` alone → `transactions`. Use with `object_type=table`.

**Prompt parsing:** split database/schema scope from the table name — "orders table in prod_db" → `object_path=prod_db`, `object_name=orders`; "who can access `BUSINESS.BANKING.ORDERS`" → `object_path=BUSINESS.BANKING.ORDERS` or `object_path=BUSINESS.BANKING`, `object_name=ORDERS`; bare "table ORDERS" / "ORDERS" → `object_name=ORDERS` (or `object_path=ORDERS`) with `object_type=table`. Quotes, backticks, and trailing punctuation are stripped. When multiple schemas match, wait for the user to pick one before retrying with `dbName.schema.table`.

### privileges filter

**privileges** (optional): post-filter response grants to rows whose native privilege list includes any value you pass (e.g. `INSERT`, `UPDATE` for write-access checks). Case-insensitive; does not change the API query.

### Multiple connections

When the response spans more than one `connectionId` and you did not pass `connection_id`, tell the user and ask for `connection_id` plus a narrower `object_path` / `object_name` for best results — do not probe or discover connection ids.

### Sample routing

**Sample routing (infer `query_direction`; only `source_system` + `query_direction` are mandatory):**

1. "What Redshift **tables** can svc_analytics access, and how was that granted?" → `user_to_objects`, `username=svc_analytics`, `object_type=table`. Present table grants only; explain `grant_mechanism`, `contributing_role`, `contributing_group`.
2. "Who has access to the **orders** table in prod_db in Redshift?" → `object_to_users`, `object_type=table`, `object_path=prod_db`, `object_name=orders` (or full `prod_db.schema.orders` when schema is known).
3. "What can john.doe query in Snowflake? Which **roles** give him access?" → `user_to_objects`, `username=john.doe`, `object_type=all` (every database/schema/table level). Group by `contributing_role`.
4. "Does svc_etl have **write** access to the transactions table in Redshift?" → `user_to_objects`, `username=svc_etl`, `object_type=table`, `object_name=transactions`, `privileges=["INSERT","UPDATE","DELETE"]`; answer yes/no from filtered rows.

When the user gives `username` but not `connection_id`, `object_type`, or `object_path`, call the tool with what you have — do not infer object level from path segment count or discover connector ids; ask the user for missing context if the API response is insufficient.

## Snowflake built-in objects

- Always set `object_type` with `object_path` — e.g. `SNOWFLAKE.ALERT` + `object_type=schema` (built-in **schema** `ALERT` in database `SNOWFLAKE`).
- Without `object_type`, the API may infer level from `.` segment count only: `ALERT` (one segment) → database; `SNOWFLAKE.ALERT` (two) → schema.
- Do not confuse schema `ALERT` with table `ALERTS` (`object_type=table`).
- Built-in `SNOWFLAKE.*` schemas may be missing from RDAM harvest; grants are often via Snowflake database roles (e.g. `SNOWFLAKE.ALERT_VIEWER`) — not in catalog/RDAM. If RDAM has no rows, say so; do not fall back to catalog search.

## Partial object_path

When `object_path` is partial, `object_type` still disambiguates the RDAM level (e.g. `schemaName` + `object_type=schema`, `tableName` + `object_type=table`, `columnName` + `object_type=column`). For tables, a full path is `dbName.schema.table` (three dot segments).

Tableau: `object_type=project` vs `report` (path uses `/` for reports). Redshift/Snowflake segment-count hints when `object_type` omitted on the API: `BUSINESS` = database, `SNOWFLAKE.ALERT` = schema, `BUSINESS.BANKING.ALERTS` = table.

**Database paths:** for `object_type=database` and a single-segment path (e.g. `IBIS_UDFS`, `BUSINESS`), the backend must resolve from `rdam_dbprivilege` without requiring a catalog hit. If resolution returns not-found but the database exists in Snowflake, verify crawl/RDAM harvest — uncrawled databases are a backend resolution bug when RDAM rows exist.
