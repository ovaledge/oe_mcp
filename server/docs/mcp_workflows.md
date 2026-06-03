# MCP workflows, tools, and resources

This document describes how the OvalEdge MCP server exposes **tools**, **resources**, and **workflow prompts** to agents. It is served as a static doc resource at `docs://ovaledge/mcp_workflows` (alongside other files in `server/docs/`).

There is **no MCP protocol “tool priority” field**. Routing is guided by:

1. **Server instructions** (`server/app.py`) — global behavior for every session  
2. **Tool descriptions** — when to call each tool  
3. **Workflow prompts** (`server/prompts/workflows/`) — optional multi-step playbooks  
4. **Client rules** (e.g. Cursor project rules) — host-specific, outside this repo  

## Tool routing (quick reference)

| User intent | Start with |
|-------------|------------|
| Find tables, files, reports, columns | `search_catalog_assets` → `catalog_asset_details` |
| Org policies, playbooks, narrative knowledge in data stories | `lookup_datastory` (`content_query` = question) |
| OvalEdge product how-to (UI, features) | `search_platform_docs` |
| Business term definition | `lookup_glossary_term` |
| Tag meaning or hierarchy | `lookup_tags` |
| DQ rule lookup | `lookup_dq_rule` |
| Metadata drift between crawls | `metadata_changes_between_crawls` |
| Native Redshift/Snowflake/Tableau grants | `get_source_system_access` (alias `user_object_access`) |
| Lineage | `asset_lineage` |
| Column stats | `column_profile_statistics` |
| Table relationships | `table_entity_relationships` |
| Create glossary term | `create_glossary_term` (guided; human confirms) |
| Create tag | `create_tag` (guided; human confirms) |
| Update descriptions | `update_asset_descriptions` |
| Update governance roles | `update_governance_roles` |

**Data stories vs platform docs:** `lookup_datastory` searches **your organization’s** onboarded stories (`oestory`). `search_platform_docs` searches **OvalEdge product** documentation. Do not use platform docs for internal policy questions.

## Resources (deep links by object id)

Resources return JSON catalog documents from `GET /api/v1/mcp/object-details`. When you need rich narrative (story sections, tag create flow), prefer the **lookup tools** listed below.

| URI template | objectType | Prefer tool for |
|--------------|------------|-----------------|
| `ovaledge://catalog/table/{object_id}` | `oetable` | `catalog_asset_details` |
| `ovaledge://catalog/file/{object_id}` | `oefile` | `catalog_asset_details` |
| `ovaledge://governance/glossary-term/{object_id}` | `glossary` | `lookup_glossary_term` |
| `ovaledge://governance/data-story/{object_id}` | `oestory` | `lookup_datastory` |
| `ovaledge://governance/tag/{object_id}` | `oetag` | `lookup_tags` |

Static platform markdown (this folder): `docs://ovaledge/{filename}` (e.g. `docs://ovaledge/glossary_guide`).

## Workflow prompts

Invoke by name from the MCP client when supported. Each prompt returns instruction text that tells the agent which tools to call in order.

### Discovery

| Prompt | Purpose |
|--------|---------|
| `data_discovery` | Find datasets for a business need; glossary cross-check; optional data stories |
| `explore_data_domain` | Domain overview: terms, tables, tags, stories |
| `find_related_assets` | Joins, entity relationships, shared glossary/tags |

### Knowledge

| Prompt | Purpose |
|--------|---------|
| `explain_business_term` | Glossary definition + linked physical assets |
| `organizational_knowledge` | **Data stories first** — internal policies and narratives |
| `explain_tag` | Tag lookup and tagged assets |
| `explain_dq_rule` | DQ rule lookup and steward context |
| `platform_help` | OvalEdge product docs via `search_platform_docs` |

### Lineage and quality

| Prompt | Purpose |
|--------|---------|
| `trust_assessment` | Scorecard: DQ, certification, lineage, roles |
| `trace_data_lineage` | Upstream/downstream narrative |
| `metadata_drift` | Changes between crawls |

### Access

| Prompt | Purpose |
|--------|---------|
| `native_source_access` | Redshift / Snowflake / Tableau native grants (not catalog ACLs) |

### Governed writes (human-in-the-loop)

| Prompt | Purpose |
|--------|---------|
| `create_business_glossary_term` | Guided `create_glossary_term` with pickers and confirm gate |
| `create_governance_tag` | Guided `create_tag` (secure/open) with confirm gate |
| `document_asset_descriptions` | Draft + user confirm → `update_asset_descriptions` |
| `assign_governance_roles` | Resolve target → confirm → `update_governance_roles` |

## Human confirmation before write (MCP-only)

`create_glossary_term`, `create_tag`, `update_asset_descriptions`, and `update_governance_roles` require **`create_confirmed_by_user=true`** on the call that performs the OvalEdge POST (unless `dry_run=true` on update tools). Earlier calls return **`confirm_create`** or **`confirm_update`** previews (`doNotCreate` / `doNotUpdate`) with `formattedResponse` — the agent must show them and wait for explicit user approval.

This gate is enforced in the MCP server only; **no OvalEdge backend change** is required.

See also: [glossary_guide](glossary_guide), [tags_guide](tags_guide), [data_stories](data_stories).
