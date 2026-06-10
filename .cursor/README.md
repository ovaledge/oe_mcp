# Cursor MCP configuration

Copy the example to enable this repo’s MCP server in Cursor:

```bash
cp .cursor/mcp.json.example .cursor/mcp.json
```

Or merge into `~/.cursor/mcp.json` (user-wide). Restart Cursor after changes.

## Which server entry to use

| Key | Mode | When |
|-----|------|------|
| **`ovaledge-local`** | stdio (`AUTH_MODE=local`) | **Default for development** — `poetry run oe-mcp-local` |
| **`ovaledge-local-http`** | HTTP → local uvicorn | **Shows OvalEdge logo in Cursor** — run `poetry run oe-mcp-http` (or `./scripts/run_local_mcp_http.sh`) first; same tools as stdio |
| `ovaledge-remote-local` | HTTP → local uvicorn | Alias pattern for deployed-style `remote_credentials` on port 8000 |
| `ovaledge-remote-lambda` | HTTP → deployed API Gateway | Replace URL with your `MCPEndpointUrl` |
| `ovaledge-remote-oauth-wip` | HTTP + Bearer | **`AUTH_MODE=remote` OAuth — WIP**; not production-ready |

## Environment variables

Set in your shell, direnv, or Cursor’s environment (Cursor expands `${env:…}` in `mcp.json`):

- `OVALEDGE_BASE_URL` — OvalEdge app URL (e.g. `http://localhost:8080/ovaledge`)
- `OVALEDGE_USER_TOKEN`, `OVALEDGE_USER_SECRET` — machine credentials for local / `remote_credentials`

For **`ovaledge-local`**, you can omit the `env` block if `.env` in the repo root is complete and Poetry loads it (see [README_LOCAL_MCP.md](../README_LOCAL_MCP.md)).

If `${workspaceFolder}` is not expanded in your Cursor build, replace it with the **absolute** path to this repo in `args` (see [docs/client-setup/SETUP_CURSOR.md](../docs/client-setup/SETUP_CURSOR.md)).

## MCP server logo (Cursor)

Cursor shows **custom MCP logos for HTTP servers** (e.g. `docs-fastmcp`). **stdio** servers such as **`ovaledge-local`** usually get a **letter avatar** (“O”) even though the server sends a valid icon in `initialize`.

To see the OvalEdge logo locally:

1. Add **`ovaledge-local-http`** from [mcp.json.example](mcp.json.example) to your `mcp.json` (URL only — no credential headers).
2. Put **`OVALEDGE_BASE_URL`**, **`OVALEDGE_USER_TOKEN`**, and **`OVALEDGE_USER_SECRET`** in repo **`.env`** (same as stdio), then start the HTTP server:

   ```bash
   poetry run oe-mcp-http
   # or: ./scripts/run_local_mcp_http.sh
   ```

3. Enable **`ovaledge-local-http`** in Cursor Settings → MCP (disable **`ovaledge-local`** if you do not want duplicate tools).

If `POST /mcp` returns **502**, check the uvicorn log: token exchange failed at startup (missing `.env`, wrong `OVALEDGE_BASE_URL`, or invalid credentials).

### Why the logo still may not appear on localhost

Cursor **does not reliably load MCP icons from `http://127.0.0.1`** (and often ignores data URIs for custom servers). The `docs-fastmcp` logo in Cursor is **not** from your MCP metadata — it is curated client-side.

To see the **OvalEdge logo** while developing locally:

1. Deploy once (or use an existing API Gateway URL) with the `/brand/ovaledge-mcp-icon.png` route.
2. Add to repo **`.env`**:

   ```bash
   MCP_BRAND_ICON_BASE_URL=https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com
   ```

   (Use the same host as `ovaledge-mcp-remote` / `europe` — no `/mcp` suffix.)

3. Restart `poetry run oe-mcp-http` — stderr should print `MCP icon URL: https://.../brand/ovaledge-mcp-icon.png`.
4. Toggle **`ovaledge-local-http`** off/on in Cursor Settings → MCP.

## Tools, prompts, and routing

After connect, use workflow prompts and tools as documented in [server/docs/mcp_workflows.md](../server/docs/mcp_workflows.md) (`docs://ovaledge/mcp_workflows`), including **`native_source_access`** / **`source_system_access`** for Redshift, Snowflake, and Tableau native grants.

## Agent skills (this repo)

| Skill | Use when |
|-------|----------|
| [oe-mcp-tool-design](skills/oe-mcp-tool-design/SKILL.md) | Adding or reviewing MCP tools in this codebase |

Invoke in Cursor with `@oe-mcp-tool-design` or ask to follow the oe_mcp tool design skill.
