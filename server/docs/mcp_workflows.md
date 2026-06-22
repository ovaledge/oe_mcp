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
| CDE columns / DQ function & rule recommendations | `assess_cde_dq` (after `search_catalog_assets` or `discover_cde_columns=true`) |
| Associate objects to draft DQ rule | `associate_dq_rule_objects` (after `assess_cde_dq` / `lookup_dq_rule`) |
| Auto-create or associate DQ rules for CDE columns | `create_dq_rules` (assess + create/associate in one call) |
| Metadata drift between crawls | `metadata_changes_between_crawls` |
| Native Redshift/Snowflake/Tableau grants | `source_system_access` |
| Lineage | `asset_lineage` |
| Column stats | `column_profile_statistics` |
| Table relationships | `table_entity_relationships` |
| Create glossary term | `create_glossary_term` (guided; human confirms) |
| Create tag | `create_tag` (guided; human confirms) |
| Update descriptions | `update_asset_descriptions` |
| Update governance roles | `update_governance_roles` |
| Update custom / additional field | `search_catalog_assets` (if needed) → GET custom-fields → `update_custom_field_value` |

**Data stories vs platform docs:** `lookup_datastory` searches **your organization’s** onboarded stories (`oestory`). `search_platform_docs` searches **OvalEdge product** documentation. Do not use platform docs for internal policy questions.

## Catalog search (`search_catalog_assets`)

Extended parameter patterns (tool description keeps a short summary; use this section when disambiguating filters):

| User intent | Suggested parameters |
|-------------|---------------------|
| Certified tables in a schema | `object_type=oetable`, `schema_name`, optional `search_terms` |
| Assets by connector technology | `server_type` (e.g. mysql, snowflake, tableau) + `context_query` |
| Data products | `data_products=[...]`, `context_query` |
| Custom field values | `custom_fields=[...]` or `search_terms` fallback |
| Data Domains (not glossary Global Domain) | `object_type=dp_domain` alone — do not combine with other types |
| PII / classification | `classifications=["PII"]`, `context_query` |
| Glossary terms in placement | `object_type=glossary`, `domain_name`, optional `category_name` |
| Assets linked to domain terms | `object_type=oetable`, `domain_name` |
| CDE columns | `object_type=oecolumn`, `critical_data_element=["Yes"]` → then `assess_cde_dq` |

**Glossary placement:** `domain_id` or `domain_name` (required), plus optional category/subcategory. With `object_type=glossary`, returns terms in that placement; without `object_type`, returns catalog assets linked to terms there.

**server_type:** Infer from the user question when they name a technology; omit when not implied — do not guess.

Omit empty list parameters; filter-only search is valid. Each hit includes `objectId`, `objectType`, `navLink`, `redirectUrl`. For `oestory` hits, follow with `lookup_datastory`.

## Native source access (RDAM)

Use **`source_system_access`** for **native** grants harvested from Redshift, Snowflake, or Tableau (RDAM SQL only — **no Elasticsearch**). This is **not** OvalEdge catalog ACL (`get_catalog_object_access` may ship later) and **not** catalog discovery.

**Never fall back to `search_catalog_assets`** when RDAM is empty, not-found, or errors — catalog search cannot return native grants. Report the RDAM/API outcome instead.

**Workflow prompt:** `native_source_access` (pass `source_system` and the user’s question).

| Parameter | Values / notes |
|-----------|----------------|
| `source_system` | `redshift`, `snowflake`, `tableau` |
| `query_direction` | See below |
| `username` | **Required** on every call |
| `object_path` | **Required** — path at the queried level (`BUSINESS`, `BUSINESS.BANKING`, `db.schema.table`, etc.) |
| `object_type` | **Required** — RDAM level: `database`, `schema`, `table`, `column` (Redshift), `project`, `report` (Tableau) |
| `include_columns` | Redshift only — column-level grants (default false) |
| `connection_id` | **Required** — OvalEdge connector id |
| `resolve_all_matches` | When `object_path` is ambiguous, return all matches (max 50); default returns `matchCandidates` |

### Query direction

| Direction | Provide | Example question |
|-----------|---------|------------------|
| `user_to_objects` | `username`, `object_path`, `object_type`, `connection_id` | “What can `svc_analytics` access on `BUSINESS.BANKING`?” → `object_type=schema` |
| `user_to_objects` (database level) | `username`, `object_path=BUSINESS`, `object_type=database`, `connection_id` | “What **database-level** permissions does `john_analyst` have?” |
| `object_to_users` | `username`, `object_path`, `object_type`, `connection_id` | “Who has native access to `prod_db.public.orders`?” (`object_type=table`) |

### `object_path` formats

**Redshift / Snowflake** (dot-separated; level inferred by segment count):

- Database: `dbName` (e.g. `BUSINESS`)
- Schema: `dbName.schema`
- Table: `dbName.schema.table` (e.g. `BUSINESS.BANKING.ALERTS`)
- Column (Redshift only, with `include_columns=true`): `dbName.schema.table.column`
- Optional **connection name** prefix when names collide: `connectionName.dbName`, `connectionName.dbName.schema.table`, etc. Prefer **`connection_id`** to scope instead of guessing the prefix.

**Tableau:**

- Project: `Project Name`
- Report: `Project/Report Name`

Partial paths (e.g. table name only) may return **`matchCandidates`** — disambiguate with a full path from the response, or set `resolve_all_matches=true`.

### Grant models (what to expect in the response)

- **Redshift:** direct user, group, and role grants (`grant_mechanism`: direct | group | role).
- **Snowflake:** role assignment only (no direct user grants / groups).
- **Tableau:** direct site-user grants and site-group grants on project/report (`grant_mechanism`: direct | group). Group access is expanded via harvested `rdam_usergroup` membership.

**Authorization:** Instance or Connector **Data Access Admin** is enforced server-side; callers without DAA on the scoped connection see RDAM no-access. See [governance_model](governance_model#native-source-access-rdam).

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
| `assess_cde_dq_coverage` | CDE columns: catalog search → read-only `assess_cde_dq`; optional writes after approval |

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

See also: [glossary_guide](glossary_guide), [tags_guide](tags_guide), [data_stories](data_stories), [governance_model](governance_model).

## CDE / DQ intelligence (MCP)

| Step | Tool | Notes |
|------|------|--------|
| Find CDE assets | `search_catalog_assets` | Set `critical_data_element=Yes`; object types `oetable`, `oecolumn`, `oefile`, `oefilecolumn` |
| Read-only assessment | `assess_cde_dq` | Pass `objects` from search hits, or `discover_cde_columns=true` to auto-discover CDE columns |
| Resolve existing rule | `lookup_dq_rule` | DQ rules are not in catalog search |
| Link to draft rule | `associate_dq_rule_objects` | Requires `dqrule_id` from assessment or lookup; user must approve write |
| Create + associate | `create_dq_rules` | Re-assesses internally; prefer existing rule or auto-create draft when criteria sufficient |

**Workflow prompt:** `assess_cde_dq_coverage` (pass `scope` = user question or domain name).

Read-only path: search → `assess_cde_dq` only. Do not call write tools without explicit user approval (unlike glossary/tag, these DQ writes do not use `create_confirmed_by_user`; approval is conversational).
