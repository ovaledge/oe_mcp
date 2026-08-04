# Remote MCP (HTTP)

Run the same MCP tools over **HTTP** with FastAPI + Mangum (`entrypoints/lambda_handler.py`). Auth is selected with **`AUTH_MODE`** at process startup (Lambda environment, SAM template, or `.env` when using uvicorn).

← [Back to main README](README.md) · [Local MCP (stdio)](README_LOCAL_MCP.md)

## Auth modes

| `AUTH_MODE` | Client credentials | OAuth / discovery routes | Notes |
| ------------- | -------------------- | -------------------------- | ----- |
| `remote` | `Authorization: Bearer` + Okta/OIDC access token | Full discovery + `POST /register` | **Okta Connect** — validate token, forward Bearer to OvalEdge |
| `remote_credentials` | `X-OvalEdge-Credentials` (`token::secret`) **or** `X-OvalEdge-Token` + `X-OvalEdge-Secret` | Minimal `/.well-known/*` stubs (no browser OAuth) | Per-user OvalEdge JWT cached server-side; use **HTTPS** |

Shared: `POST /mcp` (streamable HTTP), `GET /health`, `GET /`.

All variables are documented in [.env.example](.env.example).

## `AUTH_MODE=remote` (Okta / OIDC Connect)

Use for remote deployments where OvalEdge APIs are an **OAuth2 resource server** (Okta opaque introspect), as in typical `oasis.properties` (`spring.security.oauth2.baseurl` + `api.introspection.uri`).

### Flow

1. MCP client **Connect** → discovers AS metadata from this server (proxied from Okta).
2. `POST /register` returns your pre-registered **`OAUTH_CLIENT_ID`** (not a random id).
3. Browser authorize/token happen on **Okta** (`OAUTH_ISSUER`).
4. Client calls `POST /mcp` with `Authorization: Bearer <access_token>`.
5. MCP validates the token (**JWT via JWKS** or **opaque via introspect**).
6. MCP forwards the same Bearer token to OvalEdge APIs (`OVALEDGE_REMOTE_FORWARD_IDP_TOKEN=true`, default).
7. OvalEdge introspects the token and maps the principal to an **existing OvalEdge user** (email/username) and that user’s roles/ACL.

**There is no hop through `/api/user/token/generate` in this path.** That endpoint is for OvalEdge userToken+secret → internal JWT (`local` / `remote_credentials`). Stock OvalEdge **cannot** turn an Okta access token into an OE JWT via `token/generate` (it decrypts `userToken` as an OvalEdge credential). Forwarding the Okta Bearer token is the correct path when the pod runs the **`oauth2`** Spring profile.

### OvalEdge must accept Okta Bearer tokens

For tools to work after Connect, the OvalEdge pod must:

1. Run with **`spring.profiles.active` containing `oauth2`** (enables opaque-token resource server on `/api/**`).
2. Have `api.introspection.uri` = `{OAUTH_ISSUER}/v1/introspect` (same AS Cursor/MCP use).
3. Have `api.clientid` / `api.clientsecret` able to call that introspect endpoint (often same as the OIDC app).
4. Map the Okta principal (usually **email**) to an **existing** OvalEdge user (`CustomAuthoritiesOpaqueTokenIntrospector`).

If the pod is **JWT-only** (no `oauth2` profile), `Authorization: Bearer <Okta token>` is ignored and Spring returns *Full authentication is required* — that is an OvalEdge deployment issue, not fixed by flipping `OVALEDGE_REMOTE_FORWARD_IDP_TOKEN`.

**Verify on the pod** (replace URL/token):

```bash
# Should be 200 (or a JSON API body), not 401, when oauth2 is correctly enabled:
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $OKTA_ACCESS_TOKEN" \
  -H "Accept: application/json" \
  "http://rohit-mcp-testing.ovaledge.net:8080/ovaledge/api/user/getUser"
```

If that curl is 401, fix OvalEdge/oauth2 first; MCP cannot work around it while forwarding.

### Operator setup

1. Okta OIDC app with **Authorization Code + PKCE**; set `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` (secret used for token introspection and confidential token exchange). Prefer a dedicated MCP app rather than reusing the OvalEdge web login app.
2. Register **Sign-in redirect URIs** for every MCP client you use — see [Okta redirect URIs (all clients)](#okta-redirect-uris-all-clients).
3. `OAUTH_ISSUER` = Okta AS base (e.g. `https://….okta.com/oauth2/default`).
4. `OAUTH_INTROSPECTION_URL` optional — defaults to `{OAUTH_ISSUER}/v1/introspect`. Must match OvalEdge `api.introspection.uri` (same Okta org + client that can introspect).
5. `OVALEDGE_BASE_URL` — OvalEdge tenant reachable from the MCP host/Lambda (API only; login UI is not the OAuth AS).
6. `MCP_PUBLIC_BASE_URL` — public HTTPS base of this MCP server (set after Lambda deploy from stack output `MCPPublicBaseUrl`).
7. Users who Connect must already exist in OvalEdge with a matching email/username.

**Run locally / on a VM:**

```bash
./scripts/run_remote_oauth_mcp_http.sh
```

**Deploy AWS Lambda (ZIP — no Docker/ECR):** see [Lambda ZIP Okta Connect](#lambda-zip-okta-connect-auth_moderremote) below, or [infra/DEPLOY.md](infra/DEPLOY.md#okta-connect-lambda-zip).

**Deploy AWS Lambda (container image):** same env vars with `./scripts/deploy.sh` (no `--zip`).

**Deploy ECS Fargate:** `AUTH_MODE=remote` + OAuth env via [`scripts/deploy_ecs.sh`](scripts/deploy_ecs.sh) — [infra/DEPLOY.md](infra/DEPLOY.md#aws-ecs-fargate--alb).

### Okta redirect URIs (all clients)

In Okta Admin → your OIDC app → **General** → **Sign-in redirect URIs**, add every client you support. Missing URIs produce: *The 'redirect_uri' parameter must be a Login redirect URI in the client app settings*.

Okta (strict mode) requires an **exact** URI match, including loopback **port**. Prefer the **fixed ports** below over ephemeral ports.

| Client | Redirect URI(s) | Notes |
|--------|-----------------|-------|
| **Cursor** (desktop) | `http://localhost:8787/callback` | Default Cursor loopback |
| **Cursor** (desktop fallback) | `cursor://anysphere.cursor-mcp/oauth/callback` | Custom scheme |
| **Cursor** (web / Agents) | `https://www.cursor.com/agents/mcp/oauth/callback` | Cursor Agents / web |
| **Claude.ai / Desktop / mobile** | `https://claude.ai/api/mcp/auth_callback` | Hosted Claude Connect |
| **Claude Code** (CLI) | `http://localhost:8788/callback` and `http://127.0.0.1:8788/callback` | Pass `--callback-port 8788` |
| **GitHub Copilot / VS Code** | `http://localhost:8790/callback` and `http://127.0.0.1:8790/callback` | Set `oauth.callbackPort: 8790` in `.vscode/mcp.json` |
| **Microsoft Copilot Studio** | Wizard-issued URL (often `https://global.consent.azure-apim.net/redirect/<slug>`) | **Do not invent the slug** — copy the full callback URL after creating the MCP tool with OAuth, or from a `redirect_uri` mismatch error. Slug changes if you rename the tool. See [SETUP_MICROSOFT_COPILOT.md](docs/client-setup/SETUP_MICROSOFT_COPILOT.md#redirect-url--you-do-not-invent-the-slug) |
| **Microsoft Copilot Studio** (common extras) | `https://token.botframework.com/.auth/web/redirect`, `https://europe.token.botframework.com/.auth/web/redirect`, `https://copilotstudio.microsoft.com/auth/callback` | Pre-add these; then add the wizard-issued `azure-apim.net` URL |

**Recommended allowlist (IDE clients — copy-paste):**

```text
http://localhost:8787/callback
https://www.cursor.com/agents/mcp/oauth/callback
cursor://anysphere.cursor-mcp/oauth/callback
https://claude.ai/api/mcp/auth_callback
http://localhost:8788/callback
http://127.0.0.1:8788/callback
http://localhost:8790/callback
http://127.0.0.1:8790/callback
```

Then add any **Microsoft Copilot Studio** redirect URLs the wizard shows (per environment / tool name).

| Client guide | Section |
|--------------|---------|
| Cursor | [SETUP_CURSOR.md](docs/client-setup/SETUP_CURSOR.md#remote-oauth-auth_moderremote) |
| Claude | [SETUP_CLAUDE.md](docs/client-setup/SETUP_CLAUDE.md#remote-oauth-auth_moderremote) |
| GitHub Copilot (VS Code) | [SETUP_VSCODE_GITHUB_COPILOT.md](docs/client-setup/SETUP_VSCODE_GITHUB_COPILOT.md#remote-oauth-auth_moderremote) |
| Microsoft Copilot Studio | [SETUP_MICROSOFT_COPILOT.md](docs/client-setup/SETUP_MICROSOFT_COPILOT.md#remote-oauth-auth_moderremote) |

### Confidential Okta apps (client secret)

OvalEdge’s default Okta **Web** app is **confidential**. MCP clients must **not** put `CLIENT_ID` / `CLIENT_SECRET` in editor `mcp.json` files.

Keep secrets on the **server** only:

1. Set `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` on Lambda / ECS / host env.
2. Redeploy — `POST /register` returns that client id (and secret when configured) so Connect can complete token exchange.
3. Editor config stays URL-only (Cursor / Claude Code / VS Code without embedding the secret).

**Microsoft Copilot Studio** is different: the Studio wizard may ask for Client ID/Secret in the **Power Platform connection** UI (maker-side). That is not the same as putting secrets in `mcp.json`. Prefer **API key** + `remote_credentials` for Studio when possible; see [SETUP_MICROSOFT_COPILOT.md](docs/client-setup/SETUP_MICROSOFT_COPILOT.md).

**Preferred long-term:** Okta **Native** or **SPA** app (PKCE, public client) for IDE Connect; use `OAUTH_CLIENT_SECRET` on the server for **introspection**.

### Client config (Connect — no token headers)

**Cursor** `mcp.json`:

```json
{
  "mcpServers": {
    "ovaledge-remote-oauth": {
      "url": "https://YOUR_MCP_HOST/mcp"
    }
  }
}
```

**Claude Code** (fixed callback port matching Okta):

```bash
claude mcp add --transport http --callback-port 8788 ovaledge-remote-oauth \
  https://YOUR_MCP_HOST/mcp
```

**Claude.ai / Desktop:** add the connector URL `https://YOUR_MCP_HOST/mcp` and complete Connect in the browser (callback is `https://claude.ai/api/mcp/auth_callback`).

**VS Code + GitHub Copilot** (`.vscode/mcp.json` — fixed loopback port **8790**):

```json
{
  "servers": {
    "ovaledge-remote-oauth": {
      "type": "http",
      "url": "https://YOUR_MCP_HOST/mcp",
      "oauth": {
        "callbackPort": 8790
      }
    }
  }
}
```

If your VS Code build requires `oauth.clientId`, set it to the same `OAUTH_CLIENT_ID` as the server (still **no** client secret in the file — confidential exchange is handled via `/register` / server env).

**Microsoft Copilot Studio:** see [SETUP_MICROSOFT_COPILOT.md](docs/client-setup/SETUP_MICROSOFT_COPILOT.md#remote-oauth-auth_moderremote) (wizard + Okta redirect from Studio).

**Modules:** `server/auth/bearer_jwt.py`, `server/auth/oauth_discovery.py`, `server/auth/metadata.py`, `server/auth/registration.py`, `server/auth/middleware.py`, `server/client.py`.

### Lambda ZIP Okta Connect (`AUTH_MODE=remote`)

Prerequisites: AWS CLI + SAM CLI; OvalEdge reachable from Lambda with `oauth2` + matching `api.introspection.*`; Okta redirect URIs registered.

```bash
export STACK_NAME=oe-mcp-oauth-zip          # unique stack name
export ENVIRONMENT=dev
export AWS_REGION=ap-south-1

export AUTH_MODE=remote
export OVALEDGE_BASE_URL=https://YOUR_OE_HOST/ovaledge   # reachable from Lambda (not 127.0.0.1)

export OAUTH_ISSUER=https://YOUR_OKTA_ORG.okta.com/oauth2/default
export OAUTH_CLIENT_ID=0oa...
export OAUTH_CLIENT_SECRET='...'            # Okta app secret (same family as OE api.clientsecret)
export OAUTH_INTROSPECTION_URL=https://YOUR_OKTA_ORG.okta.com/oauth2/default/v1/introspect
export OAUTH_SCOPES="openid profile email"  # quote spaces
export OAUTH_AUDIENCE=                      # leave empty for Okta default AS / opaque

export OVALEDGE_REMOTE_FORWARD_IDP_TOKEN=true
export MCP_HTTP_STATELESS=true

./scripts/deploy.sh --zip
```

After deploy:

1. Copy stack outputs **`MCPEndpointUrl`** and **`MCPPublicBaseUrl`**.
2. Set Lambda env **`MCP_PUBLIC_BASE_URL`** = `MCPPublicBaseUrl` (no `/mcp`).
3. Smoke-test: `curl -sS "$MCPPublicBaseUrl/health"` → `"auth_mode":"remote"`.
4. Point clients at **`MCPEndpointUrl`** (must end with `/mcp`).

macOS tip: `SAM_USE_CONTAINER=true ./scripts/deploy.sh --zip` if native wheels fail.

Full matrix: [infra/DEPLOY.md](infra/DEPLOY.md#okta-connect-lambda-zip). Troubleshooting: [infra/TROUBLESHOOTING_REMOTE.md](infra/TROUBLESHOOTING_REMOTE.md#okta-connect-auth_moderremote).

### Legacy exchange mode

Set `OVALEDGE_REMOTE_FORWARD_IDP_TOKEN=false` only if your OvalEdge build expects an exchanged OvalEdge JWT instead of the IdP Bearer. **Not** used for stock Okta opaque resource-server pods — `token/generate` cannot exchange Okta→OE JWT.

## `remote_credentials` (header auth)

- Middleware reads **`X-OvalEdge-Credentials`** (`token::secret`) **or** **`X-OvalEdge-Token`** + **`X-OvalEdge-Secret`**, exchanges with OvalEdge, caches JWTs keyed by a digest of token+secret, sets `current_oe_jwt` and `current_oe_credential_cache_key` for the request. OvalEdge issuance does not include `::` in token or secret.
- **HTTPS** is enforced for protected routes (`request.url.scheme` or `X-Forwarded-Proto: https`). Plain HTTP returns **400** `tls_required`.
- On downstream **401** from OvalEdge APIs, the in-memory cache entry for that credential key is dropped; the MCP client should **retry the same request** (headers unchanged) so the next call re-exchanges.
- Tunables: `CREDENTIALS_CACHE_MAX_ENTRIES` (see `server/config.py` / `.env.example`).

**Implementation files:** `server/auth/middleware.py`, `server/auth/credentials_cache.py`, `server/auth/token_exchange.py` (`exchange_user_credentials`, `get_or_refresh_user_token`), `server/auth/context.py`, `server/client.py` (`_send_with_401_handling`), `server/constants.py`.

## Entrypoint and deployment

- **App:** `entrypoints/lambda_handler.py` — `app` is shared; full OAuth routers are included **only** when `settings.auth_mode == "remote"`. `remote_credentials` adds `server/auth/remote_credentials_discovery.py` only.
- **Local HTTP (dev):** `./scripts/run_local_mcp_http.sh` or `poetry run oe-mcp-http` — forces **`AUTH_MODE=local`** (cached JWT at startup; credentials in `.env`; see [README_LOCAL_MCP.md](README_LOCAL_MCP.md#runtime-architecture)). Pair with **`ovaledge-local-http`** in Cursor `mcp.json`.
- **Remote host HTTP (EC2/VM) — credentials headers:** `./scripts/run_remote_mcp_http.sh` — forces **`AUTH_MODE=remote_credentials`**.
- **Remote host HTTP — Okta Connect:** `./scripts/run_remote_oauth_mcp_http.sh` — forces **`AUTH_MODE=remote`**.
- **ECS Fargate + ALB:** `./scripts/deploy_ecs.sh` — set `AUTH_MODE=remote` and OAuth env vars. Guide: [infra/DEPLOY.md](infra/DEPLOY.md#aws-ecs-fargate--alb).
- **Lambda ZIP Okta Connect:** `AUTH_MODE=remote ./scripts/deploy.sh --zip` — [infra/DEPLOY.md](infra/DEPLOY.md#okta-connect-lambda-zip) · [redirect URIs](#okta-redirect-uris-all-clients).
- **`MCP_HTTP_STATELESS`:** default **true** (good for Lambda). For **Cursor** over plain HTTP, set **`MCP_HTTP_STATELESS=false`**.
- **Observability:** optional OTLP to Phoenix or Langfuse — [infra/DEPLOY.md](infra/DEPLOY.md#telemetry-opentelemetry).
- **Lambda / SAM:** [infra/template.yaml](infra/template.yaml) — `AuthMode` `remote` | `remote_credentials`. ZIP: [infra/template-zip.yaml](infra/template-zip.yaml) via [`scripts/deploy.sh --zip`](scripts/deploy.sh). See [infra/DEPLOY.md](infra/DEPLOY.md).
- **Troubleshooting:** [infra/TROUBLESHOOTING_REMOTE.md](infra/TROUBLESHOOTING_REMOTE.md).

```bash
./scripts/run_local_mcp_http.sh
# or:
export AUTH_MODE=local
export MCP_HTTP_STATELESS=false
poetry run uvicorn entrypoints.lambda_handler:app --host 127.0.0.1 --port 8000
```

For deployed-style header auth on localhost, use `AUTH_MODE=remote_credentials` (see below).

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
poetry run uvicorn entrypoints.lambda_handler:app --host 127.0.0.1 --port 8000
```

**3. Client headers** — see [.cursor/mcp.json.example](.cursor/mcp.json.example) (`ovaledge-remote-http`).

## Security (remote)

- **`remote`:** terminate TLS at the edge; do not log Bearer tokens. Users must exist in OvalEdge for introspect mapping.
- **`remote_credentials`:** long-lived OvalEdge credentials travel in **headers** — terminate TLS at the edge; never log header values.

## Validation

```bash
poetry run pytest tests/auth/test_oauth_discovery.py tests/auth/test_oauth_bearer.py \
  tests/auth/test_oauth_metadata_route.py tests/auth/test_registration.py \
  tests/auth/test_middleware.py -q

poetry run python scripts/validate_remote_mcp.py --all --token "$OAUTH_TEST_ACCESS_TOKEN"
```

## Related source

- `server/auth/remote_credentials_discovery.py` — `remote_credentials` only (well-known stubs)
- `server/auth/metadata.py` / `registration.py` — `remote` only
