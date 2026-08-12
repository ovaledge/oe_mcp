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
| **`ovaledge-local-http`** | HTTP → local uvicorn | **Shows OvalEdge logo in Cursor** — run `./scripts/run_local_mcp_http.sh` (or `poetry run oe-mcp-http`) first; forces **`AUTH_MODE=local`** (JWT cached at startup); same tools as stdio |
| **`ovaledge-remote-http`** | HTTP → remote host | EC2/VM: run `./scripts/run_remote_mcp_http.sh` on the server (`AUTH_MODE=remote_credentials`); put token/secret in **mcp.json headers** (not on the server `.env`) |
| **`ovaledge-remote-oauth`** | HTTP → remote (Okta Connect) | Run `./scripts/run_remote_oauth_mcp_http.sh` or `AUTH_MODE=remote ./scripts/deploy.sh --zip`; Connect → Okta; register redirect URIs ([README_REMOTE_MCP.md](../README_REMOTE_MCP.md#okta-redirect-uris-all-clients)) |
| **`ovaledge-ecs`** | HTTP → ALB | ECS Fargate: `./scripts/deploy_ecs.sh` — use stack output `McpEndpointUrl`; credentials in headers ([infra/DEPLOY.md](../infra/DEPLOY.md#aws-ecs-fargate--alb)) |
| `ovaledge-remote-local` | HTTP → API Gateway / local | Alias pattern for deployed-style `remote_credentials` |
| `ovaledge-remote-lambda` | HTTP → deployed API Gateway | Replace URL with your `MCPEndpointUrl` |
| `ovaledge-remote-oauth-manual-token` | HTTP + Bearer | Debug: paste an Okta access token instead of Connect |

## Environment variables

Set in your shell, direnv, or Cursor’s environment (Cursor expands `${env:…}` in `mcp.json`):

- `OVALEDGE_BASE_URL` — OvalEdge app URL (e.g. `http://localhost:8080/ovaledge`)
- `OVALEDGE_USER_TOKEN`, `OVALEDGE_USER_SECRET` — machine credentials for local / `remote_credentials`

For **`ovaledge-local`**, you can omit the `env` block if `.env` in the repo root is complete and Poetry loads it (see [README_LOCAL_MCP.md](../README_LOCAL_MCP.md)).

For **`ovaledge-local-http`**, put credentials in repo **`.env`** only — do not send `X-OvalEdge-*` headers from Cursor. The HTTP server uses **`AUTH_MODE=local`** (overrides `remote_credentials` in `.env`).

For **`ovaledge-remote-http`**, the server `.env` needs only **`OVALEDGE_BASE_URL`**. Credentials travel in Cursor **`headers`** (`X-OvalEdge-Token` / `X-OvalEdge-Secret`) and are exchanged per user on each request. Include **`X-Forwarded-Proto: https`** when the URL is plain `http://` (TLS check). Prefer HTTPS via a reverse proxy in production.

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

After connect, use workflow prompts and tools as documented in [server/docs/mcp_workflows.md](../server/docs/mcp_workflows.md) (`docs://ovaledge/mcp_workflows`), including **`native_source_access`** / **`access_explorer`** (`operation=source_system_access`) for Redshift, Snowflake, and Tableau native grants.

## Agent skills (this repo)

| Skill | Use when |
|-------|----------|
| [oe-mcp-tool-design](skills/oe-mcp-tool-design/SKILL.md) | Adding or reviewing MCP tools in this codebase |

Invoke in Cursor with `@oe-mcp-tool-design` or ask to follow the oe_mcp tool design skill.

## CodeGraph (structural code index)

For **contributing to this repo**, use [CodeGraph](https://github.com/colbymchenry/codegraph) to reduce grep/read loops. After `codegraph install` (once), run from repo root:

```bash
codegraph init -i
```

See [docs/contributing/CODEGRAPH.md](../docs/contributing/CODEGRAPH.md) for MCP enablement, landmarks, and when to use CodeGraph vs `docs://ovaledge/*`.

**Cursor rule:** [.cursor/rules/codegraph.mdc](rules/codegraph.mdc) — applies when editing Python under `server/`, `tests/`, `evals/`, `entrypoints/` so agents call `codegraph_explore` before grep/read loops.
