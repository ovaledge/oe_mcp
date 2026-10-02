# Plugin packages (Claude Code + ChatGPT/Codex)

Bundled MCP **plugins** for hosts that install from a folder or marketplace.
The MCP **server** is still this repo’s `AUTH_MODE=remote` HTTPS `/mcp` process.

| Package | Host | Marketplace entry |
|---------|------|-------------------|
| `plugins/claude-ovaledge/` | Claude Code / Cowork | `.claude-plugin/marketplace.json` |
| `plugins/codex-ovaledge/` | ChatGPT + Codex | `.agents/plugins/marketplace.json` |

How to connect, and what is still required for public directories:
[docs/client-setup/SETUP_CLAUDE.md](../docs/client-setup/SETUP_CLAUDE.md),
[docs/client-setup/SETUP_CODEX.md](../docs/client-setup/SETUP_CODEX.md),
[docs/client-setup/PUBLISH_DIRECTORIES.md](../docs/client-setup/PUBLISH_DIRECTORIES.md).

Do not put secrets, Okta client secrets, or live challenge tokens in these files.
The Codex `mcp.json` URL uses the placeholder `YOUR_PUBLIC_MCP_BASE_URL` until you
replace it for a local install. The Claude plugin prompts for `mcp_url` at enable time.
