# Live integration tests

## Prerequisites

1. OvalEdge running at `OVALEDGE_BASE_URL` (from `.env`).
2. Auth for live calls — pick one:
   - **Recommended (local):** `OVALEDGE_USER_TOKEN` + `OVALEDGE_USER_SECRET` in repo **`.env`**. The harness calls `POST /api/user/token/generate` via `get_or_refresh_local_token()` — no manual JWT copy/paste.
   - **Optional override:** `export OE_INTEGRATION_JWT='<jwt from OvalEdge UI>'` when you want to bypass token exchange (e.g. debugging a specific session).

`.env` example:

```bash
OVALEDGE_BASE_URL=http://localhost:8080
OVALEDGE_USER_TOKEN=your-user-token
OVALEDGE_USER_SECRET=your-user-secret
```

## Run all live tests

```bash
cd oe_mcp
poetry run pytest -c tests/integration/pytest.ini tests/integration -m integration
```

---

## Consolidated read tools

File: `test_consolidated_read_tools_live.py` — **5 tests per tool (20 total)** covering:

- `GET /api/v1/mcp/asset-explorer`
- `GET /api/v1/mcp/asset-details`
- `GET /api/v1/mcp/asset-lineage`
- `GET /api/v1/mcp/knowledge-search`

Fixtures (table/column/file/glossary/tag object ids) are **discovered dynamically**
from the live catalog, so no object ids are hard-coded. `askedgidev` is the OvalEdge
backend MySQL database that stores this crawled catalog metadata; the tests target the
real crawled objects it holds. Tune discovery with these hints:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OE_IT_SCHEMA_NAME` | `superstore` | Preferred crawled schema for table discovery |
| `OE_IT_SERVER_TYPE` | `mysql` | Preferred connector technology for discovery |
| `OE_IT_TABLE_SEARCH_TERM` | `customer` | Lexical term to discover an `oetable` |
| `OE_IT_COLUMN_SEARCH_TERM` | `email` | Lexical term to discover an `oecolumn` |
| `OE_IT_FILE_SEARCH_TERM` | `customer` | Lexical term to discover an `oefile` |
| `OE_IT_GLOSSARY_TERM` | `Revenue` | Glossary name-mode check |
| `OE_IT_TAG_NAME` | `PII` | Tag name-mode check |
| `OE_IT_KNOWLEDGE_QUERY` | `data quality policy` | Dual-corpus knowledge search query |
| `OE_IT_PLATFORM_HELP_QUERY` | `how do I create a governance tag` | Product-help knowledge query |
| `OE_IT_ORG_KNOWLEDGE_QUERY` | `customer` | Org data-story knowledge query |

Tests skip cleanly when no matching object exists for a discovery hint.

```bash
poetry run pytest -c tests/integration/pytest.ini \
  tests/integration/test_consolidated_read_tools_live.py -m integration
```

---

## `source_system_access` (RDAM)

File: `test_source_system_access_live.py`

Requires OvalEdge backend with native source-system access (RDAM) MCP APIs enabled.

| Variable | Example | Purpose |
|----------|---------|---------|
| `OE_IT_CONNECTION_ID` | `1000` | Scope to one connection |
| `OE_IT_RS_USER` | `analyst@example.com` | Redshift / Tableau user |
| `OE_IT_RS_OBJECT_PATH` | `mydb.myschema.customers` | Table path |
| `OE_IT_RS_PARTIAL` | `customers` | Partial-path disambiguation |
| `OE_IT_SF_USER` | `analyst@example.com` | Snowflake user |
| `OE_IT_SF_OBJECT_PATH` | `MYDB.MYSCHEMA.MYTABLE` | Snowflake table path |
| `OE_IT_SF_DB_NAME` | `MYDB` | Snowflake `dbName`-only path test |
| `OE_IT_SF_CONN_NAME` | `snowflake` | Snowflake `connectionName.dbName` prefix test |
| `OE_IT_TABLEAU_OBJECT_PATH` | _(auto-discover)_ | Tableau report/project path |

Unit tests (mocked) still run via:

```bash
poetry run pytest tests/tools/test_source_system_access.py -q
```

## Manual QA — multi-connection schema access

See [QA_SOURCE_SYSTEM_ACCESS_SCHEMA.md](QA_SOURCE_SYSTEM_ACCESS_SCHEMA.md) for a test-case matrix
(e.g. multiple Snowflake connections with the same schema name and different permissions).
