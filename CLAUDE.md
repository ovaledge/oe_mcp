# CLAUDE.md — oe_mcp

OvalEdge MCP server (FastMCP): catalog, governance, knowledge, RDAM, and DQ tools for MCP clients. Python 3.12+, Poetry.

## Commands

```bash
poetry install --with dev
poetry run ruff check .
poetry run mypy server/ entrypoints/ evals/
./scripts/run_tests.sh                    # preferred unit tests + coverage
poetry run pytest                         # fast unit tests
poetry run oe-mcp-local                   # stdio MCP
./scripts/run_local_mcp_http.sh           # local HTTP (AUTH_MODE=local)

# Live integration (OvalEdge up; credentials in .env — never commit .env)
poetry run pytest -c tests/integration/pytest.ini tests/integration -m integration
```

Setup: `cp .env.example .env`, then `./scripts/setup_local_mcp.sh` (installs git hooks: ruff, mypy, pytest, CodeQL).

## CodeGraph (codebase navigation)

Local SQLite symbol graph for `server/`, `tests/`, `evals/`, `entrypoints/`. Prefer it over Grep/Read loops for callers, callees, registration paths, and blast radius. Details: `docs/contributing/CODEGRAPH.md`, rule: `.cursor/rules/codegraph.mdc`.

**Setup (once per machine + per clone):**

```bash
codegraph --version          # install CLI if missing
codegraph install            # wire CodeGraph MCP into Cursor; restart Cursor
codegraph init -i            # from repo root → creates .codegraph/ (not committed)
codegraph sync               # re-index if the watcher lags
```

Enable the **CodeGraph** MCP server in Cursor Settings → MCP. Pass `projectPath` to this repo when querying.

**Query:** call **`codegraph_explore`** first when you can name a symbol, file, or area (e.g. `verify_write_confirmation`, `source_system_access register`, `golden_cases`). Use the returned line-numbered source for edits; do not re-Read the same regions unless the tool reports staleness. If explore says the project is not indexed, tell the user to run `codegraph init -i` — do not run it yourself unless they ask.

**Do not use CodeGraph for:** OvalEdge runtime routing (`server/docs/mcp_workflows.md`, `docs://ovaledge/*`), new MCP tool contracts (`.cursor/skills/oe-mcp-tool-design`), or markdown/infra-only edits.

## Architecture (landmarks)

| Concern | Start here |
|---------|------------|
| App / server instructions | `server/app.py` |
| Paths, allow-lists, `TOOL_*` names | `server/constants.py` |
| Canonical tool/prompt inventory | `server/mcp_surface.py` |
| Tool packages | `server/tools/{catalog,access,governance,dataquality,docs,rdam}/` |
| Shared helpers / annotations / confirm gate | `server/tools/common/` |
| Agent routing docs | `server/docs/mcp_workflows.md` (`docs://ovaledge/mcp_workflows`) |
| Governance guide | `server/docs/governance.md` |
| HTTP client | `server/client.py` |
| Entrypoints | `entrypoints/local.py`, `entrypoints/http_local.py`, `entrypoints/lambda_handler.py` |

Domain layout: thin `register.py` (`@mcp.tool` + `Field`) → `_invoke_*` / helpers → OvalEdge HTTP. Do not duplicate client wiring or `error_payload`.

## Adding or changing MCP tools

Follow `.cursor/skills/oe-mcp-tool-design/SKILL.md` (and `checklist.md`). Hard rules:

1. **One OvalEdge endpoint → one MCP tool** — no alias tools on the same path/method; use parameters instead.
2. Tool name = snake_case function; add `TOOL_*` in `constants.py`; prompts/evals import the constant.
3. Descriptions: `_DESC_*` in helpers — compact routing only. Playbooks live in `server/docs/` + workflow prompts.
4. Every tool needs `title` (verb-led plain English) and an annotations profile from `server/tools/common/annotations.py` (`READ_ONLY`, `GOVERNED_CREATE`, `GOVERNED_UPDATE`, `GOVERNED_EXECUTE`).
5. **Context budget (tested):** each `_DESC_*` ≤ 2,500 chars; all descriptions combined ≤ 32,000 (`tests/tools/test_tool_description_budget.py`).
6. Governed writes: preview → user approval → `write_confirmed_by_user=true`. Tools with that gate must **not** be `READ_ONLY`.
7. Update inventory tests (`tests/client/test_mcp_surface_inventory.py`), unit tests, and docs/prompts when the surface changes.

Consolidated read family: `asset_explorer`, `asset_details`, `asset_lineage`, `knowledge_search`.

## Agent routing (do not invent)

| Intent | Tool |
|--------|------|
| Org knowledge / product how-to | `knowledge_search` |
| Find physical / catalog assets | `asset_explorer` → `asset_details` |
| Native DB/BI grants (RDAM) | `access_explorer` operation=source_system_access only — never fall back to explorer |
| Catalog permissions (OE user/role grants) | `access_explorer` operation=catalog_access — not RDAM |
| User-facing links | `navLink` / `redirectUrl` — never show `ovaledge://` URIs to users |

Full playbooks: `server/docs/mcp_workflows.md`.

## Testing

- Unit: `tests/tools/`, `tests/client/`, … — mock HTTP; keep inventory + description-budget green.
- Live ITs: `tests/integration/` — call MCP HTTP APIs against `OVALEDGE_BASE_URL` only. **No direct DB / MySQL / pymysql.** Discover fixtures via `asset_explorer` (see `tests/integration/helpers.py`).
- Evals (optional): `poetry install --with eval` → `evals/README.md`.

## Code style

- Ruff: line length 100, `E/F/I/UP`; MyPy strict on `server/`, `entrypoints/`, `evals/`.
- Prefer small, focused diffs; match existing patterns in the domain package you touch.
- Do not commit secrets (`.env`, tokens, JWT). Remote `remote_credentials` expects HTTPS at the edge.

## Docs map

- Run/deploy: `README.md`, `README_LOCAL_MCP.md`, `README_REMOTE_MCP.md`, `infra/DEPLOY.md`
- Client setup: `docs/client-setup/`
- CodeGraph: `docs/contributing/CODEGRAPH.md`
- Security: `SECURITY.md`
- Live IT harness: `tests/integration/README.md`
