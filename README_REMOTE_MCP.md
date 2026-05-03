# Remote MCP (HTTP)

Run the same MCP tools over **HTTP** with FastAPI + Mangum (`entrypoints/lambda_handler.py`). Auth is selected with **`AUTH_MODE`** at process startup (Lambda environment, SAM template, or `.env` when using uvicorn).

← [Back to main README](README.md) · [Local MCP (stdio)](README_LOCAL_MCP.md)

## Auth modes

| `AUTH_MODE` | Client credentials | OAuth routes | Notes |
| ------------- | -------------------- | ------------ | ----- |
| `remote` | `Authorization: Bearer <IdP access_token>` | `/.well-known/oauth-authorization-server`, `POST /register` | **WIP** — see below |
| `remote_credentials` | `X-OvalEdge-Token` + `X-OvalEdge-Secret` on each request | Minimal `/.well-known/*` stubs (no browser OAuth) | Per-user OvalEdge JWT cached server-side by credential key; many users share one process; use **HTTPS** |

Shared: `POST /mcp` (streamable HTTP), `GET /health`, `GET /`.

All variables are documented in [.env.example](.env.example).

## Work in progress: OAuth remote mode

**WIP — not fully working end-to-end today.** `AUTH_MODE=remote` (OAuth 2.x / OIDC Bearer) — the `remote` stack (OIDC discovery, dynamic client registration, JWT validation against IdP JWKS, optional `POST /api/user/token/generate` to obtain an OvalEdge JWT, or forwarding the IdP token) is present in code but real IdP + MCP client flows still need validation.

Until stable, prefer **`remote_credentials`** or local stdio (**`AUTH_MODE=local`** — [README_LOCAL_MCP.md](README_LOCAL_MCP.md)).

**Relevant modules:** `server/auth/bearer_jwt.py`, `server/auth/oauth_discovery.py`, `server/auth/metadata.py`, `server/auth/registration.py`, `server/auth/middleware.py` (OAuth branch), `server/auth/token_exchange.py` (`exchange_oauth_access_token`).

## `remote_credentials` (header auth)

- Middleware reads **`X-OvalEdge-Token`** and **`X-OvalEdge-Secret`**, exchanges with OvalEdge, caches JWTs keyed by a digest of token+secret, sets `current_oe_jwt` and `current_oe_credential_cache_key` for the request.
- **HTTPS** is enforced for protected routes (`request.url.scheme` or `X-Forwarded-Proto: https`). Plain HTTP returns **400** `tls_required`.
- On downstream **401** from OvalEdge APIs, the in-memory cache entry for that credential key is dropped; the MCP client should **retry the same request** (headers unchanged) so the next call re-exchanges.
- Tunables: `CREDENTIALS_CACHE_MAX_ENTRIES` (see `server/config.py` / `.env.example`).

**Implementation files:** `server/auth/middleware.py`, `server/auth/credentials_cache.py`, `server/auth/token_exchange.py` (`exchange_user_credentials`, `get_or_refresh_user_token`), `server/auth/context.py`, `server/client.py` (`_send_with_401_handling`), `server/constants.py`.

## Entrypoint and deployment

- **App:** `entrypoints/lambda_handler.py` — `app` is shared; full OAuth routers are included **only** when `settings.auth_mode == "remote"`. `remote_credentials` adds `server/auth/remote_credentials_discovery.py` only.
- **`MCP_HTTP_STATELESS`:** default **true** (good for Lambda). For **Cursor** (and similar) over plain HTTP, set **`MCP_HTTP_STATELESS=false`** so the MCP stack registers **GET** on `/mcp` for SSE fallback after Streamable HTTP negotiation. Without this, clients may get wrong `Content-Type` on GET.
- **Lambda / SAM:** [infra/template.yaml](infra/template.yaml) — `AuthMode` parameter (`remote` | `remote_credentials`), CORS allows the OvalEdge header names, optional empty defaults for `OAuthIssuer` / `OAuthAudience` when using credentials-only stacks.
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

## Validation script

From repo root:

```bash
poetry run python scripts/validate_remote_mcp.py --settings
poetry run python scripts/validate_remote_mcp.py --credentials   # needs OvalEdge user token+secret
poetry run python scripts/validate_remote_mcp.py --all --token "$OAUTH_TEST_ACCESS_TOKEN"   # OAuth remote path
```

See script docstring for flags (`--discovery`, `--ovaledge`, `--mcp`, etc.).

## Security (remote)

- **`remote_credentials`:** long-lived OvalEdge credentials travel in **headers** — terminate TLS at the edge (API Gateway, ALB); never log header values.
- **`remote`:** treat IdP tokens like secrets in transit; configure `OAUTH_AUDIENCE` / issuer discovery carefully once OAuth is out of WIP.

## Layout (remote-relevant paths)

- `entrypoints/lambda_handler.py` — HTTP app + Mangum handler
- `server/auth/middleware.py` — mode branches
- `server/auth/metadata.py`, `server/auth/registration.py` — OAuth `remote` only
- `server/auth/remote_credentials_discovery.py` — `remote_credentials` only (well-known stubs + declined)
- `infra/template.yaml` — sample deploy
