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
| `ovaledge-remote-local` | HTTP → local uvicorn | `AUTH_MODE=remote_credentials` on port 8000; needs `X-Forwarded-Proto` for plain HTTP |
| `ovaledge-remote-lambda` | HTTP → deployed API Gateway | Replace URL with your `MCPEndpointUrl` |
| `ovaledge-remote-oauth-wip` | HTTP + Bearer | **`AUTH_MODE=remote` OAuth — WIP**; not production-ready |

## Environment variables

Set in your shell, direnv, or Cursor’s environment (Cursor expands `${env:…}` in `mcp.json`):

- `OVALEDGE_BASE_URL` — OvalEdge app URL (e.g. `http://localhost:8080/ovaledge`)
- `OVALEDGE_USER_TOKEN`, `OVALEDGE_USER_SECRET` — machine credentials for local / `remote_credentials`

For **`ovaledge-local`**, you can omit the `env` block if `.env` in the repo root is complete and Poetry loads it (see [README_LOCAL_MCP.md](../README_LOCAL_MCP.md)).

If `${workspaceFolder}` is not expanded in your Cursor build, replace it with the **absolute** path to this repo in `args` (see [docs/client-setup/SETUP_CURSOR.md](../docs/client-setup/SETUP_CURSOR.md)).

## Tools, prompts, and routing

After connect, use workflow prompts and tools as documented in [server/docs/mcp_workflows.md](../server/docs/mcp_workflows.md) (`docs://ovaledge/mcp_workflows`), including **`native_source_access`** / **`source_system_access`** for Redshift, Snowflake, and Tableau native grants.
