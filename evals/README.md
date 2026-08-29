# OvalEdge MCP — DeepEval (Tier 2)

LLM-as-judge checks on **how well an agent uses MCP** (tool choice, arguments, multi-turn flows). Tier 1 remains `pytest` + FastMCP in-process tests under `tests/`.

Main project docs: [README.md](../README.md) (local stdio, remote HTTP, Okta `remote` OAuth). Agent routing (data stories vs platform docs, confirm-before-create): [README.md#agent-guidance](../README.md#agent-guidance-mirrors-serverapppy-instructions).

## Install

```bash
poetry install --with eval
```

Pinned package: `deepeval` (`>=3.9.9,<4.2.0`) in the `eval` Poetry group (`pyproject.toml`).

## Environment

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required for real eval runs (judge model). |
| `DEEPEVAL_JUDGE_MODEL` | Optional; default `gpt-4o-mini`. |
| `DEEPEVAL_THRESHOLD` | Optional; default `0.5` (metric `success` vs threshold). |
| `DEEPEVAL_TELEMETRY_OPT_OUT` | Set to `YES` by `run_evals.py` (DeepEval telemetry). |
| `DEEPEVAL_MCP_USE_CASES_JSON` | Optional path to JSON for pytest `test_mcp_use_metric_from_user_json_file`. |

If `OPENAI_API_KEY` is unset, `python -m evals.run_evals` **exits 0** after printing a skip message (fork-friendly CI). Use `--require-key` to exit `2` when the key is missing.

### GitHub Actions secret (public repo)

1. Create repo secret **`OPENAI_API_KEY`** (Settings → Secrets and variables → Actions).
2. Optional Actions variable **`DEEPEVAL_JUDGE_MODEL`** (e.g. `gpt-4o-mini`).
3. Run **Eval nightly (DeepEval MCP)** via **Actions → workflow_dispatch**, or wait for the daily cron.
4. Forks never receive your secrets; keep “secrets for PRs from forks” disabled.

The nightly job always runs:

1. **Structural gates** — `test_json_cases_loader`, `test_red_team_cases`, golden construct/coverage/rigor (**must pass**, no LLM key).
2. **`--dry-run`** — builds Python goldens plus both example JSON files (happy-path + red-team).
3. **LLM golden metrics** — `test_mcp_deepeval.py` (skips without key; `continue-on-error: true`).
4. **LLM red-team metrics** — same key, `DEEPEVAL_MCP_USE_CASES_JSON=evals/examples/mcp_red_team_cases.example.json`, plus `run_evals --cases-json … --output evals/out/red-team-report.json` (`continue-on-error: true`).

Artifacts: `evals/out/eval-pytest.xml`, `red-team-pytest.xml`, `red-team-report.json`.

## User-provided JSON (MCPUseMetric)

DeepEval does not run arbitrary JSON by itself. You describe each scenario in JSON; this repo **loads** it into `LLMTestCase` (see `evals/json_cases.py`) and then runs **`MCPUseMetric`** the same way as for Python goldens.

1. **Author a file** — root is either a JSON **array** of cases, or an object with a **`mcp_use_cases`** (or `cases`) array. Each element needs **`input`**, **`actual_output`**, and **`mcp_tools_called`** (array of `{ "name", "args"?, "result"? }`). The `result` object is the tool payload (same shape as in `golden_cases.py` / `tool_call_result`).

2. **Validate without LLM:**

   ```bash
   poetry run python -m evals.run_evals --dry-run --cases-json path/to/your.json
   ```

3. **Run metrics (JSON replaces the two built-in MCPUse goldens; conversational goldens unchanged):**

   ```bash
   poetry run python -m evals.run_evals --cases-json path/to/your.json --output evals/out/report.json
   ```

4. **Or pytest** (same metric; set env to your file):

   ```bash
   export DEEPEVAL_MCP_USE_CASES_JSON=/absolute/path/to/your.json
   poetry run pytest evals/test_mcp_deepeval.py::test_mcp_use_metric_from_user_json_file -v
   ```

Example schema: `evals/examples/mcp_use_cases.example.json`. **v1 JSON** covers **tools** only (`mcp_prompts_called` / `mcp_resources_called` for file-driven cases stay in Python `golden_cases.py` until you extend the loader). Tool names must appear in `server/mcp_surface.py` (`MCP_TOOL_NAMES`).

Optional per-case flag **`llm_score`: false** — keep the row for structural happy/adverse coverage, but skip it in `run_evals` / DeepEval pytest (`load_mcp_use_cases_from_json(..., llm_only=True)`). Use this for intentional invalid-argument fixtures: `MCPUseMetric` always penalizes bad args, even when the fixture documents server-side validation.

The example file is gated by `evals/test_json_cases_loader.py`: every registered tool must appear in **≥1 happy** success result and **≥1 adverse** result (API/`status_code` error, empty search, confirm preview / `doNot*`, Deep Analysis fallback, or `ACCESS_INTENT_REQUIRED`).

## Red team (MCP agent misuse)

Adversarial agent-routing cases live in [`evals/examples/mcp_red_team_cases.example.json`](examples/mcp_red_team_cases.example.json). They encode **safe** behavior under attack prompts (confirm-gate bypass, forged tokens, access-intent skip, catalog-vs-RDAM misuse, secret exfil requests, docs-vs-datastory injection).

Case `input` fields are framed as **`[Safety eval] … Correct agent behavior: …`** so `MCPUseMetric` judges the safe golden (not the attacker's demand).

Structural checks (no LLM key):

```bash
poetry run pytest evals/test_red_team_cases.py -q
```

LLM judge (uses your secret) — also runs on **Eval nightly** when `OPENAI_API_KEY` is set:

```bash
export DEEPEVAL_MCP_USE_CASES_JSON="$PWD/evals/examples/mcp_red_team_cases.example.json"
poetry run pytest evals/test_mcp_deepeval.py::test_mcp_use_metric_from_user_json_file -v
# or
poetry run python -m evals.run_evals \
  --cases-json evals/examples/mcp_red_team_cases.example.json \
  --output evals/out/red-team-report.json
```

These are **MCP contract / agent-routing** red teams, not full DeepTeam attack generation. Extend the JSON when you find a new misuse pattern.

## Commands

Dry-run (no LLM; validates golden case objects):

```bash
poetry run python -m evals.run_evals --dry-run
```

**Pytest suite** (same goldens + metrics via DeepEval `assert_test`; skips when no API key):

```bash
poetry run pytest evals/test_mcp_deepeval.py -v
```

JUnit XML (e.g. for CI artifacts):

```bash
mkdir -p evals/out && poetry run pytest evals/test_mcp_deepeval.py -v --junit-xml=evals/out/eval-pytest.xml
```

Full run via script (writes JSON when `--output` is set; add `--cases-json` for file-driven MCPUse cases):

```bash
poetry run python -m evals.run_evals --output evals/out/report.json
```

## Golden cases

Defined in `golden_cases.py`:

- `MCPUseMetric` — single-turn goldens: asset exploration (keywords + `context_query`; nested `filters` for certification / `tableType` / open-ended `dqIndex`, `rating`, or `popularity` min, plus `createdDate` `{from,to}` — backend **POST** `/api/v1/mcp/asset-explorer`), `data_discovery` prompt + search, `knowledge_search`, `organizational_knowledge` prompt + knowledge search, `access_explorer` (`operation=source_system_access` and `operation=catalog_access`), first-person “I want access…” → `create_service_request` (not `access_explorer`).
- Filter-only catalog search is a valid `asset_explorer` call: omit `search_terms`, pass `filters` (and optional `object_type`). Do not flatten extra global-search facets into extra FastMCP fields. JSON examples: `example_catalog_filters_certified_views`, `example_catalog_dq_index_range`, `example_catalog_rating_min_filter`, `example_catalog_rating_more_than_filter`, `example_catalog_rating_max_filter`, `example_catalog_popularity_min_filter`, `example_catalog_created_date_filter`, `example_catalog_null_density_eq`, `example_catalog_filters_no_match`.
- `MCPTaskCompletionMetric` — conversational discovery with expected outcome.
- `MultiTurnMCPUseMetric` — follow-up user turn with resource read.

`mcp_eval_helpers.py` registers **all** tools, workflow prompts, and OvalEdge resource templates from `server/mcp_surface.py` for judge context.

## Interpreting judge scores

All metrics use an LLM judge (`DEEPEVAL_JUDGE_MODEL`, default `gpt-4o-mini`). **`success: true` means `score >= threshold`** (default `0.5`), not a perfect run.

Typical patterns in reports:

| Score band | Meaning |
|------------|---------|
| **1.0** | Judge fully agrees tool choice, args, and outcome (see `task_completion_discovery`). |
| **0.75** | Correct primary tool; judge nitpicks optional follow-ups (e.g. “could also call asset_details”). |
| **0.5** | Passes threshold but judge wanted a different tool or richer args — often because the golden registered **all** MCP tools and the judge prefers alternates. |

Goldens now pass **subset** `tool_names` / `prompt_names` into `ovaledge_eval_mcp_server()` so the judge only sees relevant tools. **`actual_output`** text explicitly states why other tools were *not* used (e.g. knowledge search vs asset discovery).

**MultiTurnMCPUseMetric** at `0.5` is common even when passing; treat as advisory ([DeepEval #2579](https://github.com/confident-ai/deepeval/issues/2579)). The lineage golden now calls **`asset_lineage`** plus a catalog resource read.

Re-run after golden tweaks:

```bash
poetry run python -m evals.run_evals --output evals/out/report.json
```

## Score thresholds and governance

- **Default threshold:** `0.5` (DeepEval default). Raise gradually (e.g. `0.6` → `0.7`) as golden sets stabilize.
- **Release gating:** Prefer gating **releases** or **nightly** jobs on eval pass, not every PR (cost + judge variance).
- **Human review:** Any drop > 0.1 vs last baseline, or `success: false` with score near threshold, should get a quick human review before blocking a train.
- **Baselines:** Store `evals/out/report.json` from green nightly runs as named artifacts; compare in spreadsheets or a future small script.

## Known limitations

1. **MultiTurn MCP + Pydantic:** DeepEval issue [#2579](https://github.com/confident-ai/deepeval/issues/2579) describes `Turn._mcp_interaction` staying false under some Pydantic v2 paths, which can deflate **MultiTurnMCPUseMetric** scores. Treat multi-turn scores as **advisory** until verified on your pinned `deepeval` + `pydantic` stack; pin versions in `pyproject.toml` / lockfile.
2. **Judge variance:** Different `DEEPEVAL_JUDGE_MODEL` versions can shift scores; pin model name per pipeline.
3. **Golden data drift:** When OvalEdge tool names or schemas change, update `golden_cases.py` and `ovaledge_eval_mcp_server()` in `mcp_eval_helpers.py`.
