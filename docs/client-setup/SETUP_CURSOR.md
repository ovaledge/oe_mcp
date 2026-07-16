# Cursor + OvalEdge MCP

**Last reviewed:** July 2026.

[Cursor MCP docs](https://cursor.com/docs) · Cursor reads **`~/.cursor/mcp.json`** (user) and/or project **`.cursor/mcp.json`** depending on version and settings.

**Project template:** copy [`.cursor/mcp.json.example`](../../.cursor/mcp.json.example) → `.cursor/mcp.json` (see [`.cursor/README.md`](../../.cursor/README.md)).

This guide is for **Cursor** only. Microsoft Copilot Studio is [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md); VS Code GitHub Copilot is [SETUP_VSCODE_GITHUB_COPILOT.md](SETUP_VSCODE_GITHUB_COPILOT.md).

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

## Remote OAuth (`AUTH_MODE=remote`)

Use when the server is deployed with **Okta Connect** (no `X-OvalEdge-*` headers). Full server setup: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md#auth_moderremote-okta--oidc-connect). Lambda ZIP: [infra/DEPLOY.md — Okta Connect Lambda ZIP](../../infra/DEPLOY.md#okta-connect-lambda-zip).

### Okta Sign-in redirect URIs (required)

In the Okta OIDC app used as `OAUTH_CLIENT_ID`, add Cursor’s URIs (and any other clients you use):

```text
http://localhost:8787/callback
https://www.cursor.com/agents/mcp/oauth/callback
cursor://anysphere.cursor-mcp/oauth/callback
```

| Surface | URI |
|---------|-----|
| Desktop (default) | `http://localhost:8787/callback` |
| Desktop (fallback) | `cursor://anysphere.cursor-mcp/oauth/callback` |
| Web / Cursor Agents | `https://www.cursor.com/agents/mcp/oauth/callback` |

Full allowlist (Claude, GitHub Copilot, Microsoft Copilot): [README_REMOTE_MCP.md — Okta redirect URIs (all clients)](../../README_REMOTE_MCP.md#okta-redirect-uris-all-clients).

Also enable **Authorization Code + PKCE** on that Okta app.

### `mcp.json`

```json
{
  "mcpServers": {
    "ovaledge-remote-oauth": {
      "url": "https://YOUR_PUBLIC_MCP_BASE_URL/mcp"
    }
  }
}
```

Use Cursor’s **Connect** button (URL only — **do not** put Okta client id/secret in `mcp.json`). If you see *redirect_uri must be a Login redirect URI*, add the URIs above in Okta. If token exchange fails with *Client authentication failed*, ensure Lambda has `OAUTH_CLIENT_SECRET` and redeploy so `/register` can supply it. See [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md#confidential-okta-apps-client-secret).

If Cursor logs **`fetch failed`**, the URL is wrong or unreachable from your laptop — curl `https://YOUR_PUBLIC_MCP_BASE_URL/health` first (expect `"auth_mode":"remote"`).
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

## Troubleshooting

| Symptom | Action |
| ------- | ------ |
| Tools missing after edit | Restart Cursor / toggle MCP server off→on |
| `fetch failed` on remote URL | `curl` `…/health`; confirm URL ends with `/mcp` |
| OAuth redirect rejected | Add Cursor URIs in Okta (above); retry Connect |
| Token exchange / client auth failed | Ensure Lambda has `OAUTH_CLIENT_SECRET`; redeploy |
| Duplicate tools | Disable stdio **or** HTTP entry, not both |

## Security

Never commit real tokens. Rotate credentials if exposed. Prefer least-privilege OvalEdge accounts for local mode.
