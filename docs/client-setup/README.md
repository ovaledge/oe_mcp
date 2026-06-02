# Client setup (MCP)

Guides for connecting **OvalEdge MCP** from common editors and assistants.

| Client | Local (stdio) | Remote HTTP (`remote_credentials`) |
| ------ | --------------- | ---------------------------------- |
| **Cursor** | [SETUP_CURSOR.md](SETUP_CURSOR.md#local-stdio-configuration) | [SETUP_CURSOR.md](SETUP_CURSOR.md#remote-http-configuration) |
| **Kiro** | [SETUP_KIRO.md](SETUP_KIRO.md#local-stdio-configuration) | [SETUP_KIRO.md](SETUP_KIRO.md#remote-http-configuration) |
| **Claude** (Desktop, Chat, Code) | [SETUP_CLAUDE.md](SETUP_CLAUDE.md) (Desktop: `mcp-remote`; local stdio: same Poetry pattern as Cursor) | [SETUP_CLAUDE.md](SETUP_CLAUDE.md) |
| **VS Code + GitHub Copilot** | — (HTTP-first; optional stdio) | [SETUP_VSCODE_GITHUB_COPILOT.md](SETUP_VSCODE_GITHUB_COPILOT.md) |
| **Microsoft Copilot** (Studio / Teams / M365 agents) | — | [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md) |

**Do not mix guides:** GitHub Copilot (VS Code `mcp.json`) and Microsoft Copilot (Copilot Studio wizard) use different hosts, config surfaces, and auth UI.

**Shared references**

- Local mode (env, scripts, architecture): [README_LOCAL_MCP.md](../../README_LOCAL_MCP.md)
- Remote mode (auth, TLS, deploy, testing): [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)
- Environment variables: [.env.example](../../.env.example)
- MCP tools, resources, and workflow prompts: [server/docs/mcp_workflows.md](../../server/docs/mcp_workflows.md) (also `docs://ovaledge/mcp_workflows` when the server is connected)
- Agent routing and human-in-the-loop creates: [README.md](../../README.md#agent-guidance-mirrors-serverapppy-instructions)

**Workflow prompts** (optional): invoke by name in clients that support MCP prompts — e.g. `organizational_knowledge` for data-story questions (uses `lookup_datastory`, not platform docs), `platform_help` for OvalEdge product how-to, `create_governance_tag` / `create_business_glossary_term` for guided writes with **`create_confirmed_by_user`** after you approve the preview.

**Quick routing:** organizational policy/playbooks → `lookup_datastory`; physical datasets → `search_catalog_assets`; OvalEdge UI/features → `search_platform_docs`; native Redshift/Snowflake/Tableau grants → `user_object_access`.

**Placeholders:** in remote HTTP examples, **`YOUR_PUBLIC_MCP_BASE_URL`** is only the **MCP client → MCP server** host (plus you keep **`https://`** and **`/mcp`** as in your deploy **`MCPEndpointUrl`**). It is **not** OvalEdge’s **`OVALEDGE_BASE_URL`**. Local stdio examples use **`YOUR_OVALEDGE_APP_BASE_URL`** for the latter.
