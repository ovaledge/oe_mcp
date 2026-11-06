# CodeGraph (contributors)

[CodeGraph](https://github.com/colbymchenry/codegraph) indexes this repo into a **local SQLite code graph** (symbols, callers, callees, imports). Cursor connects via MCP so agents can query structure in one call instead of repeated grep/read loops.

**Scope:** editing **oe_mcp** in Cursor. This is separate from OvalEdge MCP **`docs://ovaledge/*`** resources (runtime tool routing for catalog/governance clients).

---

## One-time setup

You already need CodeGraph installed (`codegraph --version`). Wire MCP into Cursor once (if not done):

```bash
codegraph install
```

Restart Cursor after `install`.

---

## Per clone (this repo)

From the repo root:

```bash
codegraph init -i
```

- Creates `.codegraph/codegraph.db` (local only; not committed — see `.codegraph/.gitignore`).
- File watcher keeps the index updated as you edit.

Re-index manually if needed:

```bash
codegraph sync
```

---

## Using it in Cursor

1. Enable the **CodeGraph** MCP server in Cursor Settings → MCP (added by `codegraph install`).
2. Open this repo as the workspace root.
3. **Project rule:** `.cursor/rules/codegraph.mdc` applies when you edit `server/`, `tests/`, `evals/`, or `entrypoints/` Python — agents should call **`codegraph_explore`** before Grep/Read for structural work.
4. Prefer **`codegraph_explore`** when you need:
   - Who calls `verify_write_confirmation` or `register` in a domain package
   - Impact before changing `server/constants.py` or `mcp_surface.py`
   - The path from `helpers._DESC_*` → `register.py` → tests

**Still use for oe_mcp work:**

| Need | Use |
|------|-----|
| MCP tool contract / new tool | `@oe-mcp-tool-design` skill |
| OvalEdge routing (RDAM vs catalog permissions) | `server/docs/mcp_workflows.md`, `rdam_source_access.md` |
| Runtime agent docs | `docs://ovaledge/*` on the running MCP server |

CodeGraph does **not** encode which MCP tool answers a user question — use static docs and workflow prompts for that.

---

## oe_mcp structural landmarks

| Area | Path |
|------|------|
| Tool registration | `server/tools/<domain>/register.py` |
| Descriptions | `server/tools/<domain>/helpers.py` (`_DESC_*`) |
| HTTP paths / allow-lists | `server/constants.py` |
| Canonical tool names | `server/mcp_surface.py` |
| Governed-write tokens | `server/tools/common/confirm_gate.py` |
| Static agent docs | `server/docs/*.md` → `docs://ovaledge/{stem}` |
| Eval goldens | `evals/golden_cases.py`, `evals/golden_cases_coverage.py` |

---

## Telemetry

CodeGraph may collect anonymous usage stats. Disable locally:

```bash
codegraph telemetry off
# or: export CODEGRAPH_TELEMETRY=0
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| CodeGraph tools missing in Cursor | `codegraph install`, restart Cursor |
| Stale symbol results | `codegraph sync` from repo root |
| Empty graph | Run `codegraph init -i` from repo root (not a parent folder) |
