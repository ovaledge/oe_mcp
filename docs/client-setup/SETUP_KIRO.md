# Kiro + OvalEdge MCP

[Kiro MCP configuration](https://kiro.dev/docs/mcp/configuration/) · [MCP security (Kiro)](https://kiro.dev/docs/mcp/security)

Kiro uses the same **`mcpServers`** JSON shape as many other clients: **local** servers use `command` + `args`; **remote** servers use `url` + optional `headers`.

**Config file locations**

- **Workspace:** `.kiro/settings/mcp.json`
- **User:** `~/.kiro/settings/mcp.json`

If both exist, settings are merged with **workspace overriding** user. Open via Command Palette (**Kiro: Open workspace MCP config (JSON)** / **Kiro: Open user MCP config (JSON)**) or the Kiro panel **Open MCP Config**.

Environment values can use **`${VAR}`** expansion (see Kiro docs).

---

## Local stdio configuration

Same as Cursor: **`AUTH_MODE=local`**, `poetry run oe-mcp-local`, absolute path with Poetry **`-C`**.

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
        "OVALEDGE_USER_TOKEN": "${OVALEDGE_USER_TOKEN}",
        "OVALEDGE_USER_SECRET": "${OVALEDGE_USER_SECRET}",
        "OVALEDGE_HTTP_AUTH_SCHEME": "jwt",
        "AUTH_MODE": "local"
      }
    }
  }
}
```

Set **`OVALEDGE_USER_TOKEN`** / **`OVALEDGE_USER_SECRET`** in your shell or OS user environment when using `${...}` placeholders. Replace **`YOUR_OVALEDGE_APP_BASE_URL`** with your OvalEdge **`OVALEDGE_BASE_URL`**. Restart or save the config per Kiro behavior so the server reconnects.

---

## Remote HTTP configuration

Use **`url`** plus **`headers`** for **`remote_credentials`** ([README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)).

**`url`** must be your **MCP server’s** public base URL through **`/mcp`** (e.g. deploy **`MCPEndpointUrl`**), **not** your OvalEdge app **`OVALEDGE_BASE_URL`**.

```json
{
  "mcpServers": {
    "ovaledge-remote": {
      "url": "https://YOUR_PUBLIC_MCP_BASE_URL/mcp",
      "headers": {
        "X-OvalEdge-Token": "${OVALEDGE_USER_TOKEN}",
        "X-OvalEdge-Secret": "${OVALEDGE_USER_SECRET}"
      }
    }
  }
}
```

Replace **`YOUR_PUBLIC_MCP_BASE_URL`** with your real host (e.g. an API Gateway execute-api hostname). Kiro documents **HTTPS** for remote URLs. If you use plain **`http://`** and see **`tls_required`**, set **`MCP_HTTP_STATELESS=false`** on the server and add **`X-Forwarded-Proto: https`** to `headers`, or terminate TLS in front of the app.

---

## Security

Do not commit `mcp.json` with hard-coded secrets. Prefer environment variable references. Use HTTPS in production.
