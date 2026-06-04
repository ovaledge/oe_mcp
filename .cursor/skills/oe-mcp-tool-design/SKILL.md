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

1. **One OvalEdge endpoint → one MCP tool** — no alias tools (`user_object_access` + `source_system_access` on the same GET). Use parameters (`query_direction`, modes) instead of duplicate registrations.
2. **Tool name = snake_case function name** — add `TOOL_*` constant in `server/constants.py`; prompts and evals import the constant, never hard-code strings.
3. **Descriptions live in `helpers.py`** as `_DESC_<NAME>` — include purpose, when **not** to use sibling tools, `Backend: GET|POST {MCP_PATH_*}`, examples, and RBAC/DAA notes if applicable.
4. **Thin `register.py`** — `@mcp.tool(description=_DESC_…)` + `Annotated`/`Field` params; delegate to `_invoke_*` or helper builders; use `server.tools.common` (`drop_none`, `map_ovaledge_error`, `ovaledge_client`, validators).
5. **Client validation before HTTP** — return `error_payload(...)` from helpers when args are invalid; do not rely on the API for MCP-side mutual-exclusion rules.

## Choose a domain package

| Package | Use for |
|---------|---------|
| `server/tools/catalog/` | Catalog search, details, lineage, profiles, metadata drift, asset descriptions |
| `server/tools/governance/` | Glossary, tags, data stories, DQ, governance roles (incl. guided creates) |
| `server/tools/docs/` | OvalEdge **product** documentation search only |
| `server/tools/rdam/` | Native Redshift/Snowflake/Tableau grants (RDAM harvest) |
| New domain | Only if none fit — add `server/tools/<domain>/`, export in `server/tools/__init__.py`, call `register` from `server/mcp/bootstrap.py` |

Shared logic: `server/tools/common/` (never duplicate `error_payload` or client wiring).

## Implementation checklist

Copy and complete: [checklist.md](checklist.md)

### Minimal file touch list

| Step | File(s) |
|------|---------|
| Constants | `server/constants.py` — `TOOL_*`, `MCP_PATH_*`, allow-lists (`MCP_*_DOC` for descriptions) |
| Helpers | `server/tools/<domain>/helpers.py` — `_DESC_*`, param builders, `validate_*` |
| Register | `server/tools/<domain>/register.py` — `def register(mcp: FastMCP)` |
| Surface | `server/mcp_surface.py` — add to `MCP_TOOL_NAMES` |
| Tests | `tests/tools/test_<tool>.py` — param forwarding, validation, description assertions |
| Docs | `server/docs/mcp_workflows.md` routing table; domain doc if needed |
| Prompt | `server/prompts/workflows/register.py` + `tests/prompts/test_workflows.py` `_PROMPT_REQUIRED_TOOLS` only when a workflow applies |
| Evals | `evals/golden_cases.py` only for high-value agent paths |

Run: `poetry run ruff check .` and `poetry run pytest tests/tools/test_<tool>.py tests/client/test_mcp_surface_inventory.py -q`

## `register.py` pattern

```python
async def _invoke_my_tool(arg: str, ...) -> dict[str, Any]:
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
    @mcp.tool(description=_DESC_MY_TOOL)
    async def my_tool_name(
        arg: Annotated[str, Field(description="...")],
        optional: Annotated[str | None, Field(description="...", default=None)] = None,
    ) -> dict[str, Any]:
        """One-line pointer to MCP tool description."""
        return await _invoke_my_tool(arg, optional)
```

- Wire names: Python `snake_case` → API `camelCase` in `drop_none(...)`.
- Use `Literal[...]` + shared `MCP_*_DOC` strings for enums.
- Docstring on the function stays short; **agent routing uses `description=_DESC_*`**.

## Description template (`_DESC_*`)

```markdown
<One sentence purpose and primary user questions>

Backend: GET /api/v1/mcp/<path>

**Not** <other_tool> — <when to use the other tool instead>.

**<param>** (required|optional): <rules, examples>.

Read-only. Returns validation errors for ...; <RBAC/DAA if enforced server-side>.
```

For **governed writes** (`create_*`, `update_*`): document `confirm_create` / `confirm_update`, `create_confirmed_by_user=true`, and `dry_run` in `_DESC_*` (see `create_glossary_term`, `create_tag`).

## Tests (required)

In `tests/tools/test_<feature>.py`:

1. Register domain on `FastMCP(name="test", version="0.0.1")`, `fn = await get_tool_fn(mcp, TOOL_CONSTANT)`.
2. Mock `mock_oe_client.get` / `.post`; assert exact path + `params`/`json`.
3. Assert validation returns `error` key without calling client.
4. Optionally assert critical phrases in `_DESC_*` (DAA, routing boundaries).

`tests/client/test_mcp_surface_inventory.py` must pass after updating `MCP_TOOL_NAMES`.

## Anti-patterns

| Avoid | Do instead |
|-------|------------|
| Second tool wrapping same `MCP_PATH_*` | Extend params on one tool |
| Long logic in `register.py` | `helpers.py` / `formatters.py` (catalog) |
| Hard-coded tool names in prompts | `from server.constants import TOOL_*` |
| Platform docs for org stories | `lookup_datastory` vs `search_platform_docs` |
| Catalog search for native DB grants | `source_system_access` |
| Skipping `mcp_workflows.md` | Add one routing table row + section if non-obvious |

## Reference

- Full checklist: [checklist.md](checklist.md)
- Example read-only tool: `server/tools/rdam/`
- Example simple GET: `server/tools/docs/`
- Example complex writes: `server/tools/governance/`
- Agent routing index: `server/docs/mcp_workflows.md`
