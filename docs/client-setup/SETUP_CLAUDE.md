# Claude (Desktop, Chat, Code) + OvalEdge MCP

**Last reviewed:** July 2026.

Anthropic’s [MCP quickstart (user)](https://modelcontextprotocol.io/quickstart/user) · [Connect Claude Desktop to local MCP](https://support.anthropic.com/en/articles/10995153-connecting-claude-desktop-to-local-mcp-servers) · [`mcp-remote` (npm)](https://www.npmjs.com/package/mcp-remote) · [Claude Code setup](https://code.claude.com/docs/en/setup)

Not for Microsoft Copilot Studio — see [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md).

---

## Claude Desktop / Claude Chat (stdio → HTTP)

Claude Desktop starts MCP servers as **local stdio** processes. It does **not** use Cursor’s **`"url"` + `"headers"`** block for remote HTTP.

To reach a **deployed** `remote_credentials` HTTPS endpoint, run **[`mcp-remote`](https://github.com/geelen/mcp-remote)** under **`npx`**: stdio to Claude, HTTPS upstream, with **`--header`** forwarding **`X-OvalEdge-Token`** and **`X-OvalEdge-Secret`**.

**Prerequisites:** [Node.js](https://nodejs.org/) for `npx`. On the **server**, if negotiation fails, set **`MCP_HTTP_STATELESS=false`** so **`GET /mcp`** exists for clients that probe SSE-style paths (same idea as [Claude Code HTTP MCP](#claude-code-http-mcp)).

**Config paths**

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Enable Developer / MCP features in Claude settings if the file does not exist yet (see Anthropic support article above).

**Example `mcpServers` entry** — replace **`YOUR_PUBLIC_MCP_BASE_URL`** with the host part of your **MCP HTTP(S) endpoint** (e.g. from **`MCPEndpointUrl`**), **not** your OvalEdge **`OVALEDGE_BASE_URL`**. Replace token/secret placeholders; **do not commit** real values.

```json
{
  "mcpServers": {
    "ovaledge-remote": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://YOUR_PUBLIC_MCP_BASE_URL/mcp",
        "--header",
        "X-OvalEdge-Token:YOUR_USER_TOKEN",
        "--header",
        "X-OvalEdge-Secret:YOUR_USER_SECRET"
      ]
    }
  }
}
```

**Notes**

- **`--header`** format: **`Name:value`** with **no space after the colon** (avoids quoting bugs on some Windows / Claude Desktop invocations).
- If values contain spaces or args get mangled, put secrets in **`env`** and use a header value without spaces after `:` (see [mcp-remote: Custom Headers](https://github.com/geelen/mcp-remote#custom-headers)).
- Pin **`mcp-remote@<version>`** for reproducible installs; **`--transport http-only`** can help against some gateways (`npx mcp-remote --help`).
- **Security:** rotate anything pasted into chat; restrict permissions on the JSON config file.

**Restart Claude Desktop** after edits.

For **local stdio** (`poetry run oe-mcp-local`), use the same **`command` / `args` / `env`** pattern as [SETUP_CURSOR.md](SETUP_CURSOR.md#local-stdio-configuration) inside `claude_desktop_config.json` instead of `mcp-remote`.

---

## Claude Code (HTTP MCP)

**Claude Code** is the CLI-driven product; register HTTP MCP with **`claude mcp`** and **`--transport http`**.

**Install** (official installer — see [Claude Code setup](https://code.claude.com/docs/en/setup) for current steps):

**macOS, Linux, or WSL:**

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://claude.ai/install.ps1 | iex
```

**Alternatives:** Homebrew `brew install --cask claude-code`; Windows WinGet `winget install Anthropic.ClaudeCode`.

Run **`claude`** once and complete login before **`claude mcp`**.

On the **server**, set **`MCP_HTTP_STATELESS=false`** (SAM **`McpHttpStateless=false`**, or `export MCP_HTTP_STATELESS=false` for uvicorn) so **`GET /mcp`** is registered for SSE-style fallback.

**`https://YOUR_PUBLIC_MCP_BASE_URL/mcp`** stands for the full URL of your **MCP server** (scheme + host + path through **`/mcp`**), e.g. deploy **`MCPEndpointUrl`** — **not** OvalEdge’s **`OVALEDGE_BASE_URL`**. For plain **`http://`** MCP URLs, the app must still see HTTPS semantics (TLS in front or **`X-Forwarded-Proto: https`**); the CLI does not add that header—prefer **HTTPS** in production.

**1. Register**

From the workspace where you use Claude Code:

```bash
claude mcp add --transport http ovaledge-remote https://YOUR_PUBLIC_MCP_BASE_URL/mcp \
  --header "X-OvalEdge-Token: YOUR_USER_TOKEN" \
  --header "X-OvalEdge-Secret: YOUR_USER_SECRET"
```

**2. Remove**

```bash
claude mcp remove ovaledge-remote
```

---

## Remote OAuth (`AUTH_MODE=remote`)

Use when the MCP server is deployed with **Okta Connect** (browser login; no OvalEdge token/secret headers). Server setup: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md#auth_moderremote-okta--oidc-connect). Lambda ZIP: [infra/DEPLOY.md — Okta Connect Lambda ZIP](../../infra/DEPLOY.md#okta-connect-lambda-zip).

### Okta Sign-in redirect URIs (required)

In the Okta OIDC app used as `OAUTH_CLIENT_ID`, add:

```text
https://claude.ai/api/mcp/auth_callback
http://localhost:8788/callback
http://127.0.0.1:8788/callback
```

| Surface | URI |
|---------|-----|
| Claude.ai / Desktop / mobile | `https://claude.ai/api/mcp/auth_callback` |
| Claude Code (CLI) | Fixed loopback, e.g. `http://localhost:8788/callback` (and `127.0.0.1`) |

Claude Code picks a **random** port unless you fix it. Okta typically requires an **exact** redirect URI, so register **8788** (or another port you choose) and pass the same port when adding the server.

Also enable **Authorization Code + PKCE** on that Okta app. Full Cursor + Claude + Copilot allowlist: [README_REMOTE_MCP.md — Okta redirect URIs (all clients)](../../README_REMOTE_MCP.md#okta-redirect-uris-all-clients).

### Claude.ai / Desktop

Add the connector URL `https://YOUR_PUBLIC_MCP_BASE_URL/mcp` and complete **Connect** in the browser (callback is `https://claude.ai/api/mcp/auth_callback`).

### Claude Code

```bash
claude mcp add --transport http --callback-port 8788 ovaledge-remote-oauth \
  https://YOUR_PUBLIC_MCP_BASE_URL/mcp
```

Or JSON with a fixed callback port:

```bash
claude mcp add-json ovaledge-remote-oauth \
  '{"type":"http","url":"https://YOUR_PUBLIC_MCP_BASE_URL/mcp","oauth":{"callbackPort":8788}}'
```

If authorize fails with *redirect_uri must be a Login redirect URI*, add the exact URI (including port) in Okta and retry Connect / `claude mcp`.

---

## Troubleshooting

| Symptom | Action |
| ------- | ------ |
| Desktop ignores config | Restart Claude Desktop; confirm Developer/MCP enabled |
| `mcp-remote` auth fails | Header format `Name:value` (no space after `:`); pin `mcp-remote` version |
| Claude Code OAuth redirect mismatch | Register fixed port **8788** in Okta; pass `--callback-port 8788` |
| SSE / GET `/mcp` issues | Set server `MCP_HTTP_STATELESS=false` |

## Shared references

- Remote auth and TLS: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)
- Local stdio env: [README_LOCAL_MCP.md](../../README_LOCAL_MCP.md)
- Client index: [README.md](README.md)
