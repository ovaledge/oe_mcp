# MCP workflows, tools, and resources

This document is the **agent routing guide** for the OvalEdge MCP server. It is served as a static MCP resource at **`docs://ovaledge/mcp_workflows`** (alongside other files in `server/docs/`).

**Agents must read this resource** at session start and before multi-step workflows, governed writes, native source access (RDAM), catalog ACL checks, or DQ operations. Server instructions (`server/app.py`) and tool descriptions link here; workflow prompts assume you have loaded this guide or an equivalent section.

Canonical inventories (used by tests): **`server/mcp_surface.py`** — `MCP_TOOL_NAMES` (20 tools), `MCP_WORKFLOW_PROMPT_NAMES` (21 prompts), `MCP_OVALEDGE_RESOURCE_TEMPLATES` (5 object-detail templates).

There is **no MCP protocol “tool priority” field**. Routing is guided by:

1. **Server instructions** (`server/app.py`) — global behavior for every session  
2. **This document** (`docs://ovaledge/mcp_workflows`) — full routing index and playbooks  
3. **Tool descriptions** — per-tool when-to-call (budget: `tests/tools/test_tool_description_budget.py`)  
4. **Workflow prompts** (`server/prompts/workflows/`) — optional multi-step playbooks  
5. **Domain guides** — `docs://ovaledge/glossary_guide`, `tags_guide`, `rdam_source_access`, etc.  
6. **Client rules** (e.g. Cursor project rules) — host-specific, outside this repo  

## Tool routing (quick reference)

| User intent | Start with |
|-------------|------------|
| Find tables, files, reports, columns | `asset_explorer` → `asset_details` |
| Rich metadata, column profile, or table relationships | `asset_details` (after search or when `object_id` known) |
| Org policies, playbooks, narratives, or OvalEdge product how-to | `knowledge_search`; prompts `organizational_knowledge`, `platform_help` |
| Business term definition | `asset_explorer` with `name` and `object_type=glossary`; prompt `explain_business_term` |
| Tag meaning or hierarchy | `asset_explorer` with `name` and `object_type=oetag`; prompt `explain_tag` |
| Data quality rule lookup | `lookup_dq_rule`; prompt `explain_dq_rule` |
| CDE assets / DQ function & rule recommendations | `assess_cde_dq` (after `asset_explorer` or `discover_cde_columns=true`) |
| Associate objects to existing data quality rule | `associate_dq_rule_objects` (after `assess_cde_dq` / `lookup_dq_rule`; confirm gate) |
| Find same-function rules before creating | `create_dq_rules` with `prefer_existing_rule=true` (default); user chooses a returned rule ID or explicitly requests new |
| Create a **new** data quality rule (second rule / explicit new) | `create_dq_rules` with `prefer_existing_rule=false`; often `skip_duplicate_function_on_object=false` |
| Mark object as CDE before auto-create | `update_cde_associations` (confirm gate) → then `create_dq_rules` |
| Generate custom SQL data quality queries | `generate_dq_queries` (after `assess_cde_dq` when workflow is `custom_sql`) |
| Validate custom SQL data quality queries | `validate_dq_queries` (confirm gate; executes SELECT on connection) |
| Create custom SQL data quality rule | `create_sql_dq_rule` (confirm gate; after validate when `canCreateRule`) |
| CDE / custom SQL DQ workflow (prompt) | `create_custom_sql_dq_workflow` or `assess_cde_dq_coverage` |
| Metadata drift between crawls | `metadata_changes_between_crawls`; prompt `metadata_drift` |
| Native Redshift/Snowflake/Tableau grants | `source_system_access`; prompts `native_source_access`, `dam_object_browse` |
| OvalEdge catalog ACL (user/role on catalog objects) | `get_user_object_access`; prompt `catalog_object_access` |
| Lineage | `asset_lineage`; prompt `trace_data_lineage` |
| Column stats / table relationships | `asset_details` (automatic for `oetable`/`oefile`; relationships for `oetable`); prompt `find_related_assets` |
| Trust / certification scorecard | prompt `trust_assessment` |
| Domain overview (terms, tables, stories) | prompt `explore_data_domain` |
| Create glossary term | `create_glossary_term` (guided; human confirms); prompt `create_business_glossary_term` |
| Create tag | `create_tag` (guided; human confirms); prompt `create_governance_tag` |
| Update descriptions | `update_asset_descriptions`; prompt `document_asset_descriptions` |
| Update governance roles | `update_governance_roles`; prompt `assign_governance_roles` |
| Update CDE flag on tables/columns/files | `update_cde_associations` (confirm gate) |
| Update custom / additional field | `asset_explorer` (if needed) → `update_custom_field_value` (confirm gate) |

**Knowledge search:** `knowledge_search` searches both your organization’s onboarded data stories (`oestory`) and OvalEdge product documentation. It has no corpus enum; use the question context and returned citations to distinguish the result source.

## Registered MCP tools (inventory)

| Domain | Tool | Governed write |
|--------|------|----------------|
| Catalog | `asset_explorer` | — |
| Catalog | `asset_details` | — |
| Catalog | `asset_lineage` | — |
| Catalog | `metadata_changes_between_crawls` | — |
| Catalog | `update_asset_descriptions` | confirm gate |
| Catalog | `update_cde_associations` | confirm gate |
| Governance | `create_glossary_term` | confirm gate |
| Governance | `create_tag` | confirm gate |
| Governance | `update_governance_roles` | confirm gate |
| Governance | `update_custom_field_value` | confirm gate |
| Data quality | `lookup_dq_rule` | — |
| Data quality | `assess_cde_dq` | — |
| Data quality | `associate_dq_rule_objects` | confirm gate |
| Data quality | `create_dq_rules` | confirm gate |
| Data quality | `generate_dq_queries` | — |
| Data quality | `validate_dq_queries` | confirm gate |
| Data quality | `create_sql_dq_rule` | confirm gate |
| Access | `get_user_object_access` | — |
| RDAM | `source_system_access` | — |
| Knowledge | `knowledge_search` | — |

## Asset explorer (`asset_explorer`)

Extended parameter patterns (tool description keeps a short summary; use this section when disambiguating filters):

| User intent | Suggested parameters |
|-------------|---------------------|
| Certified tables in a schema | `object_type=oetable`, `schema_name`, optional `search_terms` |
| Assets by connector technology | `server_type` (e.g. mysql, snowflake, tableau) + `context_query` |
| Data products | `data_products=[...]`, `context_query` |
| Custom field values | `custom_fields=[...]` or `search_terms` fallback |
| Data Domains (not glossary Global Domain) | `object_type=dp_domain` alone — do not combine with other types |
| Report Groups | `object_type=oedomain` alone — do not combine with other types |
| PII / classification | `classifications=["PII"]`, `context_query` |
| Assets by exact tag name | `tags=["Customer and Sales"]` — exact tag name (case-insensitive), not FQN/description contains |
| Assets by exact glossary term | `terms=["Payment"]` — exact term name (case-insensitive), not description/domain contains |
| Glossary terms in placement | `object_type=glossary`, `domain_name`, optional `category_name` |
| Assets linked to domain terms | `object_type=oetable`, `domain_name` |
| CDE columns | `object_type=oecolumn`, `critical_data_element=["Yes"]` → then `assess_cde_dq` |

**Glossary placement:** `domain_id` or `domain_name` (required), plus optional category/subcategory. With `object_type=glossary`, returns terms in that placement; without `object_type`, returns catalog assets linked to terms there.

**server_type:** Infer from the user question when they name a technology; omit when not implied — do not guess.

`asset_explorer` is the unified blanket search; it has no operation enum. Omit empty list parameters; filter-only search is valid. Each hit includes `objectId`, `objectType`, `navLink`, `redirectUrl`.

Use `name` plus `object_type=glossary` for a business term, or `name` plus `object_type=oetag` for a tag.

## Asset details (`asset_details`)

Call with `object_id` and `object_type`; `fully_qualified_name` is not supported. The response always includes rich details plus an automatic profile for `oetable`/`oefile` and relationships for `oetable`.

## Knowledge search (`knowledge_search`)

Searches both data stories and OvalEdge product documentation. There is no corpus selector. For organizational questions, search the user’s policy or narrative wording; for product help, search the OvalEdge feature or configuration question. Present returned citations and formatted content when available.

## Who has access? (disambiguate first)

Use workflow prompt **`resolve_object_access`**. Native RDAM → `source_system_access` with `access_intent_confirmed=native`; OvalEdge catalog ACL → `get_user_object_access` with `access_intent_confirmed=catalog_acl`. Skip disambiguation when the question includes native/DAM signals (native, remote, DAM, source system, …) or catalog ACL signals (OE security, ACL, catalog access, …). **Snowflake/Redshift/Tableau alone do not skip disambiguation** — e.g. “Who has access to BUSINESS.BANKING in Snowflake?” and “Who has access to customer1 in redshift1 in Redshift?” both require the **1** / **2** choice first. Server returns `ACCESS_INTENT_REQUIRED` when who-has-access directions omit `access_intent_confirmed`.

## Native source access (RDAM)

Use **`source_system_access`** for **native** grants harvested from Redshift, Snowflake, or Tableau (RDAM SQL only — **no Elasticsearch**). This is **not** OvalEdge catalog ACL (`get_user_object_access`) and **not** catalog discovery.

**Never fall back to `asset_explorer`** when RDAM is empty, not-found, or errors — catalog search cannot return native grants. Report the RDAM/API outcome instead.

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

Do not use `asset_explorer` for either browse or native grants.

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

**Asset resolution (exactly one):** `object_id` + `object_type` (preferred after `asset_explorer`), `fully_qualified_name`, or `object_name` (may return `matchCandidates`).

**Connectors:** `object_type=connection` (aliases: `connector`, `data source`) with `object_name`. Connectors are not in catalog search — resolve by display name or pass `object_id` from data-sources.

**JDBC-backed types** (may be absent from Elasticsearch — use exclusive `asset_explorer` then access with ids from the hit):

| Type | object_type | Notes |
|------|-------------|--------|
| Data Domains | `dp_domain` | Search alone, not combined with other types |
| Data Products | `dp_product` | Includes unpublished |
| Glossary Domains | `oeglobaldomain` | Search alone |
| Story Zones | `storyzone` | Search alone |
| Report Groups | `oedomain` | Search alone (aliases: `reportgroup`); not ES-indexed |
| Data Stories | `oestory` | Access inherited from parent Story Zone — present `inheritedFrom` |

When the user names a catalog asset, call `asset_explorer` first, then pass `object_id` and `object_type` from the chosen hit.

## Update asset descriptions (`update_asset_descriptions`)

**Workflow prompt:** `document_asset_descriptions`.

Resolve `object_id` via `asset_explorer` — do not guess ids. Required: `object_id`, `object_type`, and an explicit description slot.

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

Resources return JSON catalog documents from `GET /api/v1/mcp/asset-details`. When you need rich narrative or citations, use `knowledge_search`; use `asset_explorer` for glossary terms and tags.

| URI template | objectType | Prefer tool for |
|--------------|------------|-----------------|
| `ovaledge://catalog/table/{object_id}` | `oetable` | `asset_details` |
| `ovaledge://catalog/file/{object_id}` | `oefile` | `asset_details` |
| `ovaledge://governance/glossary-term/{object_id}` | `glossary` | `asset_explorer` |
| `ovaledge://governance/data-story/{object_id}` | `oestory` | `knowledge_search` |
| `ovaledge://governance/tag/{object_id}` | `oetag` | `asset_explorer` |

Static platform markdown (this folder): `docs://ovaledge/{filename}`:

| Resource URI | Topic |
|--------------|--------|
| `docs://ovaledge/mcp_workflows` | This routing guide (read first) |
| `docs://ovaledge/overview` | OvalEdge product overview + MCP summary |
| `docs://ovaledge/asset_types` | Catalog `object_type` allow-list |
| `docs://ovaledge/glossary_guide` | Glossary create wizard |
| `docs://ovaledge/tags_guide` | Tag create (OPEN/SECURE) wizard |
| `docs://ovaledge/data_stories` | Data story lookup behavior |
| `docs://ovaledge/governance_model` | Roles, DAA, governance concepts |
| `docs://ovaledge/rdam_source_access` | Deep RDAM routing and disambiguation |

## Workflow prompts

Invoke by name from the MCP client when supported. Each prompt returns instruction text that tells the agent which tools to call in order. **20 prompts** registered (see `MCP_WORKFLOW_PROMPT_NAMES` in `server/mcp_surface.py`).

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
| `explain_dq_rule` | Data quality rule lookup and steward context |
| `platform_help` | OvalEdge product docs via `knowledge_search` |

### Lineage and quality

| Prompt | Purpose |
|--------|---------|
| `trust_assessment` | Scorecard: DQ, certification, lineage, roles |
| `trace_data_lineage` | Upstream/downstream narrative |
| `metadata_drift` | Changes between crawls |
| `assess_cde_dq_coverage` | CDE columns: catalog search → read-only `assess_cde_dq`; optional writes after approval |
| `create_custom_sql_dq_workflow` | CDE assess → associate/create_rules → generate/validate/create SQL via thin DQ tools |

### Access

| Prompt | Purpose |
|--------|---------|
| `resolve_object_access` | Disambiguate native RDAM vs catalog ACL before calling an access tool |
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
| `assess_cde_dq_coverage` | CDE assess → lookup → associate / `create_dq_rules` with confirm gate |
| `create_custom_sql_dq_workflow` | Custom SQL path: `generate_dq_queries` → `validate_dq_queries` → `create_sql_dq_rule` |

## Update CDE associations (`update_cde_associations`)

Mark or unmark **Critical Data Element (CDE)** on catalog objects — tables, columns, files, file columns, schemas, charts, APIs, and queries. Resolve targets via `asset_explorer` first.

**Required before auto-create:** `create_dq_rules` skips objects that are not **CDE=Yes** (per-row message explains this).

**Confirm gate:** call without `write_confirmed_by_user` for `confirm_update` preview → user approval → re-call with `write_confirmed_by_user=true` and `confirmation_token` from the preview.

Often used before DQ workflows when the user wants to mark a table or column as CDE, or change CDE coverage after `assess_cde_dq`.

## Human confirmation before write (MCP-only)

`create_glossary_term`, `create_tag`, `update_asset_descriptions`, `update_governance_roles`, `update_custom_field_value`, `update_cde_associations`, `associate_dq_rule_objects`, `create_dq_rules`, `validate_dq_queries`, and `create_sql_dq_rule` require **`write_confirmed_by_user=true`** on the call that performs the OvalEdge POST (unless `dry_run=true` on update tools). Earlier calls return **`confirm_create`** or **`confirm_update`** previews (`doNotCreate` / `doNotUpdate`) with `formattedResponse` and **`confirmationToken`** — the agent must show them and wait for explicit user approval.

This gate is enforced in the MCP server (preview tokens, `write_confirmed_by_user`). The OvalEdge backend enforces RBAC and business rules on the actual POST (e.g. CDE prerequisite and skip reasons on `create_dq_rules`).

See also: [glossary_guide](glossary_guide), [tags_guide](tags_guide), [data_stories](data_stories), [governance_model](governance_model).

## CDE / DQ intelligence (MCP)

End-to-end routing for function-based and custom-SQL data quality workflows.

### Read-only path

1. `asset_explorer` with `critical_data_element=Yes` (types: `oetable`, `oecolumn`, `oefile`, `oefilecolumn`), **or** pass known `objects` to `assess_cde_dq`.
2. `assess_cde_dq` — recommended function and `existingRulesForFunction` (all active rules using that function, purpose-ranked but never filtered by purpose).
3. Optional: `lookup_dq_rule` when the user names an existing rule (rules are not in catalog search).

### Write path (function-based auto-create / associate)

| Step | Tool | Notes |
|------|------|--------|
| Mark CDE (prerequisite) | `update_cde_associations` | Object must be **CDE=Yes** before auto-create; tables, columns, files, schemas, charts, APIs, queries; **confirm gate** |
| Select or create | `create_dq_rules` | Re-assesses internally; same-function rules require user selection; new create has **confirm gate** |
| Link to known rule only | `associate_dq_rule_objects` | When `dqrule_id` is known; does not auto-create; **confirm gate** |

**`create_dq_rules` routing (agent):**

| User intent | Parameters |
|-------------|------------|
| One named column/table (after reading its description) | `objects=[{"objectId": <id>, "objectType": "oecolumn"}]`, `discover_cde_columns=false` — **do not** discover-all |
| List / assess all CDE columns in a domain | `discover_cde_columns=true` (or explicit multi-object `objects`) |
| “Create data quality rule” / from business description (default) | `prefer_existing_rule=true` lists every same-function rule; ask user to select an ID or explicitly choose new |
| “Create **new** rule” / second rule / different purpose on same object | `prefer_existing_rule=false`; often `skip_duplicate_function_on_object=false` |
| Criteria only in user message, not in catalog | `supplemental_criteria_text` |
| Pick a function from assess candidates | `preferred_function_name` |
| Rejected top matches — try next-closest | `excluded_function_names` (then re-assess / create) |

**Scope rule:** If the user asked about one asset (e.g. only `createdate`), pass **only** that object. Never widen to every CDE on the table because validation failed or args looked wrong — fix `objects` shape instead (`[{objectId, objectType}]`, not a JSON string).

**Function recommendation (assess):**

1. Match business metadata (description / rule / term text) against catalog DQ function **names and definitions** → ranked `recommendedFunctionCandidates` (top also in `recommendedFunction`).
2. Present candidates to the user. If they reject them, re-call `assess_cde_dq` with `excluded_function_names` for the next-closest set.
3. Only when **no** strong catalog function candidates remain → `recommendedWorkflow=custom_sql` (last resort) with the **best-match OEQUERY SQL function** when available (e.g. **SQL Exact Value** for “equal to X”, **SQL Values Contains** for `IN` / `NOT IN` or allowed-value sets, **SQL Value Range** for ranges) → `generate_dq_queries` / `create_sql_dq_rule` using that `recommendedFunction` verbatim.
4. Weak catalog matches (low score) do **not** block the custom-SQL last resort. Preserve the returned function family through create; do not replace Values Contains or Value Range with Exact Value.

**`prefer_existing_rule` behavior:**

- **`true` (default):** Assessment returns every active rule with the recommended function in `existingRulesForFunction`. Purpose similarity only sorts the list; it never removes a same-function rule. The MCP preview returns `select_existing_rule` without a create token. Ask the user to choose a `dqruleId`, then use `associate_dq_rule_objects`.
- **`false`:** Explicitly request a **new** data quality rule. The normal create confirmation gate applies.
- Criteria are parsed from business metadata first. A create response reports `criteriaSource=business_metadata`, `business_metadata_with_defaults`, `function_default`, `not_required`, or `unresolved`; `criteriaMessage` explains partial/failed parsing, defaults applied, or required manual review.

**Skip / fail messages (per-row `message` — never silent):**

| Situation | Typical message theme |
|-----------|------------------------|
| Not CDE | Mark object as CDE (Yes) before auto-create |
| Already linked (prefer existing) | Already associated to recommended rule |
| Duplicate function (skip dup on) | Object already has a rule for this function type |
| Function not identified / not found | Cannot map business metadata to a DQ function |
| Associate failed | Could not link to recommended rule |
| Rule name exists / insert failed | Create collision or server error |

Missing success/input criteria do **not** block create — function defaults are applied when metadata has none.

Present skipped/failed rows and `message` to the user; fix prerequisites (CDE, flags) before re-calling.

### Custom SQL path

| Step | Tool | Notes |
|------|------|--------|
| Assess | `assess_cde_dq` | When workflow is `custom_sql` |
| Generate SQL | `generate_dq_queries` | Read-only; not for function-based rules (use `create_dq_rules`) |
| Validate | `validate_dq_queries` | Executes SELECT on connection; **confirm gate** |
| Create rule | `create_sql_dq_rule` | After validate when `canCreateRule`; **confirm gate** |

**Workflow prompts:** `assess_cde_dq_coverage` (pass `scope` = user question or domain name); `create_custom_sql_dq_workflow` for the full custom-SQL path.

For all writes: call without `write_confirmed_by_user` for a preview, then re-call with `write_confirmed_by_user=true` and `confirmation_token` after explicit user approval (same pattern as glossary/tag governed writes).
