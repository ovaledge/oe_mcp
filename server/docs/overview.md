# OvalEdge overview

OvalEdge is a data governance platform that helps organizations find, understand, trust, and use data consistently. It connects technical metadata (schemas, columns, pipelines) with business meaning (terms, ownership, policies) so teams share one source of truth.

## Core capabilities

- **Data catalog** — Searchable inventory of tables, files, reports, APIs, and code with profiling, popularity, and usage context.
- **Business glossary** — Definitions, domains, and relationships between business concepts and physical data.
- **Lineage** — Upstream and downstream impact analysis.
- **Governance** — Ownership, stewardship, certification, classifications, tags, and access context.
- **Data quality** — Rules, scores, and monitoring signals that feed trust in the catalog.
- **Knowledge** — Data stories (org narratives) and product documentation searchable via MCP.

## Key concepts

| Concept | Meaning |
|--------|---------|
| **Asset** | Any governed object (table, column, report, API, …) with metadata and governance attributes. |
| **Steward / owner** | People accountable for definition, quality, and appropriate use. |
| **Domain** | Business grouping for glossary and catalog organization. |
| **Certification** | Lifecycle state signaling trust and review status. |
| **CDE** | Critical Data Element — high-impact fields under enhanced governance. |
| **Curation / DQ score** | Metadata hygiene vs measured data quality. |

## MCP read tools (consolidated)

| Tool | Role |
|------|------|
| **`asset_explorer`** | Find data assets across types; omit `object_type` unless the query implies one. Then shortlist. |
| **`asset_details`** | View full metadata for one shortlisted `object_id` + `object_type`. |
| **`asset_lineage`** | Trace lineage for a table or file. |
| **`knowledge_search`** | Search org stories and OvalEdge product docs. |

Present **`formattedResponse`** (and **`storyCitation`** for stories) when provided. Do not invent glossary descriptions. Filing an access, content-change, or DQ-recommendation **ticket** is **`create_service_request`**, not `access_explorer`. Full routing: [mcp_workflows](mcp_workflows). Governance / glossary / tags / stories: [governance](governance). Types: [asset_types](asset_types).

## Bridge Client

For on-premises or restricted networks, the **Bridge Client** connects OvalEdge Cloud to sources inside your perimeter so crawling, profiling, and lineage run where the data lives—without moving raw data to the cloud unnecessarily.
