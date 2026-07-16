# Client setup (MCP)

Guides for connecting **OvalEdge MCP** from common editors and assistants.

**Last reviewed:** July 2026.

| Client | Local (stdio) | Remote HTTP (`remote_credentials`) | Remote OAuth (`AUTH_MODE=remote` / Okta) |
| ------ | --------------- | ---------------------------------- | ---------------------------------------- |
| **Cursor** | [SETUP_CURSOR.md](SETUP_CURSOR.md#local-stdio-configuration) | [SETUP_CURSOR.md](SETUP_CURSOR.md#remote-http-configuration) | [SETUP_CURSOR.md](SETUP_CURSOR.md#remote-oauth-auth_moderremote) |
| **Kiro** | [SETUP_KIRO.md](SETUP_KIRO.md#local-stdio-configuration) | [SETUP_KIRO.md](SETUP_KIRO.md#remote-http-configuration) | — (use HTTP headers; no Okta Connect path documented) |
| **Claude** (Desktop, Chat, Code) | [SETUP_CLAUDE.md](SETUP_CLAUDE.md) | [SETUP_CLAUDE.md](SETUP_CLAUDE.md) (`mcp-remote` / headers) | [SETUP_CLAUDE.md](SETUP_CLAUDE.md#remote-oauth-auth_moderremote) |
| **VS Code + GitHub Copilot** | [SETUP_VSCODE_GITHUB_COPILOT.md](SETUP_VSCODE_GITHUB_COPILOT.md#local-stdio-optional) | [SETUP_VSCODE_GITHUB_COPILOT.md](SETUP_VSCODE_GITHUB_COPILOT.md#remote-http-remote_credentials) | [SETUP_VSCODE_GITHUB_COPILOT.md](SETUP_VSCODE_GITHUB_COPILOT.md#remote-oauth-auth_moderremote) |
| **Microsoft Copilot** (Studio / Teams / M365 agents) | — | [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md) (API key) | [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md#remote-oauth-auth_moderremote) |

**Okta Sign-in redirect URI allowlist** (Cursor, Claude, GitHub Copilot, Microsoft Copilot): [README_REMOTE_MCP.md — Okta redirect URIs (all clients)](../../README_REMOTE_MCP.md#okta-redirect-uris-all-clients).

**Do not mix guides**

| Product | Config surface |
| ------- | -------------- |
| **GitHub Copilot** (VS Code) | `.vscode/mcp.json` — top-level `servers`, `"type": "http"` |
| **Microsoft Copilot** | Copilot Studio MCP wizard + publish/Agent Store — not `mcp.json` |
| **Cursor / Kiro** | `mcpServers` in Cursor/Kiro MCP JSON |
| **Claude Desktop** | `claude_desktop_config.json` (often via `mcp-remote` for remote HTTP) |

**Microsoft Copilot quick path**

1. Attach MCP in Copilot Studio (API key or OAuth) — [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md).
2. Test in Studio (generative orchestration on).
3. Enable **Microsoft 365 Copilot** / **Teams** channel → Publish → admin approve for org.
4. Users open the agent from **Built by your org** / Teams Apps / Studio share link — not default Copilot chat.

**Shared references**

- Local mode (env, scripts, architecture, local HTTP): [README_LOCAL_MCP.md](../../README_LOCAL_MCP.md)
- Remote mode (auth, TLS, deploy, testing): [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)
- Lambda ZIP Okta Connect: [infra/DEPLOY.md — Okta Connect Lambda ZIP](../../infra/DEPLOY.md#okta-connect-lambda-zip)
- Lambda telemetry (Phoenix / Langfuse): [infra/DEPLOY.md](../../infra/DEPLOY.md#telemetry-opentelemetry)
- Environment variables: [.env.example](../../.env.example)
- MCP tools, resources, and workflow prompts: [server/docs/mcp_workflows.md](../../server/docs/mcp_workflows.md) (also `docs://ovaledge/mcp_workflows` when the server is connected)
- Agent routing and human-in-the-loop creates: [README.md](../../README.md#agent-guidance-mirrors-serverapppy-instructions)

**Workflow prompts** (optional): invoke by name in clients that support MCP prompts — e.g. `organizational_knowledge` for data-story questions (uses `lookup_datastory`, not platform docs), `platform_help` for OvalEdge product how-to, `create_governance_tag` / `create_business_glossary_term` for guided writes with **`write_confirmed_by_user`** after you approve the preview.

**Quick routing:** organizational policy/playbooks → `lookup_datastory`; physical datasets → `search_catalog_assets`; OvalEdge UI/features → `search_platform_docs`; native Redshift/Snowflake/Tableau grants → `source_system_access`.

**Placeholders:** in remote HTTP examples, **`YOUR_PUBLIC_MCP_BASE_URL`** is only the **MCP client → MCP server** host (plus you keep **`https://`** and **`/mcp`** as in your deploy **`MCPEndpointUrl`**). It is **not** OvalEdge’s **`OVALEDGE_BASE_URL`**. Local stdio examples use **`YOUR_OVALEDGE_APP_BASE_URL`** for the latter.
