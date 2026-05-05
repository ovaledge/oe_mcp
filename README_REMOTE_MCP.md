# Remote MCP (HTTP)

Run the same MCP tools over **HTTP** with FastAPI + Mangum (`entrypoints/lambda_handler.py`). Auth is selected with **`AUTH_MODE`** at process startup (Lambda environment, SAM template, or `.env` when using uvicorn).

**OAuth 2.x / OIDC remote MCP (`AUTH_MODE=remote`) is work in progress (WIP)** — not production-ready; prefer **`remote_credentials`** (header auth to OvalEdge) unless you are explicitly exercising the OAuth stack.

← [Back to main README](README.md) · [Local MCP (stdio)](README_LOCAL_MCP.md)

## Auth modes

| `AUTH_MODE` | Client credentials | OAuth / discovery routes | Notes |
| ------------- | -------------------- | -------------------------- | ----- |
| `remote` | `Authorization: Bearer <IdP access_token>` | `/.well-known/oauth-authorization-server`, `POST /register` | **OAuth 2.x remote MCP — WIP** — see below |
| `remote_credentials` | `X-OvalEdge-Token` + `X-OvalEdge-Secret` on each request | Minimal `/.well-known/*` stubs (no browser OAuth) | Per-user OvalEdge JWT cached server-side by credential key; many users share one process; use **HTTPS** |

Shared: `POST /mcp` (streamable HTTP), `GET /health`, `GET /`.

All variables are documented in [.env.example](.env.example).

## Work in progress: OAuth 2.x remote MCP

**WIP — not fully working end-to-end today.** `AUTH_MODE=remote` (OAuth 2.x / OIDC Bearer for this remote HTTP MCP server) — the `remote` stack (OIDC discovery, dynamic client registration, JWT validation against IdP JWKS, optional `POST /api/user/token/generate` to obtain an OvalEdge JWT, or forwarding the IdP token) is present in code but real IdP + MCP client flows still need validation.

Until stable, prefer **`remote_credentials`** or local stdio (**`AUTH_MODE=local`** — [README_LOCAL_MCP.md](README_LOCAL_MCP.md)).

**Relevant modules:** `server/auth/bearer_jwt.py`, `server/auth/oauth_discovery.py`, `server/auth/metadata.py`, `server/auth/registration.py`, `server/auth/middleware.py` (OAuth branch), `server/auth/token_exchange.py` (`exchange_oauth_access_token`).

## `remote_credentials` (header auth)

- Middleware reads **`X-OvalEdge-Token`** and **`X-OvalEdge-Secret`**, exchanges with OvalEdge, caches JWTs keyed by a digest of token+secret, sets `current_oe_jwt` and `current_oe_credential_cache_key` for the request.
- **HTTPS** is enforced for protected routes (`request.url.scheme` or `X-Forwarded-Proto: https`). Plain HTTP returns **400** `tls_required`.
- On downstream **401** from OvalEdge APIs, the in-memory cache entry for that credential key is dropped; the MCP client should **retry the same request** (headers unchanged) so the next call re-exchanges.
- Tunables: `CREDENTIALS_CACHE_MAX_ENTRIES` (see `server/config.py` / `.env.example`).

**Implementation files:** `server/auth/middleware.py`, `server/auth/credentials_cache.py`, `server/auth/token_exchange.py` (`exchange_user_credentials`, `get_or_refresh_user_token`), `server/auth/context.py`, `server/client.py` (`_send_with_401_handling`), `server/constants.py`.

## Entrypoint and deployment

- **App:** `entrypoints/lambda_handler.py` — `app` is shared; full OAuth routers ( **`remote` only — WIP** ) are included **only** when `settings.auth_mode == "remote"`. `remote_credentials` adds `server/auth/remote_credentials_discovery.py` only.
- **`MCP_HTTP_STATELESS`:** default **true** (good for Lambda). For **Cursor** (and similar) over plain HTTP, set **`MCP_HTTP_STATELESS=false`** so the MCP stack registers **GET** on `/mcp` for SSE fallback after Streamable HTTP negotiation. Without this, clients may get wrong `Content-Type` on GET.
- **Lambda / SAM:** [infra/template.yaml](infra/template.yaml) — `AuthMode` parameter (`remote` **(OAuth WIP)** | `remote_credentials`), CORS allows the OvalEdge header names, optional empty defaults for `OAuthIssuer` / `OAuthAudience` when using credentials-only stacks.
- **One-shot deploy:** from repo root, set `OVALEDGE_BASE_URL` and run [`scripts/deploy.sh`](scripts/deploy.sh) (`./scripts/deploy.sh --help` for env vars). Step-by-step copy-paste: [infra/DEPLOY.md](infra/DEPLOY.md).
- **Local HTTP (uvicorn):**

  ```bash
  export AUTH_MODE=remote_credentials
  poetry run uvicorn entrypoints.lambda_handler:app --host 127.0.0.1 --port 8000
  ```

## Testing `remote_credentials` on your laptop

Protected routes require **TLS or a proxy hint**: the app treats the request as HTTPS if `request.url.scheme == "https"` **or** the first value in `X-Forwarded-Proto` is `https`. Plain `http://127.0.0.1` **without** that header returns **400** `tls_required` (by design).

**1. Configure OvalEdge and mode**

In `.env` (or export in the shell before uvicorn):

- `AUTH_MODE=remote_credentials`
- `OVALEDGE_BASE_URL` — reachable OvalEdge base URL (same as you use for local stdio)
- `OVALEDGE_HTTP_AUTH_SCHEME=jwt` (typical)

**2. Start the HTTP app**

```bash
cd /path/to/oe_mcp
export AUTH_MODE=remote_credentials
export MCP_HTTP_STATELESS=false
# optional: export OVALEDGE_BASE_URL=...
poetry run uvicorn entrypoints.lambda_handler:app --host 127.0.0.1 --port 8000
```

**3. Probe token exchange (no HTTP server; hits OvalEdge directly)**

Uses the same body as the server for `POST /api/user/token/generate`:

```bash
export AUTH_MODE=remote_credentials
export OVALEDGE_USER_TOKEN='your-token'
export OVALEDGE_USER_SECRET='your-secret'
poetry run python scripts/validate_remote_mcp.py --credentials
```

**4. Call the running app through middleware**

Send **`X-Forwarded-Proto: https`** on each request so local HTTP is accepted (mimics API Gateway / ALB in front of TLS):

```bash
curl -sS -D - http://127.0.0.1:8000/health \
  -H 'X-Forwarded-Proto: https'

curl -sS -D - http://127.0.0.1:8000/mcp \
  -H 'X-Forwarded-Proto: https' \
  -H 'X-OvalEdge-Token: YOUR_USER_TOKEN' \
  -H 'X-OvalEdge-Secret: YOUR_USER_SECRET' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0.0.1"}}}'
```

Expect **200** from `/health`. For `/mcp`, a successful auth + initialize yields a normal MCP HTTP response (often SSE); **401** means missing/invalid headers or OvalEdge rejected the exchange.

**5. Automated tests**

```bash
poetry run pytest tests/auth/test_middleware_remote_credentials.py tests/auth/test_remote_credentials_discovery.py tests/auth/test_credentials_cache.py tests/client/test_remote_credentials_401_retry.py -q
```

**Real HTTPS locally (optional):** use a reverse proxy (Caddy/nginx) terminating TLS in front of uvicorn, or run uvicorn with `--ssl-keyfile` / `--ssl-certfile` so `https://127.0.0.1:8000` works without spoofing `X-Forwarded-Proto`.

### Cursor (HTTP MCP)

Cursor resolves `${env:VAR}` from **its own process environment**, not from the repo `.env` (unless you launch Cursor with those variables set). Use **`MCP_HTTP_STATELESS=false`** on the server when testing against `http://127.0.0.1`.

Example `mcp.json` fragment:

```json
{
  "mcpServers": {
    "ovaledge-remote": {
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "X-Forwarded-Proto": "https",
        "X-OvalEdge-Token": "${env:OVALEDGE_USER_TOKEN}",
        "X-OvalEdge-Secret": "${env:OVALEDGE_USER_SECRET}"
      }
    }
  }
}
```

Each end user should use **their own** token and secret; the server keeps a separate JWT cache entry per distinct `(token, secret)` pair (bounded by `CREDENTIALS_CACHE_MAX_ENTRIES`).

The MCP URL may be `http://127.0.0.1:8000/mcp` or `.../mcp/` — the server normalizes slashless `/mcp` so clients are not tripped by Starlette’s **307** redirect to `/mcp/`.

### VS Code + GitHub Copilot (HTTP MCP)

VS Code does **not** use Cursor’s `mcpServers` shape. GitHub Copilot reads **`mcp.json`** with a top-level **`servers`** object and HTTP entries need **`"type": "http"`**. See [Add and manage MCP servers in VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) and the [MCP configuration reference](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration).

- **Workspace:** create or edit **`.vscode/mcp.json`** in your project.  
- **User-wide:** Command Palette → **MCP: Open User Configuration** (opens profile `mcp.json`).  
- **Guided:** Command Palette → **MCP: Add Server**.

Use **`MCP_HTTP_STATELESS=false`** on the server when your client needs **GET `/mcp`** (same as Cursor / Claude Code above).

On **`https://…execute-api…/mcp`** (API Gateway), **`X-Forwarded-Proto`** is usually unnecessary; keep it if you see **`tls_required`** from middleware.

**`gh` (GitHub CLI)** does not configure VS Code MCP servers for your Lambda URL—configure **`mcp.json`** in VS Code (or use Cursor’s config in Cursor).

Example **`.vscode/mcp.json`** for `remote_credentials` (replace the URL; prefer **`inputs`** over hardcoding secrets—see reference *Input variables for sensitive data*):

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "ovaledge-token",
      "description": "OvalEdge user token",
      "password": true
    },
    {
      "type": "promptString",
      "id": "ovaledge-secret",
      "description": "OvalEdge user secret",
      "password": true
    }
  ],
  "servers": {
    "ovaledge-remote": {
      "type": "http",
      "url": "https://YOUR_API_ID.execute-api.REGION.amazonaws.com/mcp",
      "headers": {
        "X-OvalEdge-Token": "${input:ovaledge-token}",
        "X-OvalEdge-Secret": "${input:ovaledge-secret}"
      }
    }
  }
}
```

### Claude Code (HTTP MCP)

**Claude (including many Claude Desktop flows) does not rely on MCP Streamable HTTP the way Cursor does.** For HTTP access from **Claude Code** (the CLI-driven product), register the server with **`claude mcp`** using **`--transport http`**.

**Install Claude Code (CLI)** — the `claude mcp` subcommands require the Claude Code binary on your `PATH`. Official options (see [Claude Code setup](https://code.claude.com/docs/en/setup) for requirements and troubleshooting):

**macOS, Linux, or WSL:**

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://claude.ai/install.ps1 | iex
```

**Alternatives:** Homebrew — `brew install --cask claude-code`; Windows WinGet — `winget install Anthropic.ClaudeCode`.

After install, run **`claude`** once and complete Anthropic’s login / subscription flow before using **`claude mcp`**.

On the **server**, set **`MCP_HTTP_STATELESS=false`** (SAM parameter **`McpHttpStateless=false`** on Lambda, or `export MCP_HTTP_STATELESS=false` before uvicorn locally) so **`GET /mcp`** is registered and SSE-style fallback works for clients that do not stick to Streamable HTTP POST-only behavior.

**`<MCP_BASE_URL>`** is the full MCP endpoint URL (same as **`MCPEndpointUrl`** from deploy output or `https://…/mcp` / `http://127.0.0.1:8000/mcp`). Use **HTTPS** in production (API Gateway); for plain `http://127.0.0.1` you still need **`X-Forwarded-Proto: https`** on the server — the CLI does not add that automatically, so prefer a **TLS** URL or terminate TLS in front of the app.

**1. Register the remote MCP server**

Run this command from the same project/workspace folder where you will use Claude Code. If you run it from a different directory/profile, the MCP entry may be saved in a different scope and won’t appear in the workspace you expect.

```bash
claude mcp add --transport http ovaledge-remote <MCP_BASE_URL> \
  --header "X-OvalEdge-Token: YOUR_USER_TOKEN" \
  --header "X-OvalEdge-Secret: YOUR_USER_SECRET"
```

Replace **`YOUR_USER_TOKEN`** / **`YOUR_USER_SECRET`** with real OvalEdge credentials (avoid committing them or pasting them into shared logs).

**2. Use Claude Code**

Open **Claude Code** and run your usual sessions or commands; the **`ovaledge-remote`** MCP definition is picked up from the CLI configuration.

**3. Remove the remote MCP configuration**

```bash
claude mcp remove ovaledge-remote
```

## Validation script

From repo root:

```bash
poetry run python scripts/validate_remote_mcp.py --settings
poetry run python scripts/validate_remote_mcp.py --credentials   # remote_credentials: needs OvalEdge user token+secret
# OAuth 2.x remote MCP (WIP): set AUTH_MODE=remote and IdP/OAuth env from .env.example, then:
poetry run python scripts/validate_remote_mcp.py --all --token "$OAUTH_TEST_ACCESS_TOKEN"
```

`--all` runs settings, OIDC discovery, OvalEdge exchange, optional `--credentials`, and `--mcp` if a token is provided. See the script docstring for flags (`--discovery`, `--ovaledge`, `--mcp`, etc.).

## Security (remote)

- **`remote_credentials`:** long-lived OvalEdge credentials travel in **headers** — terminate TLS at the edge (API Gateway, ALB); never log header values.
- **`remote` (OAuth 2.x remote MCP, WIP):** treat IdP tokens like secrets in transit; configure `OAUTH_AUDIENCE` / issuer discovery carefully once OAuth remote MCP is out of WIP.

## Layout (remote-relevant paths)

- `entrypoints/lambda_handler.py` — HTTP app + Mangum handler
- `server/auth/middleware.py` — mode branches
- `server/auth/metadata.py`, `server/auth/registration.py` — OAuth `remote` only (**WIP**)
- `server/auth/remote_credentials_discovery.py` — `remote_credentials` only (well-known stubs + declined)
- `infra/template.yaml` — sample deploy
