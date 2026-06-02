# Business glossary guide

## What the glossary is

The business glossary is the authoritative place for **organizational** definitions of metrics, dimensions, policies, and concepts. It is not generic industry text—it reflects how *your* company defines and uses terms.

## Term structure

Terms typically include:

- Name and definition
- Domain / category hierarchy
- Status (e.g. published vs draft)
- Governance roles
- Classifications and quality or curation signals
- Relationships to other terms and to physical data objects

## Relationship vocabulary

OvalEdge supports a rich set of relationship types (20+), including among others:

synonym, contains, calculates, calculates-from, filtered-by, is-a-type-of, defines, contrasts-with, qualifies, and **custom types** defined by your organization.

Use relationship types to explain how metrics are derived, how concepts relate, and which data implements a term.

## Linking terms to physical assets

Terms can be associated with tables, columns, reports, and other catalog objects. That linkage powers:

- Discovery (“which column implements Customer Lifetime Value?”)
- Inheritance of classifications and protection rules where glossary–catalog sync is enabled

## Sync options

Organizations can configure how glossary properties propagate to catalog assets (e.g. classifications, masking). Exact options depend on OvalEdge configuration; the MCP exposes whatever the API returns for sync and inheritance.

## Common use cases

- Resolve ambiguous business language before querying data.
- Find all assets governed by a term or domain.
- Trace calculation chains across related terms (`calculates`, `calculates-from`).
- Onboard new analysts with domain-specific vocabulary tied to real datasets.

For agents creating terms via MCP, use **`create_glossary_term`** (or the **`create_business_glossary_term`** workflow prompt):

1. `term_name` → user picks **domain** (or pass `domain_name` on the first call when the user names a domain in natural language)
2. `term_name` + `domain_id` → category picker when categories exist (user picks or skips with `skip_category=true` and `category_skip_confirmed=true`)
3. If a category was chosen and subcategories exist → user picks **subcategory** or skips (`skip_subcategory=true` and `subcategory_skip_confirmed=true`)
4. **Description is required** — the tool refuses create without it; never invent a description
5. When placement and description are complete → call returns **`confirm_create`** preview; show `formattedResponse` and wait for user approval
6. **POST** only after user confirms: re-call with **`create_confirmed_by_user=true`** and the same `term_name`, `domain_id`, placement, and `description`

Resource for an existing term id: `ovaledge://governance/glossary-term/{object_id}`.

See [mcp_workflows](mcp_workflows) for the full prompt and tool matrix.
