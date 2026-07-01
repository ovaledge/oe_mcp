# Cursor + OvalEdge MCP

[Official MCP docs](https://docs.cursor.com/context/model-context-protocol) · Cursor reads **`~/.cursor/mcp.json`** (user) or project-level **`.cursor/mcp.json`** depending on your Cursor version and settings.

**Project template:** copy [`.cursor/mcp.json.example`](../../.cursor/mcp.json.example) → `.cursor/mcp.json` (see [`.cursor/README.md`](../../.cursor/README.md)).

---

## Local stdio configuration

Run the server with **`AUTH_MODE=local`** (see [README_LOCAL_MCP.md](../../README_LOCAL_MCP.md)). Cursor starts a subprocess and speaks JSON-RPC over stdin/stdout.

Use Poetry **`-C`** so the command works from any working directory:

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
        "OVALEDGE_BASE_URL": "https://YOUR_OVALEDGE_APP_BASE_URL",
        "OVALEDGE_USER_TOKEN": "your-user-token",
        "OVALEDGE_USER_SECRET": "your-user-secret",
        "OVALEDGE_HTTP_AUTH_SCHEME": "jwt",
        "AUTH_MODE": "local"
      }
    }
  }
}
```

If `.env` in the repo is complete, you can omit most `env` keys and rely on the process environment. Replace **`YOUR_OVALEDGE_APP_BASE_URL`** with your OvalEdge application base URL (same as **`OVALEDGE_BASE_URL`** in `.env`). Restart Cursor after changes.

**`poetry`** must be on `PATH` for the process that launches Cursor. Use an **absolute** repo path in `-C`.

### Logo in Cursor (stdio vs HTTP)

**`ovaledge-local` (stdio)** sends the icon as a data URI in MCP metadata, but Cursor typically shows a letter avatar for command-based servers, not the PNG.

For the **OvalEdge logo**, use **local HTTP** instead:

1. Add **`OVALEDGE_BASE_URL`**, **`OVALEDGE_USER_TOKEN`**, and **`OVALEDGE_USER_SECRET`** to repo **`.env`** (same values as stdio).
2. Run: `poetry run oe-mcp-http` (or `./scripts/run_local_mcp_http.sh`).
3. Add to `mcp.json`:

```json
"ovaledge-local-http": {
  "url": "http://127.0.0.1:8000/mcp"
}
```

4. Connect **`ovaledge-local-http`** in Cursor (disable **`ovaledge-local`** if you do not want duplicate tools).

**502 on `POST /mcp`:** the HTTP server exchanges credentials at startup from `.env`. Ensure OvalEdge is reachable at `OVALEDGE_BASE_URL` and credentials match your working stdio setup. Do not use `remote_credentials` headers for this entry unless you intentionally run with `AUTH_MODE=remote_credentials`.

See [.cursor/README.md](../../.cursor/README.md#mcp-server-logo-cursor).

---

## Remote HTTP configuration

Use this when the MCP app runs over HTTP with **`AUTH_MODE=remote_credentials`** (see [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)).

**`url` is your deployed MCP HTTP(S) endpoint** (path usually ends in **`/mcp`**), e.g. from deploy output **`MCPEndpointUrl`**. It is **not** the same value as **`OVALEDGE_BASE_URL`** (the OvalEdge application URL the MCP *server* uses to call APIs—see local stdio `env` above).

Cursor expands **`${env:VAR}`** from **Cursor’s own process environment**, not from the repo `.env` (unless you launched Cursor with those variables set).

Example `mcp.json` fragment (replace **`YOUR_PUBLIC_MCP_BASE_URL`** with your real MCP host only—keep **`https://`** and **`/mcp`** as appropriate for your URL):

```json
{
  "mcpServers": {
    "ovaledge-remote": {
      "url": "https://YOUR_PUBLIC_MCP_BASE_URL/mcp",
      "headers": {
        "X-OvalEdge-Token": "${env:OVALEDGE_USER_TOKEN}",
        "X-OvalEdge-Secret": "${env:OVALEDGE_USER_SECRET}"
      }
    }
  }
}
```

On **HTTPS** URLs (typical API Gateway), **`X-Forwarded-Proto`** is usually unnecessary. If your MCP URL is plain **`http://`** (e.g. local uvicorn), set **`MCP_HTTP_STATELESS=false`** on the server and add **`"X-Forwarded-Proto": "https"`** in `headers` so middleware accepts the request as TLS-terminated (see remote README).

Each user should use **their own** OvalEdge token and secret. The server caches a JWT per credential key (bounded by `CREDENTIALS_CACHE_MAX_ENTRIES`).

The path may be **`/mcp`** or **`/mcp/`** — the server normalizes slashless **`/mcp`** so clients are not tripped by Starlette’s **307** redirect to **`/mcp/`**.

---

## Workflow prompts and docs

With the server connected, Cursor can list **MCP prompts**, **resources**, and **doc resources**:

| Need | Start with |
| ---- | ---------- |
| Internal policy / playbook / narrative | Prompt `organizational_knowledge` or tool `lookup_datastory` |
| Find tables, files, reports | Prompt `data_discovery` or `search_catalog_assets` |
| Create tag or glossary term | Prompt `create_governance_tag` / `create_business_glossary_term` (confirm preview, then `write_confirmed_by_user=true`) |
| OvalEdge product how-to | Prompt `platform_help` or `search_platform_docs` |
| Native Redshift / Snowflake / Tableau grants | Prompt `native_source_access` or tool `source_system_access` |
| Deep link by id | `ovaledge://catalog/table/{id}`, `ovaledge://governance/data-story/{id}`, … |

Full index: [server/docs/mcp_workflows.md](../../server/docs/mcp_workflows.md) (`docs://ovaledge/mcp_workflows`). Agent rules: [README.md](../../README.md#agent-guidance-mirrors-serverapppy-instructions).

## Security

Never commit real tokens. Rotate credentials if exposed. Prefer least-privilege OvalEdge accounts for local mode.
