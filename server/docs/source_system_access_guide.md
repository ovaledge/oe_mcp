# Native source-system access (RDAM)

Use the **`source_system_access`** MCP tool — not `search_catalog_assets` — for Redshift, Snowflake, and Tableau **native** grants harvested into OvalEdge RDAM.

## When to use

| Question type | Tool |
|---------------|------|
| Who can SELECT in Redshift/Snowflake? Native roles/groups? | `source_system_access` |
| OvalEdge catalog ACL / metadata permissions | Catalog layer (not this tool) |

## Required parameters

- **source_system:** `redshift`, `snowflake`, or `tableau`
- **query_direction:** infer from the question — do not ask the user to pick
  - **user_to_objects** — “What can user X access?”
  - **object_to_users** — “Who has access to table Y?”

## Optional parameters

`username`, `object_path`, `object_name`, `object_type`, `connection_id`, `privileges`, `include_columns`, `resolve_all_matches`.

Pass only one value for `source_system`, `object_type`, and `connection_id` per call.

## Agent rules (summary)

1. **Never** fall back to `search_catalog_assets` when RDAM returns empty or errors.
2. **Do not discover** `connection_id` — ask the user when unknown.
3. **username** matching is exact remote login (case-insensitive), not fuzzy search.
4. “What **tables** can user X access?” with `connection_id` → `object_type=table`, **omit** `object_path`.
5. Table name without schema → if `matchCandidates` / `ambiguousMatch`, **stop** and ask which schema; then retry with `dbName.schema.table`.
6. **user_to_objects** → list only that user’s grants; never switch to `object_to_users` and list all principals.

## object_path formats (Redshift/Snowflake)

- `dbName`, `dbName.schema`, `dbName.schema.table`, `dbName.schema.table.column` (columns: Redshift + `include_columns=true`)
- Optional connection prefix: `connectionName.dbName.schema.table`
- Tableau: project `Project Name`; report `Project/Report Name`

## object_type

`database`, `schema`, `table`, `column`, `project`, `report`, or `all` (Snowflake user-wide). Catalog aliases: `oeschema`→schema, `oetable`→table, `oecolumn`→column.

**object_to_users** (RS/SF): column grants include parent table/schema/database; **user_to_objects** returns only the requested level.

## Grant mechanisms

- **Redshift:** direct | group | role (`contributing_group`, `contributing_role`)
- **Snowflake:** role only
- **Tableau:** direct | group

## Sample routing

1. “What Redshift tables can svc_analytics access?” → `user_to_objects`, `username=svc_analytics`, `object_type=table`
2. “Who has access to orders in prod_db?” → `object_to_users`, `object_type=table`, `object_path=prod_db`, `object_name=orders`
3. “What can john.doe query in Snowflake?” → `user_to_objects`, `username=john.doe`, `object_type=all`

## DAA scope

Caller must have Instance/Connector DAA for scoped connections. Read-only tool.

Workflow prompt: **`native_source_access`**.
