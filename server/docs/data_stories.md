# Data stories (organizational knowledge)

**Data stories** (`oestory`) are narrative governance content in OvalEdge: policies, playbooks, domain context, onboarding material, and other **organization-specific** knowledge your teams published as stories (often grouped in **story zones**).

They are **not**:

- **Business glossary terms** — use `asset_explorer` with `name` and `object_type=glossary`  
- **Physical tables/files** — use `asset_explorer` / `asset_details`  

## MCP tool: `knowledge_search`

Backend: `GET /api/v1/mcp/knowledge-search` (data-story and product-documentation corpora + RBAC).

| Mode | Parameters | When to use |
|------|------------|-------------|
| Search | Question text | Open-ended questions (“What is our PII retention policy?”) or an OvalEdge product question |

**Response:** `formattedResponse`, `storyCitation` (use as the **first line** of the answer — verbatim, no “Based on…” prefix), sections, `navUrl`, metadata, access control.

`knowledge_search` searches both corpora; it has no corpus enum. Use returned citations and context to identify organization stories versus product documentation.

## MCP resource

`ovaledge://governance/data-story/{object_id}` — catalog JSON via asset-details. Prefer `knowledge_search` when you need formatted narrative and citations.

## Workflow prompt

Use the **`organizational_knowledge`** prompt for a fixed sequence: `knowledge_search` → optional `oestory` asset search → present citations.

## Example agent flow

1. User: “How does Finance document revenue recognition?”  
2. `knowledge_search(query="How does Finance document revenue recognition?")`  
3. Present `formattedResponse`; lead with `storyCitation`  
4. If no story is returned, refine the `knowledge_search` query or use `asset_explorer(search_terms=[...], object_type="oestory")` to locate related metadata

Server instructions in `server/app.py` reinforce this routing for all MCP clients.
