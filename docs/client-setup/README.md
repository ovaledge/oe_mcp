# Client setup (MCP)

Guides for connecting **OvalEdge MCP** from common editors and assistants.

| Client | Local (stdio) | Remote HTTP (`remote_credentials`) |
| ------ | --------------- | ---------------------------------- |
| **Cursor** | [SETUP_CURSOR.md](SETUP_CURSOR.md#local-stdio-configuration) | [SETUP_CURSOR.md](SETUP_CURSOR.md#remote-http-configuration) |
| **Kiro** | [SETUP_KIRO.md](SETUP_KIRO.md#local-stdio-configuration) | [SETUP_KIRO.md](SETUP_KIRO.md#remote-http-configuration) |
| **Claude** (Desktop, Chat, Code) | [SETUP_CLAUDE.md](SETUP_CLAUDE.md) (Desktop: `mcp-remote`; local stdio: same Poetry pattern as Cursor) | [SETUP_CLAUDE.md](SETUP_CLAUDE.md) |
| **VS Code + GitHub Copilot** | — (Copilot MCP is HTTP-first; use local stdio only if your workflow supports a command server) | [SETUP_VSCODE_GITHUB_COPILOT.md](SETUP_VSCODE_GITHUB_COPILOT.md) |

**Shared references**

- Local mode (env, scripts, architecture): [README_LOCAL_MCP.md](../../README_LOCAL_MCP.md)
- Remote mode (auth, TLS, deploy, testing): [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)
- Environment variables: [.env.example](../../.env.example)

**Placeholders:** in remote HTTP examples, **`YOUR_PUBLIC_MCP_BASE_URL`** is only the **MCP client → MCP server** host (plus you keep **`https://`** and **`/mcp`** as in your deploy **`MCPEndpointUrl`**). It is **not** OvalEdge’s **`OVALEDGE_BASE_URL`**. Local stdio examples use **`YOUR_OVALEDGE_APP_BASE_URL`** for the latter.
