# MCP workflows, tools, and resources

This document describes how the OvalEdge MCP server exposes **tools**, **resources**, and **workflow prompts** to agents. It is served as a static doc resource at `docs://ovaledge/mcp_workflows` (alongside other files in `server/docs/`).

There is **no MCP protocol “tool priority” field**. Routing is guided by:

1. **Server instructions** (`server/app.py`) — global behavior for every session  
2. **Tool descriptions** — when to call each tool (budget enforced by `tests/tools/test_tool_description_budget.py`; classification via `classify_tool_desc()`)
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
| Associate objects to data quality rule | `associate_dq_rule_objects` (after `assess_cde_dq` / `lookup_dq_rule`) |
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

Use **`source_system_access`** for **native** grants harvested from Redshift, Snowflake, or Tableau (RDAM SQL only — **no Elasticsearch**). This is **not** OvalEdge catalog ACL (`get_user_object_access`) and **not** catalog discovery.

**Never fall back to `search_catalog_assets`** when RDAM is empty, not-found, or errors — catalog search cannot return native grants. Report the RDAM/API outcome instead.

**Workflow prompt:** `native_source_access` (pass `source_system` and the user’s question).

| Parameter | Values / notes |
|-----------|----------------|
| `source_system` | **Required** — `redshift`, `snowflake`, `tableau` |
| `query_direction` | **Required** — infer from question: `user_to_objects`, `object_to_users`, `browse` |
| `username` | **Required** for `user_to_objects` only |
| `object_path` | **Required** for `object_to_users` (exact). Optional parent scope for `browse`. For `user_to_objects` + `connection_id` + `object_type=table`, omit to list all tables on the connector |
| `object_type` | **Required** for `browse` and whenever `object_path` is set |
| `include_columns` | Redshift only — column-level grants (default false) |
| `connection_id` | **Required** for `browse`; strongly recommended for grants — from the user only, do not probe |
| `resolve_all_matches` | When `object_path` is ambiguous, return all matches (max 50); default returns `matchCandidates` |

### Query direction

| Direction | Provide | Example question |
|-----------|---------|------------------|
| `user_to_objects` | `username`; scope via `object_path`/`object_type`/`connection_id` as needed | “What can `svc_analytics` access on `BUSINESS.BANKING`?” → `object_type=schema` |
| `user_to_objects` (all tables on connector) | `username`, `connection_id`, `object_type=table` (omit `object_path`) | “What **tables** can `svc_analytics` query?” |
| `user_to_objects` (database level) | `username`, `object_path=BUSINESS`, `object_type=database`, `connection_id` | “What **database-level** permissions does `john_analyst` have?” |
| `object_to_users` | `object_path`, `object_type`, `connection_id` recommended | “Who has native access to `prod_db.public.orders`?” (`object_type=table`) |
| `browse` | `connection_id`, `object_type`; optional `object_path` as parent | “List tables in `BUSINESS.BANKING`” |

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

### DAM object browse + scoped “who has access to all …”

Use **`source_system_access`** for inventory browse and scoped grant rollups:

| User intent | Approach |
|-------------|----------|
| List databases / schemas / tables / columns in DAM | `source_system_access` with `query_direction=browse` |
| Who can access **one** table or schema grant | `source_system_access` `object_to_users` (default `scope_mode=exact`) |
| Who has access to **all objects under** a schema or database | `source_system_access` with `scope_mode=descendants` |
| Schema inventory **and** access audit | Browse tables/columns, then scoped grants call |

Do not use `search_catalog_assets` for either browse or native grants.

### Grant models (what to expect in the response)

- **Redshift:** direct user, group, and role grants (`grant_mechanism`: direct | group | role).
- **Snowflake:** role assignment only (no direct user grants / groups).
- **Tableau:** direct site-user grants and site-group grants on project/report (`grant_mechanism`: direct | group). Group access is expanded via harvested `rdam_usergroup` membership.

**Authorization:** Instance or Connector **Data Access Admin** is enforced server-side; callers without DAA on the scoped connection see RDAM no-access. See [governance_model](governance_model#data-access-admin-daa). Deep routing (agent rules, privilege map, disambiguation): [rdam_source_access](rdam_source_access).

## Catalog object access (`get_user_object_access`)

OvalEdge **catalog ACL** grants (metadata read/write, data permissions) — **not** native DB/BI grants (`source_system_access`).

**Workflow prompt:** `catalog_object_access`.

| Direction | Use when |
|-----------|----------|
| `user_to_object` | What access does user X have on object Y? (`username` required) |
| `object_to_principals` | Which users and roles have access on object Y? |

**Asset resolution (exactly one):** `object_id` + `object_type` (preferred after `search_catalog_assets`), `fully_qualified_name`, or `object_name` (may return `matchCandidates`).

**Connectors:** `object_type=connection` (aliases: `connector`, `data source`) with `object_name`. Connectors are not in catalog search — resolve by display name or pass `object_id` from data-sources.

**JDBC-backed types** (may be absent from Elasticsearch — use exclusive `search_catalog_assets` then access with ids from the hit):

| Type | object_type | Notes |
|------|-------------|--------|
| Data Domains | `dp_domain` | Search alone, not combined with other types |
| Data Products | `dp_product` | Includes unpublished |
| Glossary Domains | `oeglobaldomain` | Search alone |
| Story Zones | `storyzone` | Search alone |
| Data Stories | `oestory` | Access inherited from parent Story Zone — present `inheritedFrom` |

When the user names a catalog asset, call `search_catalog_assets` first, then pass `object_id` and `object_type` from the chosen hit.

## Update asset descriptions (`update_asset_descriptions`)

**Workflow prompt:** `document_asset_descriptions`.

Resolve `object_id` via `search_catalog_assets`, `lookup_glossary_term`, or `lookup_tags` — do not guess ids. Required: `object_id`, `object_type`, and an explicit description slot.

If the user says only "description", ask which slot applies — do not guess `business_description` vs `technical_description`. For multi-slot types, a typed field without `clientContext.prompt` naming the slot is rejected (HTTP 400).

**Field applicability** (server returns 400 for unsupported combinations):

| object_type group | Allowed fields |
|-------------------|----------------|
| Catalog assets (`oeschema`, `oetable`, `oecolumn`, `oefile`, `oefilecolumn`, `oechart`, `chartchild`, `oeapi`, `oeapicolumn`, `code`) | `business_description`, `technical_description` |
| Glossary (`glossary`) | `business_description`, `detailed_description` (Draft terms only) |
| Data product (`dp_product`) | `business_description`, `detailed_description` |
| Glossary Global Domain (`oeglobaldomain`) | `domain_description` |
| Data Domain (`dp_domain`) | `domain_description` |
| Tag (`oetag`) | `tag_description` |
| Master tag (`mastertag`) | `master_tag_description` |

**Confirm gate:** call without `write_confirmed_by_user` for `confirm_update` preview → user approval → re-call with `write_confirmed_by_user=true` (unless `dry_run=true`).

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
| `catalog_object_access` | OvalEdge catalog ACL (`get_user_object_access`) |
| `dam_object_browse` | DAM inventory browse via `source_system_access` |

### Governed writes (human-in-the-loop)

| Prompt | Purpose |
|--------|---------|
| `create_business_glossary_term` | Guided `create_glossary_term` with pickers and confirm gate |
| `create_governance_tag` | Guided `create_tag` (secure/open) with confirm gate |
| `document_asset_descriptions` | Draft + user confirm → `update_asset_descriptions` |
| `assign_governance_roles` | Resolve target → confirm → `update_governance_roles` |

## Human confirmation before write (MCP-only)

`create_glossary_term`, `create_tag`, `update_asset_descriptions`, and `update_governance_roles` require **`write_confirmed_by_user=true`** on the call that performs the OvalEdge POST (unless `dry_run=true` on update tools). Earlier calls return **`confirm_create`** or **`confirm_update`** previews (`doNotCreate` / `doNotUpdate`) with `formattedResponse` — the agent must show them and wait for explicit user approval.

This gate is enforced in the MCP server only; **no OvalEdge backend change** is required.

See also: [glossary_guide](glossary_guide), [tags_guide](tags_guide), [data_stories](data_stories), [governance_model](governance_model).

## CDE / DQ intelligence (MCP)

| Step | Tool | Notes |
|------|------|--------|
| Find CDE assets | `search_catalog_assets` | Set `critical_data_element=Yes`; object types `oetable`, `oecolumn`, `oefile`, `oefilecolumn` |
| Read-only assessment | `assess_cde_dq` | Pass `objects` from search hits, or `discover_cde_columns=true` to auto-discover CDE columns |
| Resolve existing rule | `lookup_dq_rule` | DQ rules are not in catalog search |
| Link to data quality rule | `associate_dq_rule_objects` | Requires `dqrule_id` from assessment or lookup; user must approve write |
| Create + associate | `create_dq_rules` | Re-assesses internally; prefer existing rule or auto-create data quality rule when criteria sufficient |

**Workflow prompt:** `assess_cde_dq_coverage` (pass `scope` = user question or domain name).

Read-only path: search → `assess_cde_dq` only. Do not call write tools without explicit user approval (unlike glossary/tag, these DQ writes do not use `write_confirmed_by_user`; approval is conversational).
