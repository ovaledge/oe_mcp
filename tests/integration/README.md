# Live integration tests — `source_system_access`

## Prerequisites

1. OvalEdge running at `OVALEDGE_BASE_URL` (from `.env`).
2. Backend deployed with `McpSourceSystemAccessReadService` (NFD-48785).
3. Valid JWT — either:
   - **Recommended:** `export OE_INTEGRATION_JWT='<jwt from OvalEdge UI>'`
   - Or working `OVALEDGE_USER_TOKEN` + `OVALEDGE_USER_SECRET` in `.env` (token exchange must return a JWT, not an empty body).

Optional env overrides:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OE_IT_CONNECTION_ID` | `1000` | Scope to one connection |
| `OE_IT_RS_USER` | `sithik` | Redshift / Tableau user |
| `OE_IT_RS_OBJECT_PATH` | `ovaledgedb.automation.customers` | Table path |
| `OE_IT_RS_PARTIAL` | `customers` | Partial-path disambiguation |
| `OE_IT_SF_USER` | `sithik` | Snowflake user |
| `OE_IT_SF_OBJECT_PATH` | `BUSINESS.BANKING.ACCOUNTSCHEDULE` | Snowflake table path |
| `OE_IT_SF_DB_NAME` | `BUSINESS` | Snowflake `dbName`-only path test |
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
poetry run pytest tests/tools/test_data_access_management.py -q
```
