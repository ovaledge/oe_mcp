# Governance model

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

Write tools (e.g. `create_tag`, `create_glossary_term`, `update_asset_descriptions`, `update_governance_roles`) invoke the same OvalEdge APIs as the UI; they succeed only when the authenticated user has the required governance privileges.

The MCP adds **human-in-the-loop** steps for governed writes: picker responses (`formattedResponse`) on creates, explicit confirmation flags, a **`confirmationToken`** that binds the confirmed POST to the previewed payload, and a final **`write_confirmed_by_user`** gate before POST (creates and updates). Agents must not skip pickers or auto-confirm on behalf of users.

## Critical Data Element (CDE)

Catalog assets (schemas, tables, columns, files, reports, APIs, codes) support a **Critical Data Element** designation. Use the `update_cde_associations` MCP tool to set `Yes`, `No`, or `None`, with optional category and justification — matching the catalog UI shutter. Resolve assets via `asset_explorer` first; updates require meta-write permission and are audited in asset history.

## Data stories

**Data stories** (`oestory`) hold narrative organizational knowledge (policies, playbooks, domain context). They are governed and RBAC-scoped like other assets. Use `knowledge_search` for search and display; see [data_stories](data_stories).

## Tags

**Tags** (`oetag`) classify assets. Search via `asset_explorer` (`name` + `object_type=oetag`); creation follows secure or open master/parent flows via `create_tag`. See [tags_guide](tags_guide).

## Native source access (RDAM)

**`source_system_access`** returns **native** Redshift, Snowflake, or Tableau grants from **RDAM SQL metadata** — not catalog ACLs, not Elasticsearch, and not `asset_explorer`. Do not fall back to catalog when RDAM is empty or errors. Use the **`native_source_access`** workflow prompt for grant questions. See [mcp_workflows](mcp_workflows#native-source-access-rdam) for `query_direction`, `object_path`, `object_type`, and examples. Deep routing rules: [rdam_source_access](rdam_source_access).

### Data Access Admin (DAA)

**Data Access Admin (DAA)** — enforced server-side on `source_system_access` (same as DAM UI):

- **Instance Data Access Admin:** RDAM instance roles; access to connectors on that instance.
- **Connector Data Access Admin:** roles on one connection only.

The API returns RDAM no-access if the caller lacks Connector DAA on the connection (or Instance DAA on its parent instance). No separate DAA check endpoint is required.

**DAM object scope:** grant rows are limited to databases/schemas/tables/columns visible in DAM (active catalog objects with RDAM crawl — same as OETP RDAM browse). Harvested privileges for objects not in DAM (e.g. uncrawled schemas) are excluded.

## Glossary–catalog sync and inheritance

Terms in the business glossary can be linked to physical columns and tables. When sync is enabled, governance properties (e.g. classifications, masking, restriction flags) may **inherit** from the term to the asset. Responses may indicate whether masking or restriction came from term sync versus direct assignment on the asset.

## Curation score

Curation reflects how complete and trustworthy metadata is—examples of components include descriptions, ownership, glossary linkage, classifications, and quality signals. It complements DQ score: curation is about metadata health; DQ is about measured data quality.
