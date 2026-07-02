# Tags (OETAG) via MCP

Tags classify and govern catalog assets. The MCP exposes **lookup** and **guided create** tools; both honor OvalEdge RBAC.

## Lookup: `lookup_tags`

Provide **either** `object_id` **or** `tag_name`, not both.

Use when the user asks what a tag means, its hierarchy, or stewardship metadata returned by the API.

## Resource

`ovaledge://governance/tag/{object_id}` — catalog document (`objectType=oetag`). Prefer `lookup_tags` for hierarchy and enriched display fields.

## Create: `create_tag`

Backend: create-options, parent-options, `POST /api/v1/mcp/tags`.

Flow depends on **`tagSecurityMode`** from create-options:

### OPEN mode

1. `tag_name` only → show **parent** options (`userSelectableParents`); **no POST**  
2. User chooses parent or no parent → call again with `parent_step_completed_by_user=true` plus either:  
   - `parent_tag_id` + `parent_tag_id_confirmed_by_user=true`, or  
   - `create_directly_under_master=true` (no parent; open root tag)  
3. **Confirm** → call with same placement + `write_confirmed_by_user=true` → POST  

### SECURE mode

1. `tag_name` only → user must pick **master** (`master_tag_id` + `master_tag_id_confirmed_by_user=true`)  
2. Show **parent** options under that master (optional). Rows with `hasChildren=true` support nested browse via `browse_parent_tag_id` on the next `create_tag` call (`GET parent-options?browseParentTagId=…`).  
3. Finalize with `parent_step_completed_by_user=true` and parent choice or `create_directly_under_master=true`  
4. **Confirm** → `write_confirmed_by_user=true` → POST  

Never invent `master_tag_id` or `parent_tag_id`. Never set confirmation flags on the same call as `tag_name` only.

Optional `description`; if omitted on POST, MCP may auto-generate wiki HTML from tag and hierarchy names (`OVALEDGE_TAG_AUTO_DESCRIPTION`).

## Workflow prompt

Use **`create_governance_tag`** for the full human-in-the-loop sequence including the confirm step.

## Workflow prompt (read)

Use **`explain_tag`** to resolve a tag by name and optionally find tagged assets via catalog search.
