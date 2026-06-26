# OvalEdge overview

OvalEdge is a data governance platform that helps organizations find, understand, trust, and use data consistently. It connects technical metadata (schemas, columns, pipelines) with business meaning (terms, ownership, policies) so teams share one source of truth.

## Core capabilities

- **Data catalog** — Searchable inventory of tables, files, reports, APIs, and code with profiling, popularity, and usage context.
- **Business glossary** — Definitions, domains, and rich relationships between business concepts and physical data.
- **Lineage** — Upstream and downstream impact analysis, combining automated SQL-based lineage with curated manual links.
- **Governance** — Ownership, stewardship, certification, classifications, and access context aligned to your operating model.
- **Data quality** — Rules, scores, and monitoring signals that feed trust and prioritization in the catalog.

## Key concepts

| Concept | Meaning |
|--------|---------|
| **Asset** | Any governed object (e.g. table, column, report, API) with metadata and governance attributes. |
| **Steward / owner** | People accountable for definition, quality, and appropriate use of data. |
| **Policy** | Organizational rules (e.g. retention, masking) applied in OvalEdge and reflected in metadata. |
| **Domain** | Business grouping for glossary and catalog organization (e.g. Finance, Marketing). |
| **Certification** | Lifecycle state (e.g. certified, cautioned) signaling trust and review status. |
| **CDE** | Critical Data Element — high-impact fields or objects under enhanced governance. |
| **Curation score** | Measure of metadata completeness and governance hygiene for an asset or term. |
| **DQ score** | Data quality score derived from rules and assessments. |

## MCP agents

This repository ships an MCP server (see `server/app.py` **instructions**) for catalog discovery, lineage, glossary, tags, **data stories**, platform docs, metadata drift, native access previews, and governed writes. Routing summary:

| Intent | Tool / prompt |
|--------|----------------|
| Organizational policy, playbook, onboarding narrative | **`lookup_datastory`** (`content_query`); prompt **`organizational_knowledge`** |
| OvalEdge product UI / features / configuration | **`search_platform_docs`**; prompt **`platform_help`** |
| Tables, files, columns, reports | **`search_catalog_assets`** → **`catalog_asset_details`** |
| Native Redshift / Snowflake / Tableau grants | **`source_system_access`** (not catalog ACLs) |
| Create glossary term or tag | **`create_glossary_term`** / **`create_tag`** with picker flow; POST only after **`write_confirmed_by_user=true`** |

Present **`formattedResponse`** and **`storyCitation`** from data-story tools verbatim when provided. Do not invent glossary **descriptions**. Workflow prompts and resource URIs: [mcp_workflows](mcp_workflows). Static guides: `docs://ovaledge/{name}`.

## Bridge Client

For on-premises or restricted networks, the **Bridge Client** connects OvalEdge Cloud to sources inside your perimeter so crawling, profiling, and lineage run where the data lives—without moving raw data to the cloud unnecessarily. Use it when direct cloud-to-source connectivity is not allowed.
