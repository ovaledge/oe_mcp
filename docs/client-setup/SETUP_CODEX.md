# ChatGPT / Codex + OvalEdge MCP

**Last reviewed:** September 2026.

OpenAI **ChatGPT** and **Codex** share one Plugins Directory (“With MCP”). This
guide is day-to-day connection. Store submission and remaining checklist:
[PUBLISH_DIRECTORIES.md](PUBLISH_DIRECTORIES.md).

Not for Claude — see [SETUP_CLAUDE.md](SETUP_CLAUDE.md). Not for GitHub Copilot
in VS Code — see [SETUP_VSCODE_GITHUB_COPILOT.md](SETUP_VSCODE_GITHUB_COPILOT.md).

Directory and ChatGPT connector installs need **`AUTH_MODE=remote`** (Okta Connect)
on a public **HTTPS** `/mcp` URL. They do **not** send `X-OvalEdge-*` headers.

Server setup: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md#auth_moderremote-okta--oidc-connect).

---

## Okta Sign-in redirect URIs

In the Okta OIDC app used as `OAUTH_CLIENT_ID`, add:

| Surface | URI |
|---------|-----|
| ChatGPT (legacy, stable) | `https://chatgpt.com/connector_platform_oauth_redirect` |
| ChatGPT (current) | `https://chatgpt.com/connector/oauth/{callback_id}` — **copy from the ChatGPT app / plugin page**; do not invent the id |
| Codex CLI | Exact loopback printed by `codex mcp add` (often `http://127.0.0.1/callback` or with a server-specific path suffix) |

Enable **Authorization Code + PKCE**. Full multi-client allowlist:
[README_REMOTE_MCP.md — Okta redirect URIs](../../README_REMOTE_MCP.md#okta-redirect-uris-all-clients).

---

## ChatGPT (developer mode — custom MCP)

Use this to test the same URL you will submit “With MCP”.

1. ChatGPT → **Settings → Security and login → Developer mode**.
2. **Plugins** → add server → HTTPS URL `https://YOUR_PUBLIC_MCP_BASE_URL/mcp`.
3. Complete OAuth Connect (Okta). Copy the redirect URI shown in the UI into Okta if authorize fails.
4. Run a read tool (for example Find data assets) and one governed-write **preview**.

`YOUR_PUBLIC_MCP_BASE_URL` is the MCP host from deploy output **`MCPPublicBaseUrl`**,
not OvalEdge’s `OVALEDGE_BASE_URL`.

Public listing is a separate portal step — [PUBLISH_DIRECTORIES.md](PUBLISH_DIRECTORIES.md#d-openai--codex-plugins-directory-chatgpt--codex).

---

## Codex CLI

```bash
codex mcp add --url https://YOUR_PUBLIC_MCP_BASE_URL/mcp ovaledge
```

Register the **exact** `redirect_uri` Codex prints in Okta (loopback port and path).
If authorize fails with *redirect_uri must be a Login redirect URI*, add that URI
and retry.

Codex can also load the in-repo plugin after you replace the placeholder in
[`plugins/codex-ovaledge/mcp.json`](../../plugins/codex-ovaledge/mcp.json):

```bash
codex plugin marketplace add ./
```

The repo marketplace is [`.agents/plugins/marketplace.json`](../../.agents/plugins/marketplace.json).

---

## In-repo plugin package

| File | Role |
|------|------|
| `plugins/codex-ovaledge/plugin.json` | Portable Agent Plugins manifest |
| `plugins/codex-ovaledge/mcp.json` | Streamable HTTP URL (replace `YOUR_PUBLIC_MCP_BASE_URL`) |
| `plugins/codex-ovaledge/skills/ovaledge-mcp-workflows/` | Routing skill; playbooks stay on `docs://ovaledge/mcp_workflows` |

Workspace Publish (ChatGPT admin) shares the plugin **inside your OpenAI workspace
only**. The public ChatGPT + Codex directory requires the plugin portal.

---

## Domain verification (directory only)

When the OpenAI portal shows a challenge token:

1. Set `OPENAI_APPS_CHALLENGE` on the MCP process (see [.env.example](../../.env.example); SAM/ECS parameter `OpenAIAppsChallenge`).
2. Redeploy.
3. `curl -sS https://YOUR_PUBLIC_MCP_BASE_URL/.well-known/openai-apps-challenge` must return **exactly** that token (plaintext).

---

## Troubleshooting

| Symptom | Action |
|---------|--------|
| OAuth redirect mismatch | Paste the ChatGPT `callback_id` URI or Codex loopback URI into Okta |
| Domain not verified | Token env empty (404), extra whitespace, or WAF blocking OpenAI |
| Tools missing annotations | Redeploy current `server/tools/common/annotations.py`; Scan Tools again |
| Reviewer cannot log in | Disable MFA on the demo IdP user; test from a network outside the corp VPN |
| WAF 403 | Refresh [chatgpt-connectors.json](https://openai.com/chatgpt-connectors.json) or disable WAF for review |

## Shared references

- Pending store checklist: [PUBLISH_DIRECTORIES.md](PUBLISH_DIRECTORIES.md)
- Remote auth and TLS: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)
- Client index: [README.md](README.md)
