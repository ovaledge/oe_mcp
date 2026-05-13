# Local MCP (stdio)

Run the OvalEdge MCP server as a **stdio** subprocess with **`AUTH_MODE=local`**. The MCP client (Cursor, Claude Desktop, etc.) starts `poetry run oe-mcp-local` and talks JSON-RPC over stdin/stdout.

← [Back to main README](README.md) · [Remote MCP (HTTP)](README_REMOTE_MCP.md) (OAuth 2.x **`remote`** mode: **WIP**)

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

## Security (local)

- Never commit real `OVALEDGE_USER_TOKEN` / `OVALEDGE_USER_SECRET`
- Rotate credentials if exposed
- Use a least-privilege OvalEdge account

## Layout (local-relevant paths)

- `entrypoints/local.py` — stdio entrypoint
- `server/app.py` — MCP assembly
- `server/auth/*` — token exchange and context
- `server/client.py` — outbound OvalEdge HTTP client
- `server/tools/*`, `server/resources/*`, `server/prompts/workflows.py`
- `scripts/setup_local_mcp.sh`, `scripts/setup_local_mcp.ps1`
