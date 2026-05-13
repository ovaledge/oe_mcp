# Asset types in OvalEdge

Use these values when filtering catalog search or specifying `object_type` on detail APIs.

## MCP catalog `objectType` (lowercase)

`search_catalog_assets` and `catalog_asset_details` (id + type mode) accept the following **lowercase** API values. The canonical set lives in `server.constants.MCP_CATALOG_OBJECT_TYPES`.

| Value | Typical use |
|-------|-------------|
| `oeschema` | Schema containers in the catalog |
| `oetable` | Relational tables |
| `oecolumn` | Table columns |
| `oefile` | File-based datasets |
| `filecolumn` | Columns within structured files |
| `oechart` | Charts / dashboards |
| `chartchild` | Child elements under a chart |
| `oeapi` | API assets |
| `oeapicolumn` | Parameters or attributes on APIs |
| `oequery` | Saved queries / query objects |
| `dp_product` | Data product catalog entries |
| `glossary` | Business glossary terms |
| `oetag` | Tags |
| `oestory` | Data stories |

**Narrow tools:** `column_profile_statistics` and `asset_lineage` accept **`oetable`** and **`oefile`** only. `table_entity_relationships` is **table-only** (`object_id` for an `oetable`).

## UI / filter labels (uppercase)

Some OvalEdge surfaces use these uppercase type labels (not interchangeable with MCP `objectType` without mapping):

| Value | Typical use |
|-------|-------------|
| `TABLE` | Relational tables |
| `VIEW` | Database views |
| `COLUMN` | Column-level metadata |
| `SCHEMA` | Schema containers |
| `DATABASE` | Database / connection scope |
| `REPORT` | BI reports and dashboards |
| `FILE` | File-based datasets |
| `FILE_COLUMN` | Columns within structured files |
| `REPORT_COLUMN` | Columns or fields within reports |
| `API` | API endpoints or services |
| `API_ATTRIBUTE` | Attributes or parameters on APIs |
| `CODE` | Code objects (e.g. jobs, notebooks) when catalogued |

## Using types as filters

- **Broad discovery** — Start with `oetable`, `oefile`, `oechart`, or domain-specific types (`oeapi`, `oequery`, `dp_product`) depending on the question.
- **Column-level detail** — Use `oecolumn` or `filecolumn` when the user asks about fields, PII, or masking.
- **Integration context** — Use `oeapi` / `oeapicolumn` for service-oriented assets.
- **Governance** — Use `glossary` or `oetag` for business terms and tags; `oestory` for narrative data products.

Always pair `object_id` with the correct `object_type` when calling asset detail APIs so OvalEdge resolves the right entity.
