# Live integration tests — `source_system_access`

## Prerequisites

1. OvalEdge running at `OVALEDGE_BASE_URL` (from `.env`).
2. OvalEdge backend with native source-system access (RDAM) MCP APIs enabled.
3. Valid JWT — either:
   - **Recommended:** `export OE_INTEGRATION_JWT='<jwt from OvalEdge UI>'`
   - Or working `OVALEDGE_USER_TOKEN` + `OVALEDGE_USER_SECRET` in `.env` (token exchange must return a JWT, not an empty body).

Optional env overrides (set to match **your** tenant fixtures):

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

## Run

```bash
cd oe_mcp
export OE_INTEGRATION_JWT='...'   # if .env credentials are stale
poetry run pytest -c tests/integration/pytest.ini tests/integration -m integration
```

Unit tests (mocked) still run via:

```bash
poetry run pytest tests/tools/test_source_system_access.py -q
```

## Manual QA — multi-connection schema access

See [QA_SOURCE_SYSTEM_ACCESS_SCHEMA.md](QA_SOURCE_SYSTEM_ACCESS_SCHEMA.md) for a test-case matrix
(e.g. multiple Snowflake connections with the same schema name and different permissions).
