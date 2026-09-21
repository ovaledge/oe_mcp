# ChatGPT / Codex + OvalEdge MCP

**Last reviewed:** September 2026.

[Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt) · [Connect and test your plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt) · [Codex plugins](https://developers.openai.com/codex/plugins) · [Package plugins](https://developers.openai.com/plugins/build/plugins)

OpenAI **ChatGPT** and **Codex** share one Plugins Directory (“With MCP”). This
guide is **day-to-day connection** for a deployed OvalEdge MCP server. Store
submission and remaining checklist: [PUBLISH_DIRECTORIES.md](PUBLISH_DIRECTORIES.md).

Not for Claude — see [SETUP_CLAUDE.md](SETUP_CLAUDE.md). Not for GitHub Copilot
in VS Code — see [SETUP_VSCODE_GITHUB_COPILOT.md](SETUP_VSCODE_GITHUB_COPILOT.md).
Not for Microsoft Copilot Studio — see [SETUP_MICROSOFT_COPILOT.md](SETUP_MICROSOFT_COPILOT.md).

---

## What you need

ChatGPT custom connectors, ChatGPT Apps, and Codex **directory / plugin**
installs require:

| Requirement | Detail |
|-------------|--------|
| **Auth** | `AUTH_MODE=remote` (Okta Connect / OIDC). **No** `X-OvalEdge-Token` / `X-OvalEdge-Secret` headers |
| **Transport** | Public **HTTPS** Streamable HTTP at `https://YOUR_PUBLIC_MCP_BASE_URL/mcp` |
| **OAuth** | Authorization Code + **PKCE** on the Okta app used as `OAUTH_CLIENT_ID` |
| **DCR** | This server’s `POST /register` returns the pre-registered client id |

They do **not** accept local stdio (`oe-mcp-local`), `mcp-remote` header bridges, or
`AUTH_MODE=remote_credentials`. Use Cursor / Claude Desktop for those modes.

`YOUR_PUBLIC_MCP_BASE_URL` is the **MCP host** from deploy output **`MCPPublicBaseUrl`**
(or the host part of **`MCPEndpointUrl`**). It is **not** OvalEdge’s
`OVALEDGE_BASE_URL`.

Server setup: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md#auth_moderremote-okta--oidc-connect).
Lambda ZIP: [infra/DEPLOY.md — Okta Connect Lambda ZIP](../../infra/DEPLOY.md#okta-connect-lambda-zip).

**Plans.** Developer mode and custom MCP connectors depend on the ChatGPT account
and workspace policy. Workspace admins enable developer mode under workspace
**Permissions & Roles**. Confirm current availability in OpenAI’s help article
above before you promise a rollout.

---

## Okta Sign-in redirect URIs

In the Okta OIDC app used as `OAUTH_CLIENT_ID`, add:

| Surface | URI |
|---------|-----|
| ChatGPT (legacy, stable) | `https://chatgpt.com/connector_platform_oauth_redirect` |
| ChatGPT (current) | `https://chatgpt.com/connector/oauth/{callback_id}` — **copy from the ChatGPT app / plugin page**; do not invent the id |
| Codex CLI | Exact loopback printed by `codex mcp add` (often `http://127.0.0.1/callback` or with a server-specific path suffix) |

Keep the **legacy** ChatGPT URI even after you add the per-app `callback_id` URI.

Enable **Authorization Code + PKCE**. Full multi-client allowlist:
[README_REMOTE_MCP.md — Okta redirect URIs](../../README_REMOTE_MCP.md#okta-redirect-uris-all-clients).

If authorize fails with *The 'redirect_uri' parameter must be a Login redirect URI*,
paste the **exact** URI from the error (or from the ChatGPT / Codex UI) into Okta
and retry. Okta matches path and host strictly.

---

## ChatGPT (developer mode — custom MCP)

Use this to test the same HTTPS `/mcp` URL you will submit “With MCP”. Official
flow: [Connect and test your plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt).

### Enable developer mode

1. Open ChatGPT on the **web**.
2. **Settings → Security and login**.
3. Turn on **Developer mode**.

Workspace admins may need to allow this first (**Workspace Settings → Permissions
& Roles → Connected Data / Developer mode**). Availability varies by plan.

### Add the MCP server

1. Open [ChatGPT Plugins](https://chatgpt.com/plugins) (or **Settings → Plugins**).
2. Select the **plus** button.
3. Enter a user-facing **name** and **description** (include the environment if
   you have more than one MCP host, e.g. “OvalEdge MCP — prod”).
4. Under **Connection**, choose the public endpoint and enter:

   ```text
   https://YOUR_PUBLIC_MCP_BASE_URL/mcp
   ```

   Include the `/mcp` path. Do not paste OvalEdge’s application URL.

5. Create the connection and complete **OAuth** (Okta). Copy the redirect URI
   shown in the UI into Okta if authorize fails.
6. Review the tools and metadata ChatGPT discovered (`title`, annotations,
   schemas). If tools are missing, redeploy the MCP server and **Refresh** the
   connection.

Optional local-only testing without a public origin: OpenAI **Secure MCP Tunnel**
(or another HTTPS tunnel). That is **not** a substitute for the public HTTPS
endpoint required for directory submission.

### Use it in a chat

1. Start a **new** conversation.
2. Add the app from the tools / **+ → More** menu.
3. Run a read tool (for example **Find data assets**) and one governed-write
   **preview**. Do not set `write_confirmed_by_user=true` until the user
   explicitly approves the preview.

After you change tool names, descriptions, schemas, annotations, or UI
resources: deploy, open the connection, **Refresh**, then start a new chat.

### Workspace Publish vs public directory

- **Workspace Publish** (ChatGPT admin) shares the plugin **inside your OpenAI
  workspace only**.
- The **public** ChatGPT + Codex Plugins Directory is a separate portal:
  [PUBLISH_DIRECTORIES.md](PUBLISH_DIRECTORIES.md#d-openai--codex-plugins-directory-chatgpt--codex).

---

## Codex CLI

Codex talks Streamable HTTP natively. Do **not** wrap OvalEdge MCP in
`mcp-remote` for Codex.

**1. Register**

```bash
codex mcp add ovaledge --url https://YOUR_PUBLIC_MCP_BASE_URL/mcp
```

Register the **exact** `redirect_uri` Codex prints in Okta (loopback host, port,
and path). Then authenticate:

```bash
codex mcp login ovaledge
```

**2. Inspect / remove**

```bash
codex mcp list
codex mcp get ovaledge
codex mcp logout ovaledge
codex mcp remove ovaledge
```

Codex stores servers in `~/.codex/config.toml` (TOML, not Cursor/Claude JSON).
A Streamable HTTP entry looks like:

```toml
[mcp_servers.ovaledge]
url = "https://YOUR_PUBLIC_MCP_BASE_URL/mcp"
```

Do **not** set `bearer_token_env_var` or `http_headers` for OvalEdge
`AUTH_MODE=remote`. ChatGPT/Codex must use **OAuth Connect**, not a static
Bearer token and not `X-OvalEdge-*` headers.

The Codex **IDE extension** does not install plugins; use ChatGPT desktop, Codex
in the ChatGPT app, or Codex CLI (`/plugins`).

---

## In-repo plugin package

For ChatGPT desktop / Codex CLI, this repo ships
[`plugins/codex-ovaledge/`](../../plugins/codex-ovaledge/). The MCP **server** is
still the remote HTTPS `/mcp` process; the plugin adds a marketplace install and
a routing skill.

| File | Role |
|------|------|
| `plugins/codex-ovaledge/plugin.json` | Portable Agent Plugins manifest (`extensions.com.openai`) |
| `plugins/codex-ovaledge/mcp.json` | Streamable HTTP URL — replace `YOUR_PUBLIC_MCP_BASE_URL` |
| `plugins/codex-ovaledge/skills/ovaledge-mcp-workflows/` | Routing skill; playbooks stay on `docs://ovaledge/mcp_workflows` |

**1. Point `mcp.json` at your host**

```json
{
  "mcpServers": {
    "ovaledge": {
      "type": "streamable-http",
      "url": "https://YOUR_PUBLIC_MCP_BASE_URL/mcp"
    }
  }
}
```

Do not commit a live tenant URL or Okta secrets.

**2. Add the repo marketplace and install**

From the **oe_mcp** repo root:

```bash
codex plugin marketplace add ./
```

The catalog is [`.agents/plugins/marketplace.json`](../../.agents/plugins/marketplace.json).
Then in Codex CLI:

```text
codex
/plugins
```

Install **ovaledge**, complete OAuth when prompted, and start a **new** session
before using tools or the bundled skill.

On ChatGPT desktop (Work / Codex), open the **Plugins** tab, install from the
local / workspace marketplace, and connect the MCP server when asked.

---

## MCP Apps UI (ChatGPT)

Four catalog **read** tools advertise self-contained HTML views
(`ui://ovaledge/*.html`) for hosts that implement MCP Apps:

| Tool | View |
|------|------|
| `asset_explorer` | Search table |
| `asset_details` | Details card |
| `asset_lineage` | Lineage graph |
| `metadata_changes_between_crawls` | Crawl-diff tables |

ChatGPT may render those widgets. **Codex CLI**, Cursor, Cortex, and Copilot
Studio still receive the **JSON body** and `formattedResponse`. Do not expect
the widget in Codex. Never show `ovaledge://` URIs to users — use `navLink` or
`redirectUrl`.

Directory screenshot rules: [PUBLISH_DIRECTORIES.md](PUBLISH_DIRECTORIES.md) (D10).

---

## Domain verification (directory only)

When the OpenAI plugin portal shows a challenge token:

1. Set `OPENAI_APPS_CHALLENGE` on the MCP process (see [.env.example](../../.env.example);
   SAM/ECS parameter `OpenAIAppsChallenge`).
2. Redeploy.
3. Confirm:

   ```bash
   curl -sS https://YOUR_PUBLIC_MCP_BASE_URL/.well-known/openai-apps-challenge
   ```

   The body must be **exactly** that token (plaintext, no extra whitespace). Empty
   env → HTTP 404.

---

## Smoke tests

After Connect, in a **new** ChatGPT or Codex session:

| Prompt | Expect |
|--------|--------|
| Find tables related to sales | `asset_explorer` (then `asset_details` on a shortlist) |
| Search OvalEdge knowledge for how data classification works | `knowledge_search` |
| Who has access to table *X*? | Disambiguation (native vs catalog permissions) before `access_explorer` |
| Preview a governed write (e.g. description update) | Preview only; no persist until the user approves |

Present `formattedResponse` when the tool returns it. Routing playbook:
[server/docs/mcp_workflows.md](../../server/docs/mcp_workflows.md)
(`docs://ovaledge/mcp_workflows` when the server is connected).

Suggested directory cases (5 positive + 3 negative):
[PUBLISH_DIRECTORIES.md](PUBLISH_DIRECTORIES.md#suggested-directory-test-cases).

---

## Troubleshooting

| Symptom | Action |
|---------|--------|
| OAuth redirect mismatch | Paste the ChatGPT `callback_id` URI or Codex loopback URI into Okta; keep the legacy `connector_platform_oauth_redirect` URI |
| Developer mode missing | Workspace admin must enable it; check plan / RBAC |
| Connection fails / tools empty | URL must be `https://…/mcp`; confirm `AUTH_MODE=remote`; run MCP Inspector (`npx @modelcontextprotocol/inspector@latest`) |
| Domain not verified | `OPENAI_APPS_CHALLENGE` empty (404), extra whitespace, or WAF blocking OpenAI |
| Tools missing annotations | Redeploy current `server/tools/common/annotations.py`; **Refresh** / Scan Tools again |
| Reviewer cannot log in | Disable MFA on the demo IdP user; test from a network outside the corp VPN |
| WAF 403 | Refresh [chatgpt-connectors.json](https://openai.com/chatgpt-connectors.json) or disable WAF for review |
| Codex config ignored | Codex uses `~/.codex/config.toml`, not `mcp.json`; table key is `mcp_servers` |
| Plugin tools missing in Codex | New CLI session after install; `codex mcp login`; IDE extension does not load plugins |
| Widget missing in Codex | Expected — MCP Apps UI is ChatGPT; Codex uses JSON |

## Shared references

- Pending store checklist: [PUBLISH_DIRECTORIES.md](PUBLISH_DIRECTORIES.md)
- Remote auth and TLS: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)
- Plugin packages: [plugins/README.md](../../plugins/README.md)
- Client index: [README.md](README.md)
