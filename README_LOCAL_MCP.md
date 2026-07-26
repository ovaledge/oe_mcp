# Local MCP (stdio)

Run the OvalEdge MCP server as a **stdio** subprocess with **`AUTH_MODE=local`**. The MCP client (Cursor, Claude Desktop, etc.) starts `poetry run oe-mcp-local` and talks JSON-RPC over stdin/stdout.

← [Back to main README](README.md) · [Remote MCP (HTTP)](README_REMOTE_MCP.md) (`remote` = Okta Connect; `remote_credentials` = headers)

## Runtime architecture

Local mode uses machine credentials (`OVALEDGE_USER_TOKEN`, `OVALEDGE_USER_SECRET`) to obtain an OvalEdge JWT and execute API calls.

1. MCP client starts stdio process: `poetry run oe-mcp-local`
2. `entrypoints/local.py` runs FastMCP with `local_lifespan`
3. Lifespan calls `get_or_refresh_local_token()`
4. OvalEdge `POST /api/user/token/generate` returns JWT
5. JWT is cached in memory and stored in ContextVar
6. Tools use `OvalEdgeClient` for outbound API calls
7. Before requests, local token freshness is checked and refreshed when needed
8. On one-time local 401, cache is invalidated and request is retried once

**Local HTTP** (`poetry run oe-mcp-http` / `./scripts/run_local_mcp_http.sh`) uses the same cached-JWT model with **`AUTH_MODE=local`**. See [.cursor/README.md](.cursor/README.md). Auth troubleshooting: [infra/TROUBLESHOOTING_REMOTE.md](infra/TROUBLESHOOTING_REMOTE.md#token-exchange-invalid_token--duplicate-jwt-issuance).

## Key code (local)

### Entrypoint and app composition

- `entrypoints/local.py` — local FastMCP lifespan, token exchange at startup, stdio transport
- `server/app.py` — tools, resources, prompts, static docs; shared FastMCP app with local lifespan

### Authentication and token lifecycle

- `server/auth/token_exchange.py` — `exchange_client_credentials()`, `get_or_refresh_local_token()`, `is_token_expiring()` (`JWT_REFRESH_LEEWAY_SECONDS = 120`), `invalidate_local_jwt_cache()`
- `server/auth/context.py` — `current_oe_jwt` ContextVar, `local_cached_oe_jwt` process cache
- `server/client.py` — `_ensure_local_token()`; `_send_with_401_handling()` retries once on local 401 after cache invalidation

### Configuration

- `server/config.py` — loads `.env` from repo root; `AUTH_MODE`, base URL, credentials, HTTP auth scheme, retries

Optional telemetry: see [.env.example](.env.example) and [README.md](README.md#observability-telemetry).

## One-shot setup (macOS + Linux)

```bash
chmod +x scripts/setup_local_mcp.sh
./scripts/setup_local_mcp.sh
```

What it does: verifies OS and Python 3.12+, installs Poetry if needed, `poetry install`, creates `.env` from `.env.example` if missing, smoke-imports `entrypoints.local`, prints an `mcp.json` snippet.

Developer mode (lint, typecheck, tests):

```bash
./scripts/setup_local_mcp.sh --dev
```

## One-shot setup (Windows PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local_mcp.ps1
```

Developer mode:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local_mcp.ps1 -Dev
```

## Required environment

Set in `.env` or via MCP client `env` (see [.env.example](.env.example)):

- `AUTH_MODE=local`
- `OVALEDGE_BASE_URL=http://<host>:<port>/ovaledge`
- `OVALEDGE_USER_TOKEN=<your token>`
- `OVALEDGE_USER_SECRET=<your secret>`
- `OVALEDGE_HTTP_AUTH_SCHEME=jwt` (typical default)

Optional: `OVALEDGE_TIMEOUT_SECONDS`, `OVALEDGE_MAX_RETRIES`, `OVALEDGE_RETRY_BACKOFF_SECONDS`, `OVALEDGE_LOG_HTTP_REQUESTS`

## MCP clients (stdio)

Copy-paste **`mcp.json` / `mcpServers`** examples and paths per editor: **[docs/client-setup/README.md](docs/client-setup/README.md)** (e.g. [Cursor](docs/client-setup/SETUP_CURSOR.md#local-stdio-configuration), [Kiro](docs/client-setup/SETUP_KIRO.md#local-stdio-configuration), [Claude Desktop](docs/client-setup/SETUP_CLAUDE.md)).

## Run manually

```bash
poetry -C /absolute/path/to/oe_mcp run oe-mcp-local
```

**Local HTTP** (Cursor logo, Streamable HTTP — same tools, `AUTH_MODE=local`):

```bash
./scripts/run_local_mcp_http.sh
# or: poetry run oe-mcp-http
```

Connect Cursor via **`ovaledge-local-http`** in `mcp.json`; credentials come from repo `.env` (no per-request headers). See [.cursor/README.md](.cursor/README.md).

## Troubleshooting

### `TokenExchangeError` with HTTP 200 empty body

- Check `OVALEDGE_BASE_URL` and `POST /api/user/token/generate` for your OvalEdge build
- Verify `OVALEDGE_USER_TOKEN` and `OVALEDGE_USER_SECRET`

### Works initially, then 401 after idle

- Local client retries once after invalidating the JWT cache on 401
- If the second attempt still fails, credentials or server-side session are likely invalid

### HTML or redirect from OvalEdge

- Wrong base URL or login page intercepting the API path
- Confirm API routes accept `Authorization: <scheme> <jwt>`

### MCP client does not start the server

- `poetry` on PATH for the host process
- Absolute repo path in `-C`
- `AUTH_MODE=local` and `poetry install` completed

Token exchange failures (`INVALID_TOKEN`, duplicate issuance): [infra/TROUBLESHOOTING_REMOTE.md](infra/TROUBLESHOOTING_REMOTE.md#token-exchange-invalid_token--duplicate-jwt-issuance).

## Security (local)

- Never commit real `OVALEDGE_USER_TOKEN` / `OVALEDGE_USER_SECRET`
- Rotate credentials if exposed
- Use a least-privilege OvalEdge account

## Layout (local-relevant paths)

- `entrypoints/local.py` — stdio entrypoint
- `entrypoints/http_local.py` — local HTTP wrapper (`oe-mcp-http`)
- `server/app.py` — MCP assembly
- `server/auth/*` — token exchange and context
- `server/client.py` — outbound OvalEdge HTTP client
- `server/tools/*`, `server/resources/*`, `server/prompts/workflows/`, `server/docs/` (static doc resources, e.g. `docs://ovaledge/mcp_workflows`)
- `scripts/setup_local_mcp.sh`, `scripts/setup_local_mcp.ps1`

## MCP surface (tools, resources, prompts)

After the server starts, clients see:

- **Tools** — catalog, governance (glossary, tags, data stories, writes), platform docs, native access (RDAM)
- **Resources** — `ovaledge://catalog/table|file/{id}`, `ovaledge://governance/glossary-term|data-story|tag/{id}`
- **Workflow prompts** — e.g. `data_discovery`, `organizational_knowledge`, `create_governance_tag`, `metadata_drift`, `native_source_access` (16 total; see [mcp_workflows.md](server/docs/mcp_workflows.md))
- **Doc resources** — `docs://ovaledge/{name}` from `server/docs/*.md` (`mcp_workflows`, `data_stories`, `glossary_guide`, `tags_guide`, …)

**Agent behavior** (from `server/app.py` instructions): use **`knowledge_search`** for organizational knowledge and product how-to; **`write_confirmed_by_user=true`** after user approves create or update previews; native grants via **`source_system_access`**. Full tool list and routing: [README.md](README.md#tools-resources-and-prompts) · [server/docs/mcp_workflows.md](server/docs/mcp_workflows.md).
