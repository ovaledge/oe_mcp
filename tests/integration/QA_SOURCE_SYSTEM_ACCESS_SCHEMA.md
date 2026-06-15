# QA matrix — Snowflake schema access (`source_system_access`)

Manual QA checklist for **“Who has access to `BUSINESS.BANKING` schema?”** and multi-connection
disambiguation. Requires backend deploy with RDAM-only schema resolution
(`McpSourceSystemAccessReadService` — schema path uses `rdam_schemaprivilege`, not `oeschema`).

**API:** `GET /api/v1/mcp/source-system-access`  
**MCP tool:** `source_system_access` with the same parameters (snake_case).

**MCP tool mandatory fields:** `source_system`, `query_direction` only (both directions).

**Optional:** `username` (user_to_objects), `object_path`, `object_type`, `connection_id`, and other flags.

**Single value only:** `source_system`, `object_type`, `connection_id` — multiple values return a
validation error. **Multiple allowed:** `username` (user_to_objects), `object_path`. Use
`database`, `schema`, `table`, `column` (Redshift), `project`, or `report` (Tableau). Example:
`SNOWFLAKE.ALERT` + `object_type=schema`.

## Prerequisites

| Item | Notes |
|------|--------|
| Caller is **Instance or Connector DAA** on every connection under test | Otherwise 400 RDAM no-access |
| RDAM harvest complete | Remote privilege rows in the matching RDAM **metadata** table — RS/SF: `rdam_dbprivilege`, `rdam_schemaprivilege`, `rdam_tableprivilege`, `rdam_columnprivilege` (column: Redshift only). Tableau: `rdam_reportgroup_privilege` (project), `rdam_report_privilege` (report) — no DB/schema/table objects |
| **DAM object scope** | API returns grants only for databases/schemas/tables/columns visible in DAM (active `oedatabase` / `oeschema` / `oetable` / `oecolumn` with `rdam_lastcrawldate` set — same as OETP RDAM browse). Schemas harvested in RDAM but not in DAM (e.g. `automation_schema`) must **not** appear. |
| **4 Snowflake connections** (QA scenario) | Each with schema `BUSINESS.BANKING` (or equivalent) and **different** role grants |
| Record connection ids | e.g. `1001`, `1002`, `1360`, `1400` — replace in examples below |
| JWT / local MCP credentials | See [README.md](README.md) |

### Suggested QA data shape (per connection)

| Connection | `connection_id` | Example difference |
|------------|-----------------|-------------------|
| snowflake-dev | 1001 | `ROLE_BANK_READER` → USAGE on schema |
| snowflake-qa | 1002 | `ROLE_BANK_WRITE` → USAGE on schema |
| snowflake-uat | 1360 | `ROLE_BANK_ADMIN` → USAGE on schema |
| snowflake-prod | 1400 | `ACCOUNTADMIN` → OWNERSHIP on schema |

Permissions should differ **per connection** so tests can prove scoping works.

---

## Path segment rules (reference)

**object_to_users** — parent grants are included (hierarchy):

| `object_path` | `object_type` | Grant levels returned |
|---------------|---------------|------------------------|
| `BUSINESS` | database | `database` only |
| `BUSINESS.BANKING` | schema | `schema` + `database` (no `table`) |
| `BUSINESS.BANKING.ACCOUNTS` | table | `table` + `schema` + `database` |

**user_to_objects** — exact `object_type` only (no ancestor levels). Example:
`object_type=database` returns only `database` grants for the user/path, not schema or table.

---

## Test cases

### TC-01 — Schema path, single connection (happy path)

**Question:** Who has access to `BUSINESS.BANKING` on connection 1360?

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "BUSINESS.BANKING",
  "object_type": "schema",
  "connection_id": 1360
}
```

| Check | Expected |
|-------|----------|
| HTTP / `ok` | 200, `ok: true` |
| `ambiguousMatch` | `false` or absent |
| `resolvedObjectPath` | `BUSINESS.BANKING` |
| `grants[].objectLevel` | Only `schema` and `database` |
| No table grants | No row with `objectPath` ending in `.ACCOUNTS` (or any 3rd segment) |
| `grants[].connectionId` | All `1360` |
| `grantMechanism` | `role` only (Snowflake) |
| `summary.byObjectLevel.table` | `0` |
| `summary.byObjectLevel.schema` | `> 0` |

**Pass example:** User `ABHISHEK` has `USAGE` on `BUSINESS.BANKING` via `ROLE_BANK_READER`; same or
other users have `USAGE` on `BUSINESS` at database level.

---

### TC-02 — Schema path without `connection_id` (all connections)

**Question:** Same schema name on 4 connections — what returns without scoping?

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "BUSINESS.BANKING",
  "object_type": "schema"
}
```

| Check | Expected |
|-------|----------|
| HTTP / `ok` | 200 |
| `ambiguousMatch` | `false` (full path resolves if schema exists on any connection) |
| `grants` | Rows from **multiple** `connectionId` values (up to 4) |
| Per-connection permissions | Differ by `connectionId` — QA verifies connection 1001 ≠ 1360 |
| `objectLevel` | Still only `schema` and `database` |

**Note:** Same `principalName` + same `contributingRole` + same `objectPath` on two connections may
merge privileges into one row. Prefer **TC-01** for strict per-connection validation.

---

### TC-03 — Schema path, each connection individually

Run **TC-01** four times with `connection_id` = 1001, 1002, 1360, 1400.

| Check | Expected |
|-------|----------|
| Grant sets differ | At least one principal or privilege difference across connections |
| Isolation | Grants from connection A never appear when `connection_id` is B |

---

### TC-04 — Partial path disambiguation (default)

**Question:** Ambiguous short name across connections.

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "BANKING",
  "object_type": "schema"
}
```

| Check | Expected |
|-------|----------|
| HTTP / `ok` | 200 |
| `ambiguousMatch` | `true` |
| `grants` | `[]` (empty) |
| `matchCandidates` | ≥ 2 entries (up to 4 in QA setup) |
| Each candidate | `connectionId`, `connectionName`, `objectPath`, `objectLevel: schema` |
| `advisoryMessage` | Present — instructs to pick full path + `connection_id` |

---

### TC-05 — Partial path, resolve all matches

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "BANKING",
  "object_type": "schema",
  "resolve_all_matches": true
}
```

| Check | Expected |
|-------|----------|
| HTTP / `ok` | 200 |
| `grants` | Non-empty — combined from all matched connections |
| `advisoryMessage` | Mentions count of resolved matches |
| `connectionId` on grants | Multiple distinct values |

---

### TC-06 — Case insensitivity

Repeat **TC-01** with:

```json
{ "object_path": "business.banking", "object_type": "schema", "connection_id": 1360 }
```

| Check | Expected |
|-------|----------|
| Result | Same grant set as TC-01 (case-insensitive match on RDAM `schemaname`) |

---

### TC-07 — Schema path must not 400 when RDAM has data

**Regression** for NFD-48785 / RDAM schema resolution bug.

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "BUSINESS.BANKING",
  "object_type": "schema",
  "connection_id": 1360
}
```

| Check | Expected |
|-------|----------|
| Error | **Must not** be `object_path was not found in harvested metadata` when table path works on same connection |
| Cross-check | TC-08 succeeds on same `connection_id` |

---

### TC-08 — Table path (sanity — RDAM data exists)

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "BUSINESS.BANKING.ACCOUNTS",
  "object_type": "table",
  "connection_id": 1360
}
```

| Check | Expected |
|-------|----------|
| HTTP / `ok` | 200 |
| `grants` | Non-empty |
| `summary.byObjectLevel.table` | `> 0` |

**Not a substitute for TC-01** — table path intentionally includes table-level grants.

---

### TC-09 — Wrong tool guard (catalog search)

**Question:** “Who has access to BUSINESS.BANKING schema?” must **not** be answered with
Never use `search_catalog_assets` for grant questions or as fallback when RDAM is empty/errors.
Use `source_system_access` only (RDAM SQL — no Elasticsearch).

| Check | Expected |
|-------|----------|
| Agent / tester | Calls `source_system_access`, not catalog search for grant questions |

---

## DAA errors vs “not found” (troubleshooting)

QA often reports **“DAA not found”** when the API returns one of two **different** 400 messages.
Read the exact message text before logging a DAA bug.

| API message | Meaning | Fix |
|-------------|---------|-----|
| `Sorry, you don't have access to this **connection**… DAA of this **connector**` | Caller is **not** Connector/Instance DAA for the `connection_id` passed | Assign Connector or Instance DAA in **Data Access Management** for that Snowflake connection; use the **same OvalEdge user** as the MCP JWT |
| `Sorry, you don't have access to this **instance**… DAA of this **instance**` | Same denial when no `connection_id` or caller lacks Instance DAA on the parent instance | Assign Instance DAA on the RDAM instance, or pass a `connection_id` where the user is Connector DAA |
| `The object_path was not found in harvested metadata` | **Not a DAA error** — DAA check passed; RDAM has no schema row for that path (schema-path bug until RDAM fix is deployed) | Deploy RDAM schema fix; confirm `rdam_schemaprivilege` has `BUSINESS.BANKING` / `BANKING` for that connection |

### What counts as “DAA” for this API

- **OvalEdge RBAC**: the user’s `user_role.ROLEID` must appear in `connectioninfo.dataaccessadminrole`, `connectioninfo.instancedataaccessadminrole`, or `rdam_instance.dataaccessadminrole` (comma-wrapped, e.g. `,12,34,`).
- **Not** Snowflake `ACCOUNTADMIN` or a native Snowflake role named “DAA”.
- Connection must be a **data access connector** (`isdataaccessconnector = 1`) for Connector DAA checks; Instance DAA on the parent RDAM instance is an alternate path.
- MCP auth user (`SecurityContext` / JWT subject) must match `user_role.USERID` (login id), not display name or email unless that is the userid.

### Quick verification for a failing tester

1. In DAM UI, open the **same** Snowflake connection (`connection_id`) — can they browse native access?
2. Call **table path** on the same `connection_id` (e.g. `BUSINESS.BANKING.ACCOUNTS`):
   - **Table 200, schema 400 “not found”** → schema-resolution bug (TC-07), not DAA.
   - **Both 400 DAA message** → user is not DAA for that connection in OvalEdge.
3. Confirm MCP credentials are for the DAA user, not a service account without DAA roles.

---

### TC-10 — No DAA on connection

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "BUSINESS.BANKING",
  "object_type": "schema",
  "connection_id": <connection caller is not DAA for>
}
```

| Check | Expected |
|-------|----------|
| HTTP | 400 |
| Message | Connector DAA error when `connection_id` is set (not “not found”) |

---

### TC-11 — Database-only path

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "BUSINESS",
  "object_type": "database",
  "connection_id": 1360
}
```

| Check | Expected |
|-------|----------|
| `grants[].objectLevel` | `database` only |
| `objectPath` | `BUSINESS` |

---

### TC-12 — Database-only path not in catalog (`IBIS_UDFS`, connection 1002)

**Question:** Snowflake database `IBIS_UDFS` — what permissions does it have on connection 1002?

**Correct MCP / API call** (infer `object_to_users` — “permissions on the database” = who has native access):

```json
{
  "source_system": "snowflake",
  "query_direction": "object_to_users",
  "object_path": "IBIS_UDFS",
  "object_type": "database",
  "connection_id": 1002
}
```

| Check | Expected (after backend fix) | Known failure (before fix) |
|-------|------------------------------|----------------------------|
| HTTP / `ok` | 200, `ok: true` | 400 |
| Error | — | `The object_path was not found in harvested metadata` |
| `resolvedObjectPath` | `IBIS_UDFS` | — |
| `grants[].objectLevel` | `database` only | — |
| `grantMechanism` | `role` (Snowflake) | — |

**Root cause — `resolveObjectPathForQuery`:**

1. `parseObjectPath("IBIS_UDFS", …, objectType=database)` → database-level parts (OK).
2. `catalogObjectResolver.alignToCatalog` — if `IBIS_UDFS` was **never crawled** into the OvalEdge catalog, alignment yields no usable match.
3. `objectExistsInHarvest(sourceSystem, catalog, connIds)` runs against **catalog-aligned** parts; fails when catalog alignment fails even if `rdam_dbprivilege` has rows for `IBIS_UDFS`.
4. `findCatalogMatches(…, objectType=database)` — often searches schema/table catalog rows; returns empty for uncrawled databases.
5. Four-part column fallback does not apply (single segment, `objectType=database`).
6. Method returns `null` → API 400 “not found”.

**Backend fix (required):**

- For `objectType=database`, resolve from **RDAM harvest first** using parsed `dbName` — do not require catalog alignment to succeed.
- Call `objectExistsInHarvest(sourceSystem, parsed, connIds)` **before or in addition to** catalog-aligned parts.
- Extend `findCatalogMatches` for `objectType=database` to match database names from crawled schema metadata when present.
- Only return `null` when **both** RDAM (`rdam_dbprivilege`) and catalog have no match for the connection scope.

**Data note:** `IBIS_UDFS` is often created by the Ibis Python library on Snowflake connect; it may exist natively with grants but never appear in OvalEdge crawl/RDAM harvest. If RDAM truly has no rows after fix, return 200 with empty `grants[]` and an advisory — not conflate “uncrawled” with “not found” when harvest lookup is incomplete.

---

### TC-13 — Out-of-DAM schema must not appear (`automation_schema` regression)

**Scenario:** RDAM harvest has grants for `automation_schema` and its tables, but the schema is **not**
in DAM (no active `oeschema` row with `rdam_lastcrawldate`, or schema never crawled).

```json
{
  "source_system": "redshift",
  "query_direction": "user_to_objects",
  "username": "john_analyst",
  "connection_id": <QA Redshift connection id>
}
```

| Check | Expected |
|-------|----------|
| `grants` | **No** row with `objectPath` containing `automation_schema` |
| Table grants | **No** `sales_data`, `yardi_property`, `mask_address_vw`, etc. under that schema |
| DAM parity | Result set matches what DAM browse would show for the same connector |

**Root cause (fixed):** API queried raw `rdam_*privilege` without OETP/DAM catalog scope. Fix filters
to active `oedatabase` / `oeschema` / `oetable` / `oecolumn` with `rdam_lastcrawldate IS NOT NULL`.

---

## curl template

```bash
curl -G "${OVALEDGE_BASE_URL}/api/v1/mcp/source-system-access" \
  -H "Authorization: jwt ${OE_INTEGRATION_JWT}" \
  --data-urlencode "sourceSystem=snowflake" \
  --data-urlencode "queryDirection=object_to_users" \
  --data-urlencode "objectPath=BUSINESS.BANKING" \
  --data-urlencode "objectType=schema" \
  --data-urlencode "connectionId=1360"
```

---

## Sign-off checklist

- [ ] TC-01 passes on all 4 connections (TC-03)
- [ ] TC-04 returns `matchCandidates` without grants
- [ ] TC-07 no longer 400 after RDAM schema fix deploy
- [ ] TC-01 grant levels exclude `table`
- [ ] Snowflake grants are `grantMechanism: role` with `contributingRole` populated
