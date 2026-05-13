# Claude (Desktop, Chat, Code) + OvalEdge MCP

Anthropic’s [MCP quickstart (user)](https://modelcontextprotocol.io/quickstart/user) · [Connect Claude Desktop to local MCP](https://support.anthropic.com/en/articles/10995153-connecting-claude-desktop-to-local-mcp-servers) · [`mcp-remote` (npm)](https://www.npmjs.com/package/mcp-remote) · [Claude Code setup](https://code.claude.com/docs/en/setup)

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

## Shared references

- Remote auth and TLS: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)
- Local stdio env: [README_LOCAL_MCP.md](../../README_LOCAL_MCP.md)
