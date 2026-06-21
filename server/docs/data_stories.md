# Data stories (organizational knowledge)

**Data stories** (`oestory`) are narrative governance content in OvalEdge: policies, playbooks, domain context, onboarding material, and other **organization-specific** knowledge your teams published as stories (often grouped in **story zones**).

They are **not**:

- **Business glossary terms** — use `lookup_glossary_term` for formal definitions  
- **Platform documentation** — use `search_platform_docs` for how OvalEdge works  
- **Physical tables/files** — use `search_catalog_assets` / `catalog_asset_details`  

## MCP tool: `lookup_datastory`

Backend: `GET /api/v1/mcp/lookup-datastory` (Elasticsearch `oestory` + RBAC).

| Mode | Parameters | When to use |
|------|------------|-------------|
| Content search | `content_query` (+ optional `story_zone_name`, `story_name`) | Open-ended questions (“What is our PII retention policy?”) |
| Title lookup | `story_name` (+ optional `story_zone_name`) | User names a story |
| By id | `object_id` | You already have the story id from search or a resource |

**Response:** `formattedResponse`, `storyCitation` (use as the **first line** of the answer — verbatim, no “Based on…” prefix), sections, `navUrl`, metadata, access control.

If `search_catalog_assets` returns `oestory` hits, call `lookup_datastory` for full narrative — do not answer from search snippets alone.

## MCP resource

`ovaledge://governance/data-story/{object_id}` — catalog JSON via object-details. Prefer `lookup_datastory` when you need formatted narrative and citations.

## Workflow prompt

Use the **`organizational_knowledge`** prompt for a fixed sequence: `lookup_datastory` first → optional `oestory` catalog search → present citations.

## Example agent flow

1. User: “How does Finance document revenue recognition?”  
2. `lookup_datastory(content_query="How does Finance document revenue recognition?")`  
3. Present `formattedResponse`; lead with `storyCitation`  
4. If 404, `search_catalog_assets(search_terms=[...], object_type="oestory")` then retry with `object_id` or refined `content_query`

Server instructions in `server/app.py` reinforce this routing for all MCP clients.
