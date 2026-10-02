# AGENTS.md — oe_mcp

## Purpose and boundaries

OvalEdge MCP is a Python 3.12+ FastMCP server that exposes catalog, governance,
knowledge, RDAM, and data-quality capabilities to MCP clients. It uses Poetry.

- Keep diffs focused and follow the patterns in the affected domain package.
- Never commit `.env`, credentials, JWTs, OAuth client secrets, or live API data.
- Treat `server/docs/mcp_workflows.md` as the canonical agent-routing guide; do
  not invent alternate tool workflows.
- Preserve existing worktree changes outside the task. Do not use destructive Git
  commands unless explicitly requested.

## Setup and verification

```bash
poetry install --with dev
poetry run ruff check .
poetry run mypy server/ entrypoints/ evals/
./scripts/run_tests.sh                    # preferred: unit tests plus coverage
poetry run pytest                         # fast unit-test suite
poetry run oe-mcp-local                   # local stdio MCP server
./scripts/run_local_mcp_http.sh           # local HTTP server (AUTH_MODE=local)
```

For a local setup, copy `.env.example` to `.env` and run
`./scripts/setup_local_mcp.sh`. Keep `.env` local.

Live integration tests require a running OvalEdge environment and valid local
credentials; they must exercise MCP HTTP APIs only, never a direct database:

```bash
poetry run pytest -c tests/integration/pytest.ini tests/integration -m integration
```

Run the smallest relevant test first, then lint and type-check touched Python
code. Changes to the public MCP surface should also run the inventory,
description-budget, and in-process transport tests.

## Codebase navigation

| Concern | Start here |
| --- | --- |
| MCP application and server instructions | `server/app.py` |
| Registration orchestration | `server/mcp/bootstrap.py` |
| Tool names, paths, allow-lists, URI constants | `server/constants.py` |
| Canonical tool and workflow-prompt inventory | `server/mcp_surface.py` |
| Domain tools | `server/tools/{catalog,access,governance,servicedesk,dataquality,docs,rdam}/` |
| Shared validation, errors, annotations, confirm gate | `server/tools/common/` |
| Resource packages | `server/resources/{catalog,governance}/` |
| Agent routing and workflow documentation | `server/docs/mcp_workflows.md` |
| OAuth, bearer auth, remote credentials | `server/auth/` |
| OvalEdge HTTP client | `server/client.py` |
| Entrypoints | `entrypoints/local.py`, `entrypoints/http_local.py`, `entrypoints/lambda_handler.py` |
| Deployment | `infra/`, `Dockerfile`, `Dockerfile.ecs` |

The usual domain flow is a thin `register.py` (FastMCP decorator and `Field`
metadata), followed by `_invoke_*`/helper logic, then `server.client` calls.
Reuse common error handling and client wiring; do not recreate either.

## CodeGraph first

This repository has a `.codegraph/` index. Before using `rg`, `grep`, `find`, or
opening source files to locate or understand code, query CodeGraph:

```bash
codegraph explore "create_mcp registration flow"
codegraph explore "<symbol or file> callers callees and tests"
```

Use it for symbol discovery, call paths, dynamic dispatch, registration paths,
and blast-radius analysis across `server/`, `tests/`, `evals/`, and
`entrypoints/`. Its returned line-numbered source is current source—do not
immediately re-read the same region. Query a more specific symbol if the result
is deferred or incomplete.

Do not use CodeGraph for Markdown/infra-only changes, MCP workflow routing, or
new tool-contract design. If the index is unavailable or stale, report that
rather than initializing it unless asked; `docs/contributing/CODEGRAPH.md`
contains setup details.

## MCP tool and resource changes

For a new or materially changed MCP tool, read and follow
`.cursor/skills/oe-mcp-tool-design/SKILL.md` and its checklist before editing.
Key invariants:

1. Map one OvalEdge HTTP endpoint to one MCP tool. Use parameters instead of
   aliases for the same endpoint/method.
2. Use a snake_case function name and define the matching `TOOL_*` constant in
   `server/constants.py`. Prompts, docs, and tests should import that constant.
3. Keep `_DESC_*` descriptions in helpers compact and routing-focused. The
   per-description limit is 2,500 characters; the combined limit is 32,000.
   Put detailed playbooks in `server/docs/` and workflow prompts instead.
4. Every registration needs a verb-led `title` and a truthful annotation profile
   from `server/tools/common/annotations.py`: `READ_ONLY`, `GOVERNED_CREATE`,
   `GOVERNED_UPDATE`, or `GOVERNED_EXECUTE`.
5. Add the surface to `server/mcp_surface.py`, registration, tests, and routing
   docs/prompts together. Public inventory is tested in
   `tests/client/test_mcp_surface_inventory.py`.
6. If a description, prompt, or document references `docs://ovaledge/<name>`,
   `server/docs/<name>.md` must exist. The static-doc tests enforce this.

For governed writes, the required sequence is preview → show the user → explicit
user approval → repeat with `write_confirmed_by_user=true` and the confirmation
token. Never set that flag before approval. A preview must not persist a change;
do not label write-capable tools `READ_ONLY`.

Maintain these routing distinctions:

- Organizational knowledge and product how-to: `knowledge_search`.
- Catalog assets: `asset_explorer`, then `asset_details` after a shortlist.
- Native DB/BI grants: `access_explorer` with `operation=source_system_access` and
  native intent—never substitute catalog search or catalog-permissions tools.
- OvalEdge catalog permissions: `access_explorer` with `operation=catalog_access`, not RDAM.
- File access, content-change, or DQ-recommendation tickets: `create_service_request`
  (prompt `create_service_desk_request`) — not `access_explorer` and not
  `dq_rule_advisor`. Who-has-access stays `resolve_object_access`.
- For user-facing links, use `navLink` or `redirectUrl`; never show an
  `ovaledge://` URI.

## Testing and quality conventions

- Tests are async-friendly (`asyncio_mode = auto`) and should mock HTTP for unit
  coverage. Place tests beside the affected area under `tests/`.
- Integration tests discover fixtures through `asset_explorer`; see
  `tests/integration/helpers.py` and `tests/integration/README.md`.
- Ruff uses a 100-character line limit with `E`, `F`, `I`, and `UP` rules.
  MyPy is strict for `server/`, `entrypoints/`, and `evals/`.
- Keep tool descriptions and response shapes intentional: MCP context and
  response-size budgets are enforced by tests. Preserve `formattedResponse` when
  provided for presentation to the user.
- New configuration must be represented safely in the settings model and
  `.env.example`, never as a checked-in secret.

## Documentation and deployment

- Primary run/deploy references: `README.md`, `README_LOCAL_MCP.md`,
  `README_REMOTE_MCP.md`, and `infra/DEPLOY.md`.
- Client setup lives in `docs/client-setup/`; security reporting and expectations
  live in `SECURITY.md`.
- Remote credentials require HTTPS at the edge. Preserve the auth separation:
  local stdio uses its lifespan flow, while remote HTTP uses FastAPI auth
  middleware.
