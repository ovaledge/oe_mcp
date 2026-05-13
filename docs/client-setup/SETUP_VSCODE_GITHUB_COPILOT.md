# VS Code + GitHub Copilot + OvalEdge MCP

[Add and manage MCP servers in VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) · [MCP configuration reference](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration)

VS Code does **not** use Cursor’s `mcpServers` shape. GitHub Copilot reads **`mcp.json`** with a top-level **`servers`** object, and HTTP servers use **`"type": "http"`**.

**Where to put `mcp.json`**

- **Workspace:** `.vscode/mcp.json` in the project
- **User-wide:** Command Palette → **MCP: Open User Configuration**
- **Guided:** Command Palette → **MCP: Add Server**

Use **`MCP_HTTP_STATELESS=false`** on the server when the client needs **GET `/mcp`** (same guidance as Cursor / Claude Code for Streamable HTTP vs SSE fallback).

On **HTTPS** MCP URLs, **`X-Forwarded-Proto`** is usually unnecessary; keep it if middleware returns **`tls_required`**.

The **GitHub CLI** does not configure VS Code MCP servers for your Lambda URL—you configure **`mcp.json`** in VS Code.

**Example `.vscode/mcp.json`** for **`remote_credentials`**: replace **`YOUR_PUBLIC_MCP_BASE_URL`** with the host part of your **MCP endpoint** (same idea as deploy **`MCPEndpointUrl`**), **not** OvalEdge **`OVALEDGE_BASE_URL`**. Prefer **`inputs`** for secrets—see VS Code *Input variables for sensitive data* in the reference above.

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

**References:** [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md) (auth, deploy, testing).
