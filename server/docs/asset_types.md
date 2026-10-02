# Asset types in OvalEdge

Use these values when filtering catalog search or specifying `object_type` on detail APIs.

## MCP catalog `objectType` (lowercase)

`asset_explorer` and `asset_details` accept the following **lowercase** API values (`server.constants.MCP_CATALOG_OBJECT_TYPES`).

| Value | Typical use |
|-------|-------------|
| `oeschema` | Schema containers |
| `oetable` | Relational tables |
| `oecolumn` | Table columns |
| `oefile` | File-based datasets |
| `filecolumn` / `oefilecolumn` | Columns within structured files |
| `oechart` | Charts / dashboards |
| `chartchild` | Child elements under a chart |
| `oeapi` | API assets |
| `oeapicolumn` | Parameters or attributes on APIs |
| `oequery` / `oecode` / `code` | Saved queries / code objects |
| `dp_product` / `dp_domain` | Data products / data domains |
| `oedomain` | Report groups |
| `glossary` | Business glossary terms |
| `oetag` / `mastertag` | Tags / master tags |
| `oestory` / `storyzone` | Data stories / story zones |
| `oeglobaldomain` | Glossary global domains |

`asset_details` auto-includes profile for **`oetable`** / **`oefile`**, and relationships for **`oetable`**. `asset_lineage` accepts **`oetable`** and **`oefile`** only.

## Using types as filters

- **Default discovery** — Omit `object_type` on `asset_explorer` so all types can match; set it only when the user/query implies a type (“tables”, “columns”, “glossary term”).
- **Column-level** — `oecolumn` / `filecolumn` for fields, PII, masking.
- **Governance entities** — `glossary` or `oetag` with `name` (or `object_id`) for term/tag lookup — not a substitute for open catalog search on “find related assets”.
- **Narratives** — Prefer `knowledge_search` for story content; `object_type=oestory` only for story metadata discovery.

## UI / filter labels (uppercase)

Some OvalEdge surfaces use uppercase labels (`TABLE`, `COLUMN`, `SCHEMA`, …). Map to MCP lowercase `objectType` before calling tools.

## MCP resources by type

| objectType | Resource URI |
|------------|----------------|
| `oetable` | `ovaledge://catalog/table/{object_id}` |
| `oefile` | `ovaledge://catalog/file/{object_id}` |
| `glossary` | `ovaledge://governance/glossary-term/{object_id}` |
| `oestory` | `ovaledge://governance/data-story/{object_id}` |
| `oetag` | `ovaledge://governance/tag/{object_id}` |

Always pair `object_id` with the correct `object_type`.
