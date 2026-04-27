# OvalEdge Local MCP Server

Local-only documentation for running the OvalEdge MCP server over stdio with Poetry.

This repository exposes read-only OvalEdge governance/discovery capabilities to MCP clients (Cursor, Claude Desktop, etc.).

## What This Server Provides

- Catalog discovery and details (`search_catalog_assets`, `catalog_asset_details`)
- Column profile, entity relationships, lineage
- Governance lookups (glossary and tags)
- Platform documentation search
- Resource endpoints for deep links (`ovaledge://...`)
- Pre-built workflow prompts for common analyst tasks

## Local Runtime Architecture

Local mode uses machine credentials (`OVALEDGE_USER_TOKEN`, `OVALEDGE_USER_SECRET`) to obtain an OvalEdge JWT and execute API calls.

1. MCP client starts stdio process: `poetry run oe-mcp-local`
2. `entrypoints/local.py` runs FastMCP with `local_lifespan`
3. Lifespan calls `get_or_refresh_local_token()`
4. OvalEdge `POST /api/user/token/generate` returns JWT
5. JWT is cached in memory and stored in ContextVar
6. Tools use `OvalEdgeClient` for outbound API calls
7. Before requests, local token freshness is checked and refreshed when needed
8. On one-time local 401, cache is invalidated and request is retried once

## Key Code Integrations (Local MCP)

### Entrypoint and app composition

- `entrypoints/local.py`
  - Defines local FastMCP lifespan
  - Bootstraps token exchange at startup
  - Runs stdio transport
- `server/app.py`
  - Registers all tools, resources, prompts, and static docs
  - Builds shared FastMCP application with local lifespan injection

### Authentication and token lifecycle

- `server/auth/token_exchange.py`
  - `exchange_client_credentials()` calls OvalEdge token endpoint
  - `get_or_refresh_local_token()` caches token in-process
  - `is_token_expiring()` applies expiry/leeway logic (`JWT_REFRESH_LEEWAY_SECONDS = 120`)
  - `invalidate_local_jwt_cache()` clears stale cache for forced refresh
- `server/auth/context.py`
  - `current_oe_jwt` ContextVar for request-scoped token access
  - `local_cached_oe_jwt` in-memory process cache
- `server/client.py`
  - `_ensure_local_token()` lazily refreshes token in local mode
  - `_send_with_local_401_retry()` retries once after cache invalidation on local 401
  - Retries transient HTTP failures (429/502/503/504) via Tenacity

### Configuration loading

- `server/config.py`
  - Loads `.env` from repo root (absolute path fallback)
  - Defines all local-relevant settings (`AUTH_MODE`, base URL, token credentials, HTTP auth scheme, retry controls)

## One-Shot Local Setup (macOS + Linux)

Use the setup script after cloning:

```bash
chmod +x scripts/setup_local_mcp.sh
./scripts/setup_local_mcp.sh
```

What it does:

- Verifies OS (Darwin/Linux)
- Verifies Python 3.12+
- Installs Poetry if missing (official installer)
- Runs `poetry install`
- Creates `.env` from `.env.example` if absent
- Runs a local smoke import (`from entrypoints.local import mcp`)
- Prints a ready-to-edit `mcp.json` snippet

Developer mode (adds lint/typecheck/tests):

```bash
./scripts/setup_local_mcp.sh --dev
```

## Required Local Environment

Set these in `.env` (or pass via MCP client `env`):

- `AUTH_MODE=local`
- `OVALEDGE_BASE_URL=http://<host>:<port>/ovaledge`
- `OVALEDGE_USER_TOKEN=<your token>`
- `OVALEDGE_USER_SECRET=<your secret>`
- `OVALEDGE_HTTP_AUTH_SCHEME=jwt` (default/local expected)

Optional tuning:

- `OVALEDGE_TIMEOUT_SECONDS`
- `OVALEDGE_MAX_RETRIES`
- `OVALEDGE_RETRY_BACKOFF_SECONDS`
- `OVALEDGE_LOG_HTTP_REQUESTS`

## MCP Client Configuration (`mcp.json`)

Use Poetry `-C` style (recommended):

```json
{
  "mcpServers": {
    "ovaledge-local": {
      "command": "poetry",
      "args": [
        "-C",
        "/absolute/path/to/oe_mcp",
        "run",
        "oe-mcp-local"
      ],
      "env": {
        "OVALEDGE_BASE_URL": "http://127.0.0.1:8080/ovaledge",
        "OVALEDGE_USER_TOKEN": "your-user-token",
        "OVALEDGE_USER_SECRET": "your-user-secret",
        "OVALEDGE_HTTP_AUTH_SCHEME": "jwt",
        "AUTH_MODE": "local"
      }
    }
  }
}
```

Notes:

- If `.env` inside the repo is complete, you can omit most `env` entries.
- Restart your MCP client after config changes.

## Tools, Resources, and Prompts

### Tools

Implemented in `server/tools/`:

- `search_catalog_assets`
- `catalog_asset_details`
- `column_profile_statistics`
- `table_entity_relationships`
- `asset_lineage`
- `lookup_glossary_term`
- `lookup_tags`
- `search_platform_docs`

### Resources

Implemented in `server/resources/`:

- `ovaledge://catalog/table/{object_id}`
- `ovaledge://governance/glossary-term/{object_id}`

### Prompts

Implemented in `server/prompts/workflows.py`:

- Data discovery
- Explain business term
- Trust assessment
- Explore domain
- Trace lineage
- Find related assets
- Platform help

## Local Operations

### Run manually

```bash
poetry -C /absolute/path/to/oe_mcp run oe-mcp-local
```

### Quality gates

```bash
poetry run ruff check .
poetry run mypy server/ entrypoints/
poetry run pytest
```

## Troubleshooting (Local MCP)

### 1) `TokenExchangeError` with HTTP 200 empty body

Symptom:

- Token endpoint responds 200, but no usable token payload.

Checks:

- Verify `OVALEDGE_BASE_URL`
- Verify `POST /api/user/token/generate` contract for your OvalEdge build
- Verify `OVALEDGE_USER_TOKEN` and `OVALEDGE_USER_SECRET`

### 2) Works initially, then 401 after idle

Behavior:

- Local client now does one-time cache invalidation + retry on local 401.
- If second attempt still fails, credentials/session are likely invalid server-side.

Checks:

- Confirm token/secret still valid
- Confirm system clock and JWT expiry behavior on OvalEdge side

### 3) HTML or redirect responses from OvalEdge

Likely cause:

- Wrong base URL/path or session-login endpoint intercepted API route.

Checks:

- Ensure your target path is API-enabled for token-based auth
- Inspect logs for redirect `Location` in outbound request tracing

### 4) MCP client does not start server

Checks:

- `poetry` is available in PATH of the MCP host process
- Repo path in `-C` is absolute and correct
- `AUTH_MODE=local` is set
- Dependencies installed (`poetry install`)

## Security Notes

- Never commit real `OVALEDGE_USER_TOKEN` / `OVALEDGE_USER_SECRET`.
- Rotate credentials if accidentally exposed.
- Use least-privilege OvalEdge account for local MCP usage.

## Repository Layout (Local-relevant)

- `entrypoints/local.py` - stdio entrypoint
- `server/app.py` - MCP assembly
- `server/auth/*` - token exchange/context and auth helpers
- `server/client.py` - outbound OvalEdge client + retry behavior
- `server/tools/*` - MCP tools
- `server/resources/*` - MCP resources
- `server/prompts/workflows.py` - MCP prompts
- `scripts/setup_local_mcp.sh` - one-shot local setup
