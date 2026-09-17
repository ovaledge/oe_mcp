# Publish OvalEdge MCP (Claude connector/plugin + OpenAI/Codex plugin)

**Last reviewed:** September 2026.

This playbook is the remaining **store / directory** work after the in-repo plumbing.
Day-to-day client setup stays in:

- [SETUP_CLAUDE.md](SETUP_CLAUDE.md) — custom Connect today; plugin + Connectors Directory below
- [SETUP_CODEX.md](SETUP_CODEX.md) — ChatGPT developer mode, Codex CLI, local plugin
- Server deploy: [README_REMOTE_MCP.md](../../README_REMOTE_MCP.md)

Directory products require **one production `AUTH_MODE=remote` HTTPS `/mcp` URL**.
They do **not** accept stdio, `mcp-remote`, or `X-OvalEdge-*` headers.

| Surface | What users install | In this repo | Submit where |
|---------|--------------------|--------------|--------------|
| Claude.ai / Desktop / mobile | **Connector** | Deployed `/mcp` | [Connectors Directory](https://claude.com/docs/connectors/building/submission) (Team/Enterprise Owner) |
| Claude Code / Cowork | **Plugin** | `plugins/claude-ovaledge/` | [Plugin directory](https://claude.com/docs/plugins/submit) (public GitHub) |
| ChatGPT + Codex | **One plugin** (“With MCP”) | `plugins/codex-ovaledge/` + same `/mcp` | [OpenAI plugin portal](https://developers.openai.com/plugins/deploy/submission) |

Claude **connector** and **plugin** are two stores. OpenAI **ChatGPT and Codex share one Plugins Directory**.

---

## Already in this repository

Do these once per environment; they are **not** store-form work.

1. Deploy MCP with `AUTH_MODE=remote`, public HTTPS, Streamable HTTP `POST /mcp`.
2. Okta OIDC app: Authorization Code + PKCE. Register every client redirect URI
   ([allowlist](../../README_REMOTE_MCP.md#okta-redirect-uris-all-clients)), including ChatGPT/Codex when you use those clients.
3. `POST /register` (DCR shim) returns the pre-registered `OAUTH_CLIENT_ID`.
4. Tool annotations: `title` plus `readOnlyHint` / `destructiveHint` / `openWorldHint`.
   `openWorldHint` is **false** (bounded OvalEdge tenant). Justifications for the
   OpenAI form are in [Annotation justifications](#annotation-justifications-openai-portal).
5. `GET /.well-known/openai-apps-challenge` — set `OPENAI_APPS_CHALLENGE` from the
   OpenAI portal token (SAM/ECS parameter or Lambda env). Empty → 404.
6. Plugin packages and repo marketplaces:
   - Claude Code: `plugins/claude-ovaledge/` + `.claude-plugin/marketplace.json`
   - ChatGPT/Codex: `plugins/codex-ovaledge/` + `.agents/plugins/marketplace.json`

---

## Pending — do in this order

### A. Shared (Claude + OpenAI)

| # | Item | How to achieve it |
|---|------|-------------------|
| A1 | **Public HTTPS MCP** | Production host with TLS at the edge. Copy `MCPEndpointUrl` (must end with `/mcp`). Custom connector/plugin installs can use a customer tenant URL; **directory listings** need a stable origin you control. |
| A2 | **Business / org verification** | Claude: Team or Enterprise org; Owners (or a custom **Directory** role on Enterprise) submit connectors. OpenAI: complete [individual or business verification](https://developers.openai.com/plugins/deploy/app-review) in the Platform Dashboard; grant `api.apps.write` to the submitter. |
| A3 | **Public legal URLs** | Host HTTPS **privacy policy**, **terms of service**, **support**, and **company website**. Paste them into both portals. Local connectors (Claude MCPB) also need a Privacy Policy section — remote connectors still need a privacy URL on the listing. |
| A4 | **Demo tenant + reviewer login** | Dedicated OvalEdge user with realistic catalog/governance sample data. **No MFA / SMS / email OTP** on the IdP path reviewers use. Credentials must work **off-VPN**. Okta: a demo user in the MCP app assignment. |
| A5 | **WAF / IP allowlists** | If WAF is on (`--waf`), allow Anthropic `160.79.104.0/21` and refresh OpenAI ranges from [https://openai.com/chatgpt-connectors.json](https://openai.com/chatgpt-connectors.json) (see [IP egress ranges](https://developers.openai.com/api/docs/guides/ip-addresses)). IP allowlisting does **not** replace OAuth. Prefer leaving WAF off for directory review unless you automate prefix updates. |
| A6 | **Icon / listing copy** | PNG icon (reuse `GET /brand/ovaledge-mcp-icon.png` on the MCP host). Claude listing: name ≤100 chars, tagline ≤55, description ≤2000. OpenAI: logo + starter prompts (plugin `defaultPrompt` is a starting point). |
| A7 | **Per-tenant MCP hosts** | Each customer often has their own MCP URL. **Claude Connectors Directory:** choose **URL pattern** in the Connection step (not a single Universal URL) and document how customers substitute the host. **OpenAI:** Template MCP Server URL is **trusted-partner only** — until you have that relationship, list a **universal demo URL** and tell customers to add a custom connector/plugin pointed at their tenant. |

### B. Claude Connectors Directory (claude.ai)

Portal: Claude.ai **organization settings → directory submissions** (Owners). Docs:
[Submitting to the Connectors Directory](https://claude.com/docs/connectors/building/submission).

| # | Item | How to achieve it |
|---|------|-------------------|
| B1 | **Team/Enterprise + Directory access** | Individual Claude plans cannot submit. On Team, only Owners. On Enterprise, Owners can grant a custom role with **Directory**. |
| B2 | **Connect the server** | HTTPS `/mcp`, Streamable HTTP. Confirm OAuth (DCR via this server’s `POST /register`, or CIMD if you later advertise it). |
| B3 | **Tools sync** | Portal reads `title` + annotations. Fix any “missing title/annotations” on the server **before** submit (already enforced in `tests/client/test_mcp_surface_inventory.py`). |
| B4 | **Listing + use cases + company** | Name, tagline, description, 1–5 categories, docs URL (this file or [SETUP_CLAUDE.md](SETUP_CLAUDE.md)), privacy URL, support contact, icon, **permanent slug**. |
| B5 | **Test & launch** | Written steps so a reviewer can Connect end-to-end. Confirm you ran every tool (MCP Inspector or a custom Claude connector). |
| B6 | **Seven compliance acknowledgments** | Directory guidelines, first-party API, financial transactions, AI media, prompt injection, conversation data, public documentation — all required. |
| B7 | **Allowed link URIs (optional)** | Only origins you own, if the connector uses `ui/open-link`. Omit if unused (users get a confirm prompt). |

Skills are **not** a standalone Claude connector type — they ship in the **plugin**.

### C. Claude Plugin Directory (Claude Code / Cowork)

| # | Item | How to achieve it |
|---|------|-------------------|
| C1 | **Public GitHub** | Closed-source plugins are rejected. Publish `plugins/claude-ovaledge/` (this repo or a dedicated public repo). |
| C2 | **Replace marketplace placeholders** | Point `repository` / `homepage` in `.claude-plugin/plugin.json` at the public URL. Keep `.mcp.json` on `${user_config.mcp_url}` so each user pastes **their** HTTPS `/mcp`. |
| C3 | **Validate** | `claude plugin validate plugins/claude-ovaledge` (add `--strict` in CI if you want). |
| C4 | **Submit** | [claude.ai plugin form](https://claude.ai/admin-settings/directory/submissions/plugins/new) or [Console](https://platform.claude.com/plugins/submit). After publish, GitHub updates are mirrored; you do not re-submit the form for routine commits. |
| C5 | **Private teams (no directory)** | `claude plugin marketplace add` against this repo (`.claude-plugin/marketplace.json`) or `claude --plugin-dir plugins/claude-ovaledge`. |

### D. OpenAI / Codex Plugins Directory (ChatGPT + Codex)

Submit **With MCP** (the production HTTPS URL), not a local `plugin_asdk_app…` id.
Docs: [Submit plugins](https://developers.openai.com/plugins/deploy/submission),
[Remote MCP review](https://developers.openai.com/plugins/deploy/app-review),
[Submission errors](https://developers.openai.com/plugins/deploy/submission-errors).

| # | Item | How to achieve it |
|---|------|-------------------|
| D1 | **Global data residency project** | EU-residency projects cannot submit MCP plugins. Use a **global** Platform project. |
| D2 | **Domain verification** | Portal shows a token. Set `OPENAI_APPS_CHALLENGE` and redeploy. Confirm `curl -sS https://YOUR_PUBLIC_MCP_BASE_URL/.well-known/openai-apps-challenge` prints **exactly** that token. Click **Verify Domain**. Parent-origin hosting is allowed if you cannot put the file on the MCP host. |
| D3 | **Scan Tools** | Paste the production `/mcp` URL + OAuth details. Re-scan after annotation or schema changes. Justifications **explain** server-advertised hints; they do not override them. |
| D4 | **Annotation justifications** | Paste the table in [Annotation justifications](#annotation-justifications-openai-portal) into the portal fields. |
| D5 | **Exactly 5 positive + 3 negative test cases** | Use [Suggested directory test cases](#suggested-directory-test-cases). Run them on ChatGPT (developer mode) **and** Codex against the demo tenant; paste actual vs expected. |
| D6 | **Demo recording URL** | Record the main read + one governed-write preview (do not complete a write unless the demo account is disposable). Host the video (unlisted is fine if the reviewer link works without login). |
| D7 | **Release notes** | One short paragraph: first listing of OvalEdge MCP for ChatGPT and Codex. |
| D8 | **Okta redirect for ChatGPT** | After creating the draft, copy `https://chatgpt.com/connector/oauth/{callback_id}` from the app page into the Okta Sign-in redirect URI list. Also keep the legacy `https://chatgpt.com/connector_platform_oauth_redirect`. Codex CLI: add the **exact** loopback URI printed by `codex mcp add`. |
| D9 | **Privacy vs tool payloads** | Review tool JSON for unnecessary PII, trace IDs, or secrets. Disclose in the privacy policy only what you actually return. |
| D10 | **No MCP Apps UI** | This server has no UI templates — do **not** upload screenshots (`screenshots_not_allowed` if you do). |
| D11 | **Workspace-only (skip public directory)** | ChatGPT developer mode, or install `plugins/codex-ovaledge` from `.agents/plugins/marketplace.json`. Replace `YOUR_PUBLIC_MCP_BASE_URL` in `mcp.json` first. Workspace Publish is org-scoped, not the public directory. |

EU residency, Template URLs, and enhanced directory placement are **out of band** with OpenAI (support / partner contact). Do not invent a template URL in the form unless they enabled it.

---

## Annotation justifications (OpenAI portal)

Every tool is limited to the **authenticated OvalEdge tenant** → `openWorldHint=false`.
Governed writes require preview, then the user sets `write_confirmed_by_user=true`.

| Tool | `readOnlyHint` | `destructiveHint` | Justification |
|------|----------------|-------------------|---------------|
| `asset_explorer` | true | false | Catalog search only; no persistence. |
| `asset_details` | true | false | Reads one asset; no persistence. |
| `asset_lineage` | true | false | Reads lineage graph; no persistence. |
| `metadata_changes_between_crawls` | true | false | Reads crawl diffs; no persistence. |
| `knowledge_search` | true | false | Searches org knowledge / product docs; no persistence. |
| `access_explorer` | true | false | Reads catalog permissions or native grants; does not grant or revoke. |
| `create_glossary_term` | false | false | Confirm-gated **create** of a glossary term. |
| `create_tag` | false | false | Confirm-gated **create** of a tag. |
| `create_service_request` | false | false | Confirm-gated **create** of a service-desk ticket. |
| `update_asset_descriptions` | false | true | Confirm-gated **overwrite** of business/technical descriptions. |
| `update_cde_associations` | false | true | Confirm-gated **overwrite** of CDE associations. |
| `update_governance_roles` | false | true | Confirm-gated **overwrite** of stewardship/governance roles. |
| `update_custom_field_value` | false | true | Confirm-gated **overwrite** of a custom field value. |
| `dq_rule_advisor` | false | false | Can **execute** proposed SQL on a source connection (validate step); does not delete rules. |
| `dq_rule_manager` | false | false | Confirm-gated **create**/associate of DQ rules; not a delete/overwrite of arbitrary catalog rows. |

If you add a tool, update this table **and** `server/tools/common/annotations.py` in the same change.

---

## Suggested directory test cases

Rewrite expected output against the **demo tenant** before paste. Keep cases unambiguous.

**Positive (5)**

1. “Find tables related to sales.” → `asset_explorer` (no `object_type` unless implied); shortlist; optional `asset_details`. Expect catalog hits, not an access tool.
2. “Show details for \<demo table\>.” → `asset_details` after a known id from (1). Expect `formattedResponse` / navLink.
3. “Search OvalEdge knowledge for data classification.” → `knowledge_search`. Expect docs/knowledge hits.
4. “Who has native access to \<demo Snowflake/Redshift object\>?” → after the user confirms native intent, `access_explorer` `operation=source_system_access`. Expect grants, not catalog search.
5. “Propose a glossary term \<demo name\> but do not write yet.” → `create_glossary_term` **without** `write_confirmed_by_user`. Expect a preview (`confirm_create`), no persisted term.

**Negative (3)**

1. “Delete this table from the warehouse.” → no warehouse-delete tool; refuse or explain out of scope.
2. “Who has access to \<object\>?” with **no** native vs catalog-permissions choice → do **not** call access tools; ask the user to pick.
3. Governed write with `write_confirmed_by_user=true` **before** the user approved a preview → server must reject / still preview; no persist.

---

## Local smoke (before any portal)

```bash
# Domain challenge (after OPENAI_APPS_CHALLENGE is set)
curl -sS "https://YOUR_PUBLIC_MCP_BASE_URL/.well-known/openai-apps-challenge"

# OAuth discovery (AUTH_MODE=remote)
curl -sS "https://YOUR_PUBLIC_MCP_BASE_URL/.well-known/oauth-authorization-server" | jq .issuer

# Claude plugin layout
claude plugin validate plugins/claude-ovaledge
```

Replace `YOUR_PUBLIC_MCP_BASE_URL` with the host from `MCPPublicBaseUrl` (no `/mcp` on well-known URLs; keep `/mcp` on the connector URL).
