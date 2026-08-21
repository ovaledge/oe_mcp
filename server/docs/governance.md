# Governance (glossary, tags, roles, stories)

Merged guide for business glossary, tags, stewardship/RBAC, CDE, and data stories. Routing playbooks remain in [mcp_workflows](mcp_workflows). Native grants: [rdam_source_access](rdam_source_access).

## Stewardship roles

- **Owner** — Accountable for the asset or definition; typically a business or product owner.
- **Steward** — Day-to-day curator of metadata, quality, and alignment to standards.
- **Custodian** — Often IT or platform-focused; ensures technical implementation, access, and platform policy.

Exact titles vary by organization; OvalEdge stores these roles on assets and glossary objects for accountability.

## Certification lifecycle

Common certification states include:

- **certified** — Reviewed and approved for intended use.
- **cautioned** — Usable with known limitations or pending remediation.
- **violated** — Failed rules or policy; treat as high risk until resolved.
- **inactive** — Deprecated or retired; avoid for new use cases.

Certification is enforced and interpreted in OvalEdge; the MCP surfaces values as returned by the API.

## RBAC

Access to catalog assets, glossary content, lineage nodes, and previews is enforced **only** by OvalEdge. The MCP does not bypass, broaden, or reinterpret permissions. If a user cannot see an object in the OvalEdge UI, they should not expect to retrieve it via MCP.

Write tools (e.g. `create_tag`, `create_glossary_term`, `create_service_request`, `update_asset_descriptions`, `update_governance_roles`) invoke the same OvalEdge APIs as the UI; they succeed only when the authenticated user has the required governance privileges.

The MCP adds **human-in-the-loop** steps for governed writes: picker responses (`formattedResponse`) on creates, explicit confirmation flags, a **`confirmationToken`** that binds the confirmed POST to the previewed payload, and a final **`write_confirmed_by_user`** gate before POST (creates and updates). Agents must not skip pickers or auto-confirm on behalf of users.

## Critical Data Element (CDE)

Catalog assets (schemas, tables, columns, files, reports, APIs, codes) support a **Critical Data Element** designation. Use the `update_cde_associations` MCP tool to set `Yes`, `No`, or `None`, with optional category and justification — matching the catalog UI shutter. Resolve assets via `asset_explorer` first; updates require meta-write permission and are audited in asset history.

## Glossary–catalog sync and inheritance

Terms in the business glossary can be linked to physical columns and tables. When sync is enabled, governance properties (e.g. classifications, masking, restriction flags) may **inherit** from the term to the asset. Responses may indicate whether masking or restriction came from term sync versus direct assignment on the asset.

## Curation score

Curation reflects how complete and trustworthy metadata is—examples of components include descriptions, ownership, glossary linkage, classifications, and quality signals. It complements DQ score: curation is about metadata health; DQ is about measured data quality.

## Business glossary

The business glossary is the authoritative place for **organizational** definitions of metrics, dimensions, policies, and concepts. It is not generic industry text—it reflects how *your* company defines and uses terms.

### Term structure

Terms typically include name and definition, domain / category hierarchy, status, governance roles, classifications and quality signals, and relationships to other terms and to physical data objects.

### Relationship vocabulary

OvalEdge supports a rich set of relationship types (20+), including synonym, contains, calculates, calculates-from, filtered-by, is-a-type-of, defines, contrasts-with, qualifies, and **custom types** defined by your organization.

### Linking terms to physical assets

Terms can be associated with tables, columns, reports, and other catalog objects. That linkage powers discovery (“which column implements Customer Lifetime Value?”) and inheritance of classifications and protection rules where glossary–catalog sync is enabled.

### Lookup

Use **`asset_explorer`** with `name` and `object_type=glossary` (optional domain / category placement). Resource: `ovaledge://governance/glossary-term/{object_id}`.

### Create: `create_glossary_term`

1. `term_name` → user picks **domain** (or pass `domain_name` when the user names a domain)
2. `term_name` + `domain_id` → category picker when categories exist (pick or skip with `skip_category=true` and `category_skip_confirmed=true`)
3. If a category was chosen and subcategories exist → subcategory pick or skip (`skip_subcategory=true` and `subcategory_skip_confirmed=true`)
4. **Description is required** — never invent a description
5. When placement and description are complete → **`confirm_create`** preview; show `formattedResponse` and wait for approval
6. **POST** only after user confirms: re-call with **`write_confirmed_by_user=true`**, **`confirmation_token`** from the preview, and the same placement fields

Workflow prompt: **`create_business_glossary_term`**. See [mcp_workflows](mcp_workflows).

## Tags (OETAG)

Tags classify and govern catalog assets. Lookup with **`asset_explorer`**: `name` + `object_type=oetag` (optional `include_parent` / `include_children`). Resource: `ovaledge://governance/tag/{object_id}`.

### Create: `create_tag`

Backend: create-options, parent-options, `POST /api/v1/mcp/tags`. Flow depends on **`tagSecurityMode`** from create-options:

#### OPEN mode

1. `tag_name` only → show **parent** options (`userSelectableParents`); **no POST**
2. User chooses parent or no parent → call again with `parent_step_completed_by_user=true` plus either `parent_tag_id` + `parent_tag_id_confirmed_by_user=true`, or `create_directly_under_master=true`
3. **Confirm** → same placement + `write_confirmed_by_user=true` → POST

#### SECURE mode

1. `tag_name` only → user must pick **master** (`master_tag_id` + `master_tag_id_confirmed_by_user=true`)
2. Show **parent** options under that master (optional). Rows with `hasChildren=true` support nested browse via `browse_parent_tag_id`
3. Finalize with `parent_step_completed_by_user=true` and parent choice or `create_directly_under_master=true`
4. **Confirm** → `write_confirmed_by_user=true` → POST

Never invent `master_tag_id` or `parent_tag_id`. Never set confirmation flags on the same call as `tag_name` only. Optional `description`; if omitted on POST, MCP may auto-generate wiki HTML (`OVALEDGE_TAG_AUTO_DESCRIPTION`).

Workflow prompts: **`create_governance_tag`**, **`explain_tag`**.

## Data stories (organizational knowledge)

**Data stories** (`oestory`) are narrative governance content: policies, playbooks, domain context, and other **organization-specific** knowledge (often in **story zones**).

They are **not** glossary terms (`asset_explorer` + `object_type=glossary`) or physical tables/files (`asset_explorer` / `asset_details`).

### MCP tool: `knowledge_search`

Backend: `GET /api/v1/mcp/knowledge-search` (data-story and product-documentation corpora + RBAC). Prefer `query`; optional story filters (`story_zone_name`, `story_name`, `object_id`). Present `formattedResponse`; lead story answers with `storyCitation` verbatim.

Resource: `ovaledge://governance/data-story/{object_id}` — prefer `knowledge_search` for narrative. Workflow prompt: **`organizational_knowledge`**.

## Native source access (RDAM) summary

**`access_explorer`** with **`operation=source_system_access`** returns **native** Redshift, Snowflake, or Tableau grants from **RDAM SQL metadata** — not catalog permissions and not `asset_explorer`. Do not fall back to catalog when RDAM is empty or errors. Prompt: **`native_source_access`**. Deep routing: [rdam_source_access](rdam_source_access); index: [mcp_workflows](mcp_workflows#native-source-access-rdam).

### Data Access Admin (DAA)

**Data Access Admin (DAA)** — enforced server-side on `access_explorer` source_system_access (same as DAM UI):

- **Instance Data Access Admin:** RDAM instance roles; access to connectors on that instance.
- **Connector Data Access Admin:** roles on one connection only.

The API returns RDAM no-access if the caller lacks Connector DAA on the connection (or Instance DAA on its parent instance). No separate DAA check endpoint is required.

**DAM object scope:** grant rows are limited to databases/schemas/tables/columns visible in DAM (active catalog objects with RDAM crawl — same as OETP RDAM browse). Harvested privileges for objects not in DAM (e.g. uncrawled schemas) are excluded.
