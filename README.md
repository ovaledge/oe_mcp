# OvalEdge MCP Server

OvalEdge governance and catalog MCP server for MCP clients (Cursor, Claude Desktop, etc.): catalog discovery, lineage, glossary and tags, **data stories** for organizational knowledge, metadata drift, native source-system access previews, product docs, workflow prompts, and governed writes (glossary terms, tags, descriptions, roles) — all subject to OvalEdge RBAC. Server instructions in `server/app.py` tell agents to prefer **`lookup_datastory`** for internal policy/playbook questions and **`search_platform_docs`** only for OvalEdge product how-to.

## How to run / deploy

| Mode | Transport | Doc |
| ---- | ----------- | --- |
| **Local stdio** | `poetry run oe-mcp-local` | [README_LOCAL_MCP.md](README_LOCAL_MCP.md) |
| **Local HTTP** | `./scripts/run_local_mcp_http.sh` (`AUTH_MODE=local`) | [README_LOCAL_MCP.md](README_LOCAL_MCP.md) · Cursor: `ovaledge-local-http` |
| **Remote host HTTP** | `./scripts/run_remote_mcp_http.sh` (`remote_credentials`) or `./scripts/run_remote_oauth_mcp_http.sh` (`remote` / Okta) | [README_REMOTE_MCP.md](README_REMOTE_MCP.md) · [infra/DEPLOY.md](infra/DEPLOY.md#remote-host-http-ec2--vm) |
| **AWS ECS Fargate** | ALB + uvicorn image (`Dockerfile.ecs`) | [infra/DEPLOY.md](infra/DEPLOY.md#aws-ecs-fargate--alb) |
| **AWS Lambda** | Container or ZIP (`./scripts/deploy.sh`) | [README_REMOTE_MCP.md](README_REMOTE_MCP.md) · [infra/DEPLOY.md](infra/DEPLOY.md#aws-lambda--http-api) |

Full deployment matrix (auth, credentials, scripts): **[infra/DEPLOY.md](infra/DEPLOY.md)**.

**Editor / assistant connection:** [docs/client-setup/README.md](docs/client-setup/README.md) (Cursor, Kiro, Claude, GitHub Copilot in VS Code, Microsoft Copilot Studio / M365 — separate guides; last reviewed July 2026).

**`AUTH_MODE`** in `.env` (or process env): `local`, **`remote`** (Okta/OIDC Connect — forward Bearer), or `remote_credentials` (header token+secret). Full variable reference: [.env.example](.env.example).

**`.env` is not committed.** Copy the example, then edit:

```bash
cp .env.example .env
```

Setup scripts (`scripts/setup_local_mcp.sh`, `scripts/setup_local_mcp.ps1`) create `.env` from `.env.example` only if `.env` is missing; they do not overwrite an existing file.

## Observability (telemetry)

Optional OpenTelemetry trace export to [Phoenix](https://arize.com/docs/phoenix) or [Langfuse](https://langfuse.com/docs) via `TELEMETRY_BACKEND` (default `none`). Variable reference: [.env.example](.env.example). Lambda deploy: [infra/DEPLOY.md](infra/DEPLOY.md#telemetry-opentelemetry).

**Privacy:** enabled export sends tool spans that may include argument summaries (search terms, object ids) to your OTLP backend — review before pointing at a third-party host.

## What this server provides

- Catalog search and asset details (`search_catalog_assets`, `catalog_asset_details`) — paginate with `page` when results exceed one page
- Column profile, entity relationships, lineage, metadata drift (`metadata_changes_between_crawls`)
- Glossary lookup and guided term creation (`lookup_glossary_term`, `create_glossary_term`)
- Tag lookup and guided creation (`lookup_tags`, `create_tag`)
- **Data stories** for organizational knowledge (`lookup_datastory`) — not a substitute for `search_platform_docs`
- Platform product documentation (`search_platform_docs`)
- Native source-system grant previews (`source_system_access`) — Redshift / Snowflake / Tableau, not catalog ACLs
- OvalEdge catalog ACL (`get_user_object_access`) — user/role grants on catalog objects, not native RDAM
- DQ rule lookup (`lookup_dq_rule`)
- CDE / column DQ assessment — read-only (`assess_cde_dq`)
- Associate objects to data quality rules (`associate_dq_rule_objects`)
- Auto-create or associate data quality rules for CDE columns (`create_dq_rules`)
- Custom SQL DQ: `generate_dq_queries`, `validate_dq_queries`, `create_sql_dq_rule` (workflow prompt: `create_custom_sql_dq_workflow`)
- Asset description, CDE, governance role, and custom field updates (`update_asset_descriptions`, `update_cde_associations`, `update_governance_roles`, `update_custom_field_value`)
- Resource URIs (`ovaledge://catalog/...`, `ovaledge://governance/...`) and static guides (`docs://ovaledge/...`)
- Nineteen workflow prompts under `server/prompts/workflows/` (see below; canonical list in `server/mcp_surface.py`)

Read and write tools honor OvalEdge permissions — the MCP does not bypass RBAC.

## Agent guidance (mirrors `server/app.py` instructions)

These rules apply to every MCP session (also exposed to clients as server **instructions**):

| Topic | Behavior |
| ----- | -------- |
| **Organizational knowledge** | Call **`lookup_datastory`** first (`content_query` = user question; add `story_zone_name` or `story_name` when named). Present **`formattedResponse`** and lead with **`storyCitation`** verbatim. Do not answer from model memory when a story may exist. |
| **Product how-to** | Use **`search_platform_docs`** only for OvalEdge UI/features/configuration — not for internal policy or playbooks. |
| **Physical datasets** | Use **`search_catalog_assets`**; if results include `oestory`, follow with **`lookup_datastory`**. |
| **Native DB/BI access** | Use **`source_system_access`** only (RDAM SQL). Never fall back to **`search_catalog_assets`** when RDAM is empty or errors. |
| **Catalog ACL** | Use **`get_user_object_access`** for OvalEdge user/role grants on catalog objects — not **`source_system_access`**. |
| **Deep links** | Use **`ovaledge://...` resources** when you already have object ids; prefer lookup tools for rich formatted output. |
| **Governed writes** | **`create_glossary_term`**, **`create_tag`**, **`update_asset_descriptions`**, **`update_governance_roles`**, **`update_cde_associations`**, **`update_custom_field_value`**, **`associate_dq_rule_objects`**, **`create_dq_rules`**, **`validate_dq_queries`**, **`create_sql_dq_rule`**: show **`confirm_create`** / **`confirm_update`** preview, then POST only with **`write_confirmed_by_user=true`** (`dry_run` skips confirm on updates). |
| **Glossary placement** | Domain → category (when categories exist) → subcategory; never invent **`description`**; pass **`domain_name`** on first call when the user names a domain in natural language. |
| **Workflows** | Optional MCP **prompts** (discovery, lineage, stories, tags, drift, native access, creates, DQ, roles) — see [server/docs/mcp_workflows.md](server/docs/mcp_workflows.md). |

## Tools, resources, and prompts

### Tools (`server/tools/`) — 25 tools

Canonical inventory: `server/mcp_surface.py` (`MCP_TOOL_NAMES`).

**Catalog & access**

- `search_catalog_assets`, `catalog_asset_details`, `column_profile_statistics`
- `table_entity_relationships`, `asset_lineage`, `metadata_changes_between_crawls`
- `update_asset_descriptions`, `update_cde_associations`
- `get_user_object_access` (catalog ACL)

**Governance**

- `lookup_glossary_term`, `create_glossary_term`, `lookup_tags`, `create_tag`
- `lookup_datastory`, `update_governance_roles`, `update_custom_field_value`

**Native access (RDAM)**

- `source_system_access` (Redshift / Snowflake / Tableau grant previews)

**Data quality**

- `lookup_dq_rule`, `assess_cde_dq`, `associate_dq_rule_objects`, `create_dq_rules`, `generate_dq_queries`, `validate_dq_queries`, `create_sql_dq_rule`

**Platform docs**

- `search_platform_docs`

**`create_glossary_term` workflow:** (1) `term_name` → domain picker; (2) `term_name` + `domain_id` → category picker when categories exist (skip only after user says skip: `skip_category=true` + `category_skip_confirmed=true`); (3) subcategory picker when applicable; (4) non-blank `description` required; (5) `confirm_create` preview; (6) POST with `write_confirmed_by_user=true`. Manual pickers: `search_on=oeglobaldomain|category|subcategory`.

**`create_tag` workflow:** OPEN or SECURE mode from create-options; master/parent pickers with user confirmation flags; `confirm_create` preview; POST with `write_confirmed_by_user=true`. See [server/docs/tags_guide.md](server/docs/tags_guide.md).

**`update_asset_descriptions` / `update_governance_roles` / `update_cde_associations` / `update_custom_field_value`:** Same confirm gate (`confirm_update`, `write_confirmed_by_user=true`) before POST; `dry_run=true` validates without confirm.

**DQ governed writes (`associate_dq_rule_objects`, `create_dq_rules`, `validate_dq_queries`, `create_sql_dq_rule`):** Same confirm gate before POST. `generate_dq_queries` is read-only (no confirm). Workflow prompts: `assess_cde_dq_coverage`, `create_custom_sql_dq_workflow`.

**Data stories:** Prefer `lookup_datastory` (`content_query`) for organizational knowledge; use `organizational_knowledge` prompt. Not `search_platform_docs`. See [server/docs/data_stories.md](server/docs/data_stories.md).

**Agent guides (static MCP doc resources):** [server/docs/mcp_workflows.md](server/docs/mcp_workflows.md) (tools, resources, prompts index), [glossary_guide.md](server/docs/glossary_guide.md), [governance_model.md](server/docs/governance_model.md), [asset_types.md](server/docs/asset_types.md). Exposed as `docs://ovaledge/{name}` (e.g. `docs://ovaledge/mcp_workflows`).

### Resources (`server/resources/`)

- `ovaledge://catalog/table/{object_id}` — oetable catalog document
- `ovaledge://catalog/file/{object_id}` — oefile catalog document
- `ovaledge://governance/glossary-term/{object_id}` — glossary term
- `ovaledge://governance/data-story/{object_id}` — data story (prefer `lookup_datastory` for narrative)
- `ovaledge://governance/tag/{object_id}` — tag (prefer `lookup_tags` for hierarchy)

Static product docs: `docs://ovaledge/...` (all `server/docs/*.md`, including `mcp_workflows`, `data_stories`, `tags_guide`).

### Prompts (`server/prompts/workflows/`) — 20 prompts

Full list: [server/docs/mcp_workflows.md](server/docs/mcp_workflows.md#workflow-prompts). Inventory: `server/mcp_surface.py` (`MCP_WORKFLOW_PROMPT_NAMES`).

Discovery: `data_discovery`, `explore_data_domain`, `find_related_assets`.  
Knowledge: `explain_business_term`, `organizational_knowledge`, `explain_tag`, `explain_dq_rule`, `platform_help`.  
Lineage & quality: `trust_assessment`, `trace_data_lineage`, `metadata_drift`, `assess_cde_dq_coverage`.  
Access: `native_source_access`, `catalog_object_access`, `dam_object_browse`.  
Writes (human-in-the-loop): `create_business_glossary_term`, `create_governance_tag`, `document_asset_descriptions`, `assign_governance_roles`.  
DQ writes (user-approved after `assess_cde_dq`): use `associate_dq_rule_objects`, `create_dq_rules` tools directly.

## Development

```bash
poetry run ruff check .
poetry run mypy server/ entrypoints/ evals/
./scripts/run_tests.sh          # recommended: Poetry venv + coverage
# or: poetry run pytest         # fast, no coverage (after poetry install --with dev)
```

Use `./scripts/run_tests.sh` on macOS and Linux so tests always run in the project `.venv` with coverage. Plain `pytest` on system Python can pick up this repo’s config but lacks dev plugins — prefer `poetry run pytest` or the script.

Unit tests measure coverage for `server/` and `entrypoints/` (report-only threshold for now; see `[tool.coverage.*]` in `pyproject.toml`). HTML report: `./scripts/run_tests.sh --cov-report=html` then open `htmlcov/index.html`.

Git hooks (**ruff**, **mypy**, **pytest**, and **CodeQL** on each **commit**) are installed automatically when you run `./scripts/setup_local_mcp.sh` in a git clone. CodeQL is **required** locally by default (`scripts/run_codeql.sh`); install the CLI once, then refresh hooks:

```bash
./scripts/install_codeql_cli.sh        # one-time (~CodeQL bundle download)
export PATH="$HOME/.local/bin:$PATH"   # if needed
./scripts/setup_git_hooks.sh
```

Skip CodeQL for a single commit with `CODEQL_SKIP=1`, or set `CODEQL_REQUIRED=0` if the CLI is unavailable. Local/CI analysis uses [`.github/codeql/codeql-config.yml`](.github/codeql/codeql-config.yml) so `.aws-sam/` build trees and venvs are **not** scanned (those copies of `server/` and vendored deps make scans slow and noisy). GitHub Actions runs [`.github/workflows/codeql.yml`](.github/workflows/codeql.yml) on PRs/pushes to `main`/`dev`.

See `.pre-commit-config.yaml` for hook definitions.

Optional LLM-level MCP checks: `poetry install --with eval`, then see [evals/README.md](evals/README.md).

**Contributors (Cursor):** optional [CodeGraph](docs/contributing/CODEGRAPH.md) index for faster structural navigation (`codegraph init -i` from repo root).

## Security (summary)

See **[SECURITY.md](SECURITY.md)** for the GitHub security policy (supported versions, private vulnerability reporting, Dependabot).

- Report vulnerabilities via **Security** → **Report a vulnerability** on GitHub (preferred), not public issues.
- Dependabot opens weekly PRs for Python, GitHub Actions, and Docker dependencies (see `.github/dependabot.yml`).

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
| `server/telemetry/` | OpenTelemetry OTLP export (Phoenix / Langfuse) |
| `server/client.py` | OvalEdge HTTP client |
| `server/tools/`, `server/resources/`, `server/prompts/` | MCP surface |
| `infra/template.yaml` | SAM sample for remote HTTP (`AuthMode`: `remote_credentials` or Okta **`remote`**) |
| `scripts/` | Setup and validation helpers |

More detail: [README_LOCAL_MCP.md](README_LOCAL_MCP.md#layout-local-relevant-paths) · [README_REMOTE_MCP.md](README_REMOTE_MCP.md#layout-remote-relevant-paths)
