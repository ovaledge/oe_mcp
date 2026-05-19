# VS Code + GitHub Copilot + OvalEdge MCP

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

GitHub Copilot MCP is **HTTP-first**. For local **`AUTH_MODE=local`**, use the same Poetry **`oe-mcp-local`** pattern as [SETUP_CURSOR.md](SETUP_CURSOR.md#local-stdio-configuration) inside **`mcp.json`** with `"type": "stdio"` if your VS Code build supports command-based servers.

---

## References

- [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md) — auth, deploy, testing
- [README_LOCAL_MCP.md](../../README_LOCAL_MCP.md) — local stdio mode
