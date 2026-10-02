---
name: ovaledge-mcp-workflows
description: >
  Route OvalEdge MCP work through the canonical playbooks. Use when the user
  asks about catalog assets, governance, knowledge, native grants, catalog
  permissions, data quality, or service requests.
---

# OvalEdge MCP routing

Before multi-step catalog, governance, access, DQ, or governed-write work, read
the MCP resource `docs://ovaledge/mcp_workflows`. Do **not** invent alternate
tool sequences. Present `formattedResponse` when a tool returns it. Never show
`ovaledge://` URIs; use `navLink` or `redirectUrl`.

## Intent → tool

| Intent | Tool |
|--------|------|
| Org knowledge / OvalEdge product how-to | `knowledge_search` |
| Find physical / catalog assets | `asset_explorer`, then `asset_details` after a shortlist |
| Native DB/BI grants (RDAM) | `access_explorer` `operation=source_system_access` — never fall back to explorer |
| Catalog permissions (OvalEdge user/role grants) | `access_explorer` `operation=catalog_access` |
| File access / content-change / DQ-recommendation tickets | `create_service_request` |
| Ambiguous “who has access” | Ask the user to pick native vs catalog permissions (`resolve_object_access`); call no access tools until they answer |

First-person inventory without a named principal (“what tables can I see?”) →
`asset_explorer`, not `access_explorer`.

## Governed writes

Preview first. Show the preview. Wait for explicit user approval. Only then
repeat with `write_confirmed_by_user=true` and the confirmation token. Never
set that flag before approval.

## Auth

Public ChatGPT / Codex directory listings must use a remote `AUTH_MODE=remote`
HTTPS `/mcp` URL. Directories do not accept stdio or `X-OvalEdge-*` headers.
Replace `YOUR_PUBLIC_MCP_BASE_URL` in this plugin’s `mcp.json` with the deployed
host before install.
