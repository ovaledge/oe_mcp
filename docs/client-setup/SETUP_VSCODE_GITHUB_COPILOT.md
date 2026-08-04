# VS Code + GitHub Copilot + OvalEdge MCP

**Last reviewed:** July 2026.

This guide is for **GitHub Copilot** in **Visual Studio Code** only. For **Microsoft Copilot** (Copilot Studio / Teams / M365 agents), use [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md) — do not use this file.

[Add and manage MCP servers in VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) · [MCP configuration reference](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration)

VS Code does **not** use Cursor’s `mcpServers` shape. GitHub Copilot reads **`mcp.json`** with a top-level **`servers`** object, and HTTP servers use **`"type": "http"`**.

**Where to put `mcp.json`**

- **Workspace:** `.vscode/mcp.json` in the project
- **User-wide:** Command Palette → **MCP: Open User Configuration**
- **Guided:** Command Palette → **MCP: Add Server**

Use **`MCP_HTTP_STATELESS=false`** on the server when the client needs **GET `/mcp`** (Streamable HTTP vs SSE fallback — same guidance as Cursor / Claude Code).

On **HTTPS** MCP URLs, **`X-Forwarded-Proto`** is usually unnecessary; keep it if middleware returns **`tls_required`**.

The **GitHub CLI** does not configure VS Code MCP servers for your Lambda URL—you configure **`mcp.json`** in VS Code.

---

## Remote HTTP (`remote_credentials`)

Replace **`YOUR_PUBLIC_MCP_BASE_URL`** with the host from deploy output **`MCPEndpointUrl`** (keep **`https://`** and **`/mcp`**). This is **not** OvalEdge **`OVALEDGE_BASE_URL`**.

Prefer **`inputs`** for secrets — see VS Code *Input variables for sensitive data* in the MCP configuration reference.

### Two headers (recommended for VS Code)

VS Code supports multiple custom headers on HTTP MCP servers:

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "ovaledge-token",
      "description": "OvalEdge user token",
      "password": true
    },
    {
      "type": "promptString",
      "id": "ovaledge-secret",
      "description": "OvalEdge user secret",
      "password": true
    }
  ],
  "servers": {
    "ovaledge-remote": {
      "type": "http",
      "url": "https://YOUR_PUBLIC_MCP_BASE_URL/mcp",
      "headers": {
        "X-OvalEdge-Token": "${input:ovaledge-token}",
        "X-OvalEdge-Secret": "${input:ovaledge-secret}"
      }
    }
  }
}
```

### Single combined header (optional)

If you prefer one secret prompt, use **`X-OvalEdge-Credentials`** with value **`token::secret`** (no spaces around `::`):

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "ovaledge-credentials",
      "description": "OvalEdge credentials as token::secret",
      "password": true
    }
  ],
  "servers": {
    "ovaledge-remote": {
      "type": "http",
      "url": "https://YOUR_PUBLIC_MCP_BASE_URL/mcp",
      "headers": {
        "X-OvalEdge-Credentials": "${input:ovaledge-credentials}"
      }
    }
  }
}
```

---

## Local stdio (optional)

GitHub Copilot MCP is **HTTP-first**. For local **`AUTH_MODE=local`**, use the same Poetry **`oe-mcp-local`** pattern as [SETUP_CURSOR.md](SETUP_CURSOR.md#local-stdio-configuration) inside **`mcp.json`** with `"type": "stdio"` if your VS Code build supports command-based servers:

```json
{
  "servers": {
    "ovaledge-local": {
      "type": "stdio",
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

---

## Remote OAuth (`AUTH_MODE=remote`)

Use when the MCP server is deployed with **Okta Connect** (browser login; no `X-OvalEdge-*` headers). Server setup: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md#auth_moderremote-okta--oidc-connect). Lambda ZIP: [infra/DEPLOY.md — Okta Connect Lambda ZIP](../../infra/DEPLOY.md#okta-connect-lambda-zip).

### Okta Sign-in redirect URIs (required)

VS Code / GitHub Copilot use a **loopback** callback. Okta requires an **exact** port match — do **not** rely on a random ephemeral port.

Register:

```text
http://localhost:8790/callback
http://127.0.0.1:8790/callback
```

Full allowlist (Cursor, Claude, Microsoft Copilot): [README_REMOTE_MCP.md — Okta redirect URIs (all clients)](../../README_REMOTE_MCP.md#okta-redirect-uris-all-clients).

### `.vscode/mcp.json` (or user MCP config)

```json
{
  "servers": {
    "ovaledge-remote-oauth": {
      "type": "http",
      "url": "https://YOUR_PUBLIC_MCP_BASE_URL/mcp",
      "oauth": {
        "callbackPort": 8790
      }
    }
  }
}
```

- **`callbackPort: 8790`** must match the Okta redirect URIs above.
- **Do not** put `OAUTH_CLIENT_SECRET` in this file. Keep secrets on the Lambda/server; `POST /register` supplies the confidential client when needed.
- If your VS Code build requires `oauth.clientId`, set it to the same value as server `OAUTH_CLIENT_ID` (public id only).

Complete the browser Connect flow when VS Code prompts. If Okta rejects `redirect_uri`, confirm port **8790** is on the app allowlist.

**GitHub Copilot CLI** (when supported): use the same fixed callback port via the CLI’s OAuth / `callbackPort` option so it matches Okta.

---

## Troubleshooting

| Symptom | Action |
| ------- | ------ |
| Server not listed | Command Palette → **MCP: List Servers** / reload window |
| Auth headers ignored | Confirm `"type": "http"` and `headers` under `servers` (not Cursor `mcpServers`) |
| OAuth redirect mismatch | Register **8790** in Okta; set `"oauth": { "callbackPort": 8790 }` |
| Confused with Microsoft Copilot | Use [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md) instead |

---

## References

- [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md) — auth, deploy, testing
- [README_LOCAL_MCP.md](../../README_LOCAL_MCP.md) — local stdio mode
- [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md) — Microsoft Copilot Studio (not this guide)
- [docs/client-setup/README.md](README.md) — all clients
