---
name: oe-mcp-tool-design
description: >-
  Designs and implements OvalEdge MCP tools in oe_mcp following FastMCP domain
  modules, constants, helpers, registration, tests, and doc alignment. Use when
  adding a new MCP tool, extending server/tools, reviewing tool contracts, or
  avoiding duplicate tools that call the same OvalEdge API.
---

# OvalEdge MCP tool design (oe_mcp)

## Core rules

1. **One OvalEdge endpoint → one MCP tool** — no alias tools on the same HTTP path/method. Use parameters (`query_direction`, modes) instead of duplicate registrations. Paired read/write on one path (e.g. GET + POST `glossary-terms`) is OK when intents differ.
2. **Tool name = snake_case function name** — add `TOOL_*` constant in `server/constants.py`; prompts and evals import the constant, never hard-code strings. See **Naming** below.
3. **Descriptions live in helpers** as `_DESC_<NAME>` — compact routing only (see **Context budget**). Put playbooks, allow-lists, and field matrices in `server/docs/` + workflow prompts.
4. **Thin `register.py`** — `@mcp.tool(title=…, description=_DESC_…, annotations=…)` + short `Field` params; delegate to `_invoke_*` or helper builders; use `server.tools.common` (`drop_none`, `map_ovaledge_error`, `ovaledge_client`, validators).
5. **Client validation before HTTP** — return `error_payload(...)` from helpers when args are invalid; do not rely on the API for MCP-side mutual-exclusion rules.
6. **Every tool declares `title` and `annotations`** — the human-readable name and the machine-readable side-effect contract. Both are enforced in `tests/client/test_mcp_surface_inventory.py`.

## Naming and title

| Layer | Convention | Examples |
|-------|-----------|----------|
| `name` (agent routing) | Consolidated **reads** use the `<domain>_<facet>` family so siblings sort together and the boundary is obvious. **Actions** stay verb-led. | `asset_explorer`, `asset_details`, `asset_lineage`, `knowledge_search`; `create_glossary_term`, `update_asset_descriptions`, `assess_cde_dq` |
| `title` (what a business user sees in the client) | Always **verb-led, plain English**, no jargon and no snake_case. Unique across the surface. | "Find data assets", "View asset details", "Trace data lineage", "Search knowledge & docs" |

Reference the `title` in `_DESC_*` and in `mcp_workflows.md` (e.g. ``asset_explorer`` (**Find data assets**)) so the agent and the user share vocabulary.

## Side-effect annotations

`server/tools/common/annotations.py` holds the four allowed profiles. Pick one — do not hand-roll a dict:

| Profile | Use for | `readOnlyHint` / `destructiveHint` |
|---------|---------|-----------------------------------|
| `READ_ONLY` | Lookups that never mutate OvalEdge state | `True` / `False` |
| `GOVERNED_CREATE` | Confirm-gated writes that add objects | `False` / `False` |
| `GOVERNED_UPDATE` | Confirm-gated writes that overwrite existing values | `False` / `True` |
| `GOVERNED_EXECUTE` | Confirm-gated, non-mutating (e.g. runs SQL on a connection) | `False` / `False` |

**Invariant (tested):** a tool exposing `write_confirmed_by_user` must **not** be `READ_ONLY`, and a tool without the gate must be. Clients auto-approve read-only tools — an over-claimed hint bypasses human review on a governed write.

## Context budget (always-on agent context)

MCP clients load **all** tool descriptions on every session. Keep them small.

| Tier | Where | What belongs |
|------|--------|----------------|
| 1 | `server/app.py` instructions | Global routes only (~15 lines); no tool playbooks |
| 2 | `_DESC_*` on `@mcp.tool` | Purpose, `Backend:`, **Not** sibling tools, required params summary, confirm gate one-liner |
| 3 | `docs://ovaledge/*`, workflow prompts | Extended routing, examples, allow-lists, OPEN/SECURE wizards, DAA/agent rules |

**Budget (enforced in tests):** each `_DESC_*` ≤ **2,500** chars; all descriptions combined ≤ **32,000** chars (`tests/tools/test_tool_description_budget.py`).

- `_DESC_*`: link to `docs://ovaledge/mcp_workflows` and/or domain guides (`governance`, `asset_types`).
- `Field(description=...)`: **one line** per parameter; no repeated playbook text.
- `MCP_*_DOC` constants: reuse in **docs and prompts**; avoid concatenating large blocks into `_DESC_*`.
- Heavy **responses**: apply `slim_tool_response()` from `server/mcp_response_slim.py` on large catalog/glossary reads (separate from description budget).

## Choose a domain package

| Package | Use for |
|---------|---------|
| `server/tools/catalog/` | Catalog search, details, lineage, profiles, metadata drift, asset descriptions, CDE associations |
| `server/tools/access/` | Unified access (`access_explorer`: catalog permissions + RDAM) |
| `server/tools/governance/` | Glossary, tags, data stories, governance roles, custom fields (incl. guided creates) |
| `server/tools/dataquality/` | DQ rule lookup, CDE assess, associate, create |
| `server/tools/docs/` | OvalEdge **product** documentation search only |
| `server/tools/rdam/` | Native Redshift/Snowflake/Tableau grants (RDAM harvest) |
| New domain | Only if none fit — add `server/tools/<domain>/`, export in `server/tools/__init__.py`, call `register` from `server/mcp/bootstrap.py` |

Shared logic: `server/tools/common/` (never duplicate `error_payload` or client wiring).

**Governance helpers:** split modules (`glossary_helpers.py`, `tag_helpers.py`, …) with `governance/helpers.py` as re-export hub.

**Data classification:** append via `classify_tool_desc()` from `server/tools/common/descriptions.py` (INTERNAL default; CONFIDENTIAL for access/RDAM tools).

**Invocation modules:** `catalog/invocations.py`, `governance/invocations.py`, `access/invocations.py`, and `rdam/invocations.py` hold `_invoke_*` logic; `register.py` keeps decorators and Pydantic `Field` signatures only.

## Implementation checklist

Copy and complete: [checklist.md](checklist.md)

### Minimal file touch list

| Step | File(s) |
|------|---------|
| Constants | `server/constants.py` — `TOOL_*`, `MCP_PATH_*`, allow-lists (`MCP_*_DOC` for docs/prompts/Field) |
| Helpers | `server/tools/<domain>/helpers.py` (or split `*_helpers.py`) — `_DESC_*` via `classify_tool_desc()`, param builders, `validate_*` |
| Register | `server/tools/<domain>/register.py` — `def register(mcp: FastMCP)` |
| Surface | `server/mcp_surface.py` — add to `MCP_TOOL_NAMES` |
| Tests | `tests/tools/test_<tool>.py` — param forwarding, validation, routing/description assertions |
| Budget | `tests/tools/test_tool_description_budget.py` — must stay green |
| Docs | `server/docs/mcp_workflows.md` routing table + section for non-obvious workflows |
| Prompt | `server/prompts/workflows/register.py` + `tests/prompts/test_workflows.py` `_PROMPT_REQUIRED_TOOLS` when a playbook applies |
| Evals | `evals/golden_cases.py` only for high-value agent paths |

Run:

```bash
poetry run ruff check .
poetry run pytest tests/tools/test_<tool>.py tests/tools/test_tool_description_budget.py tests/client/test_mcp_surface_inventory.py -q
```

## `register.py` pattern

```python
async def _invoke_my_tool(arg: str, ...) -> dict[str, Any]:
    """One line: METHOD path — what it returns."""
    err = validate_my_tool_args(...)
    if err is not None:
        return err
    params = drop_none(apiCamelCase=strip_or_none(arg), ...)
    try:
        async with ovaledge_client() as client:
            return await client.get(MCP_PATH_MY_TOOL, params=params)  # or .post
    except OvalEdgeError as e:
        return map_ovaledge_error(e)

def register(mcp: FastMCP) -> None:
    @mcp.tool(title="Do the thing", description=_DESC_MY_TOOL, annotations=READ_ONLY)
    async def my_tool_name(
        arg: Annotated[str, Field(description="Short param hint.")],
        optional: Annotated[str | None, Field(description="Optional.", default=None)] = None,
    ) -> dict[str, Any]:
        """One-line pointer to MCP tool description."""
        return await _invoke_my_tool(arg, optional)
```

- Wire names: Python `snake_case` → API `camelCase` in `drop_none(...)`.
- Use `Literal[...]` for enums; point to docs for long allow-lists.
- Docstring on the function stays short; **agent routing uses `description=_DESC_*`**.

## Description template (`_DESC_*`)

```markdown
<One sentence purpose>

Backend: GET|POST {MCP_PATH_*}

**Not** <sibling_tool> — <when to use sibling instead>.

<Required params summary — direction-dependent rules in one short block>

Extended routing / examples: docs://ovaledge/mcp_workflows (<section>) [and workflow prompt `...` if applicable].

Read-only. <RBAC/DAA one-liner if server-enforced>.

<Data classification appended by classify_tool_desc() — do not duplicate manually.>
```

**Governed writes** (`create_*`, `update_*`): state confirm gate in `_DESC_*` (one paragraph); full wizard steps in `governance` or `mcp_workflows` — not inlined.

## Tests (required)

In `tests/tools/test_<feature>.py`:

1. Register domain on `FastMCP(name="test", version="0.0.1")`, `fn = await get_tool_fn(mcp, TOOL_CONSTANT)`.
2. Mock `mock_oe_client.get` / `.post`; assert exact path + `params`/`json`.
3. Assert validation returns `error` key without calling client.
4. Assert routing essentials in `_DESC_*`; assert deep rules in `server/constants.py` docs or `server/docs/*.md` when de-bloated.

`tests/client/test_mcp_surface_inventory.py` and `tests/tools/test_tool_description_budget.py` must pass after surface changes.

## Anti-patterns

| Avoid | Do instead |
|-------|------------|
| Second tool wrapping same `MCP_PATH_*` | Extend params on one tool |
| Long playbooks in `_DESC_*` or `Field(description=...)` | `mcp_workflows.md` + domain guides + workflow prompts |
| Concatenating many `MCP_*_DOC` blocks into tool description | Constants in tier 3 only |
| Long logic in `register.py` | `helpers.py` / `formatters.py` / `invocations.py` |
| Hard-coded tool names in prompts | `from server.constants import TOOL_*` |
| Knowledge questions | `knowledge_search` searches both data stories and product docs |
| Catalog search for native DB grants | `access_explorer` operation=source_system_access |
| Catalog permissions for native grants | `access_explorer` catalog_access vs source_system_access |
| Skipping `mcp_workflows.md` | Routing table row + section when non-obvious |

## Enterprise architecture alignment

This repo implements **Level 2** MCP contract governance (domain-scoped tool design). Align with EA AI platform standards as follows:

| EA expectation | oe_mcp practice |
|----------------|-----------------|
| Complete tool contract (purpose, inputs, outputs, side effects) | `title` + `_DESC_*` + Pydantic `Field` + MCP `annotations` + `mcp_workflows` / domain docs |
| Human-in-the-loop for writes | `confirm_create` / `confirm_update` + `write_confirmed_by_user=true`, with `readOnlyHint=False` so clients cannot auto-approve |
| Context window budgeting | Description budget tests + `mcp_response_slim` on responses |
| AuthZ on every data call | OvalEdge RBAC/DAA enforced server-side; document in `_DESC_*` |
| Stable error contracts | `{"error", "status_code"}` via `error_payload` / `map_ovaledge_error`; optional `error_code` on validation errors |
| Eval before agent paths ship | `evals/golden_cases.py` for high-value flows |

**Not in scope of this skill:** LangGraph orchestration, Bedrock model selection, per-tool rate limits (delegated to OvalEdge API throttling).

## Reference

- Full checklist: [checklist.md](checklist.md)
- Thin read + `_invoke_*`: `server/tools/access/`, `server/tools/docs/`
- RDAM read + validation: `server/tools/rdam/`
- Governed writes (split helpers + invocations): `server/tools/governance/`
- Catalog tools: `server/tools/catalog/` (`invocations.py` + thin `register.py`)
- DQ tools: `server/tools/dataquality/`
- Agent routing index: `server/docs/mcp_workflows.md`
- Description budget: `tests/tools/test_tool_description_budget.py`
