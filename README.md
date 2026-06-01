# OvalEdge MCP Server

OvalEdge governance and catalog capabilities exposed to MCP clients (Cursor, Claude Desktop, etc.): search, lineage, glossary, tags, docs, asset description updates, and workflow prompts.

## How to run

| Mode | Transport | Doc |
| ---- | ----------- | --- |
| **Local** | stdio (`poetry run oe-mcp-local`) | [README_LOCAL_MCP.md](README_LOCAL_MCP.md) |
| **Remote (HTTP)** | `uvicorn entrypoints.lambda_handler:app` or AWS Lambda (Mangum) | [README_REMOTE_MCP.md](README_REMOTE_MCP.md) — use **`remote_credentials`** for supported header auth; **OAuth 2.x / OIDC (`AUTH_MODE=remote`) is WIP** |

**Editor / assistant connection:** [docs/client-setup/README.md](docs/client-setup/README.md) (Cursor, Kiro, Claude, GitHub Copilot in VS Code, Microsoft Copilot in Studio — separate guides).

**`AUTH_MODE`** in `.env` (or process env) selects behavior: `local`, **`remote` (OAuth 2.x remote MCP — WIP)**, or `remote_credentials`. Full variable reference: [.env.example](.env.example).

**`.env` is not committed.** Copy the example, then edit:

```bash
cp .env.example .env
```

Setup scripts (`scripts/setup_local_mcp.sh`, `scripts/setup_local_mcp.ps1`) create `.env` from `.env.example` only if `.env` is missing; they do not overwrite an existing file.

## OAuth 2.x remote MCP — work in progress

**`AUTH_MODE=remote` (OAuth 2.x / OIDC Bearer for remote HTTP MCP) is WIP** and not fully validated end-to-end with real IdPs and MCP clients. Prefer **`remote_credentials`** (HTTP headers to OvalEdge) or **`local`** (stdio) until OAuth remote MCP is stable. Details: [README_REMOTE_MCP.md](README_REMOTE_MCP.md#work-in-progress-oauth-remote-mode).

## What this server provides

- Catalog search, asset details, and description updates (`search_catalog_assets`, `catalog_asset_details`, `update_asset_descriptions`)
- Column profile, entity relationships, lineage
- Glossary and tag lookups
- Platform documentation search
- Resource URIs (`ovaledge://...`)
- Workflow prompts for common analyst tasks (see `server/prompts/workflows.py`)

## Tools, resources, and prompts

### Tools (`server/tools/`)

- `search_catalog_assets`, `catalog_asset_details`, `update_asset_descriptions`, `column_profile_statistics`
- `table_entity_relationships`, `asset_lineage`
- `lookup_glossary_term`, `lookup_tags`, `lookup_datastory`, `search_platform_docs`

### Resources (`server/resources/`)

- `ovaledge://catalog/table/{object_id}`
- `ovaledge://governance/glossary-term/{object_id}`

### Prompts (`server/prompts/workflows.py`)

Data discovery, explain business term, trust assessment, explore domain, trace lineage, find related assets, platform help.

## Development

```bash
poetry run ruff check .
poetry run mypy server/ entrypoints/ evals/
poetry run pytest
```

Unit tests measure coverage for `server/` and `entrypoints/` (report-only threshold for now; see `[tool.coverage.*]` in `pyproject.toml`). HTML report: `poetry run pytest --cov-report=html` then open `htmlcov/index.html`.

Git hooks (**ruff** + full **pytest** on each **commit**; optional pytest again on **push**) are installed automatically when you run `./scripts/setup_local_mcp.sh` in a git clone. To install or refresh hooks only:

```bash
chmod +x scripts/setup_git_hooks.sh   # once, if needed
./scripts/setup_git_hooks.sh
```

See `.pre-commit-config.yaml` for hook definitions.

Optional LLM-level MCP checks: `poetry install --with eval`, then see [evals/README.md](evals/README.md).

## Security (summary)

See **[SECURITY.md](SECURITY.md)** for reporting, deployment surface, and dependency practices.

- Do not commit real OvalEdge tokens or secrets.
- Remote header mode (`remote_credentials`) requires **HTTPS** at the edge; see [README_REMOTE_MCP.md](README_REMOTE_MCP.md#security-remote).
- Local secrets: [README_LOCAL_MCP.md](README_LOCAL_MCP.md#security-local).

## Repository layout (overview)

| Path | Role |
| ---- | ---- |
| `entrypoints/local.py` | Stdio MCP |
| `entrypoints/lambda_handler.py` | HTTP MCP (Mangum) |
| `server/app.py` | FastMCP app assembly |
| `server/auth/` | Auth, token exchange, middleware |
| `server/client.py` | OvalEdge HTTP client |
| `server/tools/`, `server/resources/`, `server/prompts/` | MCP surface |
| `infra/template.yaml` | SAM sample for remote HTTP (`AuthMode`: `remote_credentials` or OAuth **`remote` (WIP)**) |
| `scripts/` | Setup and validation helpers |

More detail: [README_LOCAL_MCP.md](README_LOCAL_MCP.md#layout-local-relevant-paths) · [README_REMOTE_MCP.md](README_REMOTE_MCP.md#layout-remote-relevant-paths)
