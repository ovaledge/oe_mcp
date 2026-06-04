# New MCP tool checklist (oe_mcp)

## Design (before coding)

- [ ] Confirmed OvalEdge API path and method (GET vs POST) with backend team or OpenAPI
- [ ] No existing tool already calls this path (grep `MCP_PATH_` and path string)
- [ ] Tool name is verb-led snake_case (`search_*`, `lookup_*`, `create_*`, `update_*`, `source_system_access`-style noun only when established)
- [ ] Documented **negative routing** (which existing tools must be used instead)
- [ ] Decided read-only vs governed write (confirm gate required?)

## `server/constants.py`

- [ ] `TOOL_<NAME> = "<function_name>"`
- [ ] `MCP_PATH_<NAME> = "/api/v1/mcp/..."`
- [ ] Allow-lists / wire param names as `MCP_*` + `MCP_*_DOC` when reused in `Field(description=...)`

## `server/tools/<domain>/helpers.py`

- [ ] `_DESC_<NAME>` with Backend line, not-confused-with, examples
- [ ] `validate_*` or param builder returning `dict | None` (`None` = ok, else `error_payload(...)`)
- [ ] CamelCase mapping documented or centralized in builder

## `server/tools/<domain>/register.py`

- [ ] `_invoke_*` handles validation → `drop_none` → `ovaledge_client` → `map_ovaledge_error`
- [ ] `@mcp.tool(description=_DESC_*)` with `Annotated` + `Field` per parameter
- [ ] `register(mcp)` exported from `server/tools/<domain>/__init__.py`

## Registration wiring

- [ ] `server/mcp/bootstrap.py` calls `<domain>.register(mcp)` if new domain
- [ ] `server/tools/__init__.py` documents domain in module docstring
- [ ] `server/mcp_surface.py` — `TOOL_*` imported and added to `MCP_TOOL_NAMES`

## Tests

- [ ] `tests/tools/test_<name>.py` — happy path param forwarding
- [ ] Validation cases (missing args, mutual exclusion, invalid enums)
- [ ] `tests/client/test_mcp_surface_inventory.py` still passes
- [ ] Description tests for security/routing keywords if critical

## Docs and prompts

- [ ] `server/docs/mcp_workflows.md` — tool routing table row (+ section if multi-param workflow)
- [ ] `server/docs/governance_model.md` or domain guide if governance/security boundary
- [ ] `server/app.py` instructions — only if new top-level agent route (keep brief)
- [ ] Workflow prompt in `server/prompts/workflows/register.py` if multi-step playbook needed
- [ ] `tests/prompts/test_workflows.py` — `_PROMPT_REQUIRED_TOOLS` entry

## Optional

- [ ] `evals/golden_cases.py` golden for agent use case
- [ ] `tests/integration/` live test behind env guard
- [ ] `README.md` tools list one line

## Final verification

```bash
poetry run ruff check .
poetry run pytest tests/tools/ tests/client/test_mcp_surface_inventory.py -q
```
