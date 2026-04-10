# Asset types in OvalEdge

Use these values when filtering catalog search or specifying `object_type` on detail APIs.

## Supported object types

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

- **Broad discovery** — Start with `TABLE`, `VIEW`, `REPORT`, or `FILE` depending on the question.
- **Column-level detail** — Use `COLUMN`, `FILE_COLUMN`, or `REPORT_COLUMN` when the user asks about fields, PII, or masking.
- **Integration context** — Use `API` / `API_ATTRIBUTE` for service-oriented assets; `CODE` for transformation logic when available.

Always pair `object_id` with the correct `object_type` when calling asset detail APIs so OvalEdge resolves the right entity.
