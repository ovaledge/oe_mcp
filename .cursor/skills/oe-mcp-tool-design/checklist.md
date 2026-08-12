# New MCP tool checklist (oe_mcp)

## Design (before coding)

- [ ] Confirmed OvalEdge API path and method (GET vs POST) with backend team or OpenAPI
- [ ] No existing tool already calls this path (grep `MCP_PATH_` and path string)
- [ ] Tool `name` follows the surface convention: verb-led snake_case for actions (`create_*`, `update_*`, `assess_*`), `<domain>_<facet>` for consolidated reads (`asset_details`, `knowledge_search`)
- [ ] Human-readable `title` chosen — verb-led plain English, unique across the surface ("Find data assets")
- [ ] Documented **negative routing** (which existing tools must be used instead)
- [ ] Decided read-only vs governed write (confirm gate required?) and picked the matching `annotations` profile
- [ ] Decided what stays in `_DESC_*` vs `mcp_workflows.md` / domain guide (keep `_DESC_*` ≤ 2,500 chars)

## `server/constants.py`

- [ ] `TOOL_<NAME> = "<function_name>"`
- [ ] `MCP_PATH_<NAME> = "/api/v1/mcp/..."`
- [ ] Allow-lists / wire param names as `MCP_*` + `MCP_*_DOC` for docs, prompts, and short `Field` hints

## Helpers (`server/tools/<domain>/`)

- [ ] `_DESC_<NAME>` via `classify_tool_desc()` — compact routing; `confidential=True` only for access/RDAM tools
- [ ] Extended examples / matrices in `server/docs/mcp_workflows.md` or domain `*.md`
- [ ] `validate_*` or param builder returning `dict | None` (`None` = ok, else `error_payload(...)`)
- [ ] CamelCase mapping in builder or `drop_none`

## `server/tools/<domain>/register.py`

- [ ] Prefer `_invoke_*`: validation → `drop_none` → `ovaledge_client` → `map_ovaledge_error`
- [ ] `@mcp.tool(title=…, description=_DESC_*, annotations=…)` with `Annotated` + **one-line** `Field` per parameter
- [ ] `annotations` uses a profile from `server/tools/common/annotations.py` (`READ_ONLY`, `GOVERNED_CREATE`, `GOVERNED_UPDATE`, `GOVERNED_EXECUTE`) — never a hand-rolled dict
- [ ] `register(mcp)` exported from `server/tools/<domain>/__init__.py`
- [ ] Apply `slim_tool_response()` when tool returns large catalog/glossary payloads

## Registration wiring

- [ ] `server/mcp/bootstrap.py` calls `<domain>.register(mcp)` if new domain
- [ ] `server/tools/__init__.py` documents domain in module docstring
- [ ] `server/mcp_surface.py` — `TOOL_*` imported and added to `MCP_TOOL_NAMES`

## Tests

- [ ] `tests/tools/test_<name>.py` — happy path param forwarding
- [ ] Validation cases (missing args, mutual exclusion, invalid enums)
- [ ] `tests/client/test_mcp_surface_inventory.py` still passes
- [ ] `tests/tools/test_tool_description_budget.py` still passes
- [ ] Routing keywords in `_DESC_*`; deep rules in docs/constants if de-bloated

## Docs and prompts

- [ ] `server/docs/mcp_workflows.md` — tool routing table row (+ section if multi-param workflow)
- [ ] `server/docs/governance.md` or domain guide if governance/security boundary
- [ ] `server/app.py` instructions — only if new top-level agent route (keep brief)
- [ ] Workflow prompt in `server/prompts/workflows/register.py` if multi-step playbook needed
- [ ] `tests/prompts/test_workflows.py` — `_PROMPT_REQUIRED_TOOLS` entry
- [ ] Workflow prompts reference `docs://ovaledge/*` — do not embed full `MCP_*_DOC` allow-lists

## Optional

- [ ] `evals/golden_cases.py` golden for agent use case
- [ ] `tests/integration/` live test behind env guard
- [ ] `README.md` tools list one line

## Final verification

```bash
poetry run ruff check .
poetry run pytest tests/tools/ tests/tools/test_tool_description_budget.py tests/client/test_mcp_surface_inventory.py -q
```
