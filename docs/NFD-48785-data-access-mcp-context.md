# NFD-48785 — `get_source_system_access` MCP tool

**Jira:** [NFD-48785](https://ovaledge.atlassian.net/browse/NFD-48785)

## Problem

`get_user_object_access` resolves **OvalEdge catalog** permissions. Customers (e.g. Twitch) need **native** grants in Redshift, Snowflake, and Tableau from OvalEdge-harvested metadata — without logging into each source.

## Solution

One MCP tool: **`get_source_system_access`**

| Layer | Tool / API |
|-------|------------|
| MCP client | `get_source_system_access` in `server/tools/data_access_management.py` |
| HTTP | `GET /api/v1/mcp/source-system-access` |
| Java | `McpSourceSystemAccessReadService` → `rdam_*privilege` tables (`source = Remote`) |

## vs `get_user_object_access`

| | `get_user_object_access` | `get_source_system_access` |
|--|--------------------------|----------------------------|
| Access layer | OvalEdge catalog ACL | Native source grants |
| Mechanisms | OE user grants + OE roles | Redshift direct/group/role; Snowflake role; Tableau direct |
| Privileges | metadata-read/write, data levels | SELECT, INSERT, ALL, … |
| Object scope | 17 OE asset types | RS/SF tables/schemas/(columns); Tableau projects/reports |

## Request parameters

| Parameter | Required | Values |
|-----------|----------|--------|
| `sourceSystem` | yes | `redshift`, `snowflake`, `tableau` |
| `queryDirection` | yes | `user_to_objects`, `object_to_users` |
| `username` | user_to_objects | Remote login / service account |
| `objectPath` | object_to_users | See formats below |
| `includeColumns` | no | Redshift only; default `false` |
| `connectionId` | no | Scope to one OvalEdge connection |

### `object_path` formats

**Redshift / Snowflake** (dot-separated):

| Pattern | Example | Level |
|---------|---------|-------|
| `dbName` | `BUSINESS` | database (partial if ambiguous) |
| `connectionName.dbName` | `snowflake.BUSINESS` | connection + database |
| `dbName.schema` | `BUSINESS.BANKING` | schema |
| `dbName.schema.table` | `BUSINESS.BANKING.ALERTS` | table |
| `dbName.schema.table.column` | _(Redshift only, `includeColumns=true`)_ | column |

Optional leading `connectionName.` disambiguates when multiple OvalEdge connections share a source type; otherwise pass `connectionId`.

**Tableau:** project `Project Name`; report `Executive/Revenue Dashboard`

## Response shape (`McpApiResult` → `data`)

```json
{
  "ok": true,
  "data": {
    "sourceSystem": "redshift",
    "queryDirection": "user_to_objects",
    "username": "svc_analytics",
    "grants": [
      {
        "objectPath": "prod_db.public.orders",
        "objectLevel": "table",
        "privileges": ["SELECT"],
        "grantMechanism": "role",
        "principalName": "svc_analytics",
        "contributingRole": "role_read_only",
        "contributingRoles": ["role_read_only", "role_analytics"],
        "connectionId": 42
      }
    ]
  }
}
```

`summary` counts rows in `grants` after merge (not distinct object paths). `byObjectLevel` always includes `database`, `schema`, `table`, `column` (0 when none); Tableau `project` / `report` appear as extra keys when present.

Partial `object_path` (**object_to_users**, or optional filter on **user_to_objects**): short names (`ALERTS`), `dbName`, or `connectionName.dbName` may match multiple catalog objects. Response sets `ambiguousMatch`, `matchCandidates`, and `advisoryMessage`. Pick one full path + `connectionId`, or pass `resolveAllMatches=true`. Up to 50 candidates.

`grantMechanism`: `direct` | `group` | `role` (Redshift may return multiple rows per object).

## Grant models (backend)

| Source | Mechanisms | Harvested tables |
|--------|------------|------------------|
| Redshift | direct, group (`rdam_usergroup`), role (`rdam_userrole`) | `rdam_tableprivilege`, `rdam_schemaprivilege`, `rdam_columnprivilege` |
| Snowflake | role only | same |
| Tableau | direct user on project/report | `rdam_folderprivilege` |

Filter: `source = 'Remote'` (native harvest only).

## Data Access Admin (Instance vs Connector DAA)

OvalEdge RDAM security assigns **Data Access Admin** roles at two levels (same as the DAM UI):

| Level | OvalEdge config | MCP check | Scope |
|-------|-----------------|-----------|--------|
| **Instance Data Access Admin** | Instance DAA roles on the RDAM instance | `userIsDaaForInstance` | All connectors/workspaces on that instance (per RDAM rules) |
| **Connector Data Access Admin** | Connector DAA roles on `connectioninfo` | `userIsDAAForConn` | That connection only |

**MCP API:** DAA is enforced inside `GET /v1/mcp/source-system-access` only (`McpSourceSystemAccessReadService` → `McpDamReadService.canQuerySourceSystemAccessForConnection` / `RdamValidationDao`). No separate DAM or DAA REST routes are required for MCP clients.

**MCP tool (oe_mcp):** `get_source_system_access` → that single endpoint.

## Errors

| Case | HTTP | Message |
|------|------|---------|
| Bad `sourceSystem` | 400 | Unsupported source_system |
| Bad direction | 400 | Unsupported query_direction |
| Missing identifier | 400 | username / object_path required |
| Unknown user | 400 | username not found in harvested metadata |
| Unknown object | 400 | object_path not found in harvested metadata |
| Not Instance/Connector DAA | 400 | RDAM no-access message (`RDAM_NO_ACCESS_ERROR_MSG`) |

## Sample prompts

| Question | Call |
|----------|------|
| What Redshift tables can svc_analytics access? | `user_to_objects`, `username=svc_analytics`, `sourceSystem=redshift` |
| Who can access prod_db.public.orders? | `object_to_users`, `objectPath=prod_db.public.orders` |
| Who can access BUSINESS database on snowflake conn? | `object_to_users`, `objectPath=snowflake.BUSINESS` or `BUSINESS` + `connectionId` |
| Snowflake roles for john.doe | `user_to_objects`, `username=john.doe`, `sourceSystem=snowflake` |
| Tableau report access | `object_to_users`, `objectPath=Executive/Revenue Dashboard`, `sourceSystem=tableau` |

## Repo layout

### oe_mcp (this repo)

- `server/tools/data_access_management.py` — MCP tool
- `server/constants.py` — `MCP_PATH_SOURCE_SYSTEM_ACCESS`
- `tests/tools/test_data_access_management.py`

### oasis_repo (backend)

- `oe-next-gen-commons/.../mcp/access/McpSourceSystemAccess*.java` — DTOs
- `oe-api/.../mcp/McpSourceSystemAccessReadService.java` — resolution logic
- `oe-api/.../mcp/McpApi.java` — REST endpoint
- `oe-api/.../mcp/McpApiService.java` — adapter

## Deploy / test

```bash
# oe_mcp
poetry run pytest tests/tools/test_data_access_management.py -q

# Manual (OvalEdge running, .env configured)
curl -G "http://127.0.0.1:8080/ovaledge/api/v1/mcp/source-system-access" \
  --data-urlencode "sourceSystem=redshift" \
  --data-urlencode "queryDirection=user_to_objects" \
  --data-urlencode "username=svc_analytics" \
  -H "Authorization: jwt <token>"
```

Restart Cursor MCP after backend deploy.

## Follow-ups

- Database-level privilege queries (`rdam_dbprivilege`)
- Tableau report-level join via `oechart` / `chart` tables
- Postman entry in `McpApi.postman_collection.json`
- Integration tests against seeded `oe-rdam` test SQL
