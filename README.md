# oe_mcp — OvalEdge MCP Server (Phase 1)

Python [Model Context Protocol](https://modelcontextprotocol.io/) server for the **OvalEdge** data governance platform. Phase 1 is **read-only**: catalog search, asset details, glossary, lineage, relationships, and documentation search, plus static context docs and workflow prompts.

## Modes

| Mode | Transport | Auth |
|------|-----------|------|
| **Local** | stdio (`poetry run oe-mcp-local`) | OvalEdge **user token + user secret** exchange → OvalEdge JWT at process startup (machine principal; not per end-user RBAC like the UI). |
| **Remote** | Streamable HTTP on AWS Lambda (Mangum) | OAuth **access token** (JWT) per request; IdP from **OIDC / RFC 8414 discovery** (`OAUTH_ISSUER`, `OAUTH_AUDIENCE`) → OvalEdge JWT via token exchange. |

All OvalEdge calls use the JWT in the `current_oe_jwt` context (set by local lifespan or remote middleware). RBAC is enforced only by OvalEdge.

## Setup

```bash
./scripts/setup.sh
# or: pip install poetry && poetry install && cp .env.example .env
```

Edit `.env` with your OvalEdge base URL and local credentials. For CI and tests, `OVALEDGE_BASE_URL` must be set (see `.github/workflows/ci.yml`).

## Run locally (Cursor / Claude Desktop)

Configure your MCP client to run:

- **command:** `poetry`
- **args:** `run`, `oe-mcp-local`
- **cwd:** this repository
- **env:** `OVALEDGE_BASE_URL`, `OVALEDGE_USER_TOKEN`, `OVALEDGE_USER_SECRET`, `AUTH_MODE=local`

## Remote (Lambda)

- Build/push the image and deploy SAM: see [`scripts/deploy.sh`](scripts/deploy.sh) and [`infra/template.yaml`](infra/template.yaml). Stack parameters are `OAuthIssuer` and `OAuthAudience` (plus OvalEdge settings).
- Point MCP clients at `https://<api-id>.execute-api.<region>.amazonaws.com/mcp` (OAuth discovery at `/.well-known/oauth-authorization-server`).
- **Mangum** uses `lifespan="auto"` so the FastMCP streamable-HTTP session manager starts correctly (the raw spec’s `lifespan="off"` would skip ASGI startup and break MCP).

## API paths (TBC)

OvalEdge REST paths and token-exchange payloads are marked `TODO` in code until confirmed from OvalEdge API docs (see implementation spec §25).

## Development

```bash
poetry run ruff check .
poetry run mypy server/ entrypoints/
poetry run pytest
```

## License

See [LICENSE](LICENSE).
