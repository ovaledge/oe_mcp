# Deploy OvalEdge MCP

How to run **oe_mcp** for clients (Cursor, Claude, etc.). Pick a path from the matrix below.

## Deployment options

| Option | Where it runs | Auth | Credentials | Script / entry |
|--------|---------------|------|-------------|----------------|
| **Local stdio** | Laptop (Cursor subprocess) | `AUTH_MODE=local` | `.env` or mcp.json `env` | `poetry run oe-mcp-local` — [README_LOCAL_MCP.md](../README_LOCAL_MCP.md) |
| **Local HTTP** | Laptop uvicorn (`127.0.0.1`) | `AUTH_MODE=local` | Server `.env` (JWT at startup) | [`scripts/run_local_mcp_http.sh`](../scripts/run_local_mcp_http.sh) |
| **Remote host HTTP** | EC2 / VM uvicorn (`0.0.0.0`) | `AUTH_MODE=remote_credentials` | **mcp.json headers** (not on server) | [`scripts/run_remote_mcp_http.sh`](../scripts/run_remote_mcp_http.sh) — [below](#remote-host-http-ec2--vm) |
| **AWS Lambda (container)** | API Gateway + Lambda image | `remote_credentials` (default) or `remote` (OAuth WIP) | Client headers / Bearer | [`scripts/deploy.sh`](../scripts/deploy.sh) — default |
| **AWS Lambda (ZIP)** | API Gateway + Lambda ZIP | same | same | `./scripts/deploy.sh --zip` |

**Client setup:** [docs/client-setup/README.md](../docs/client-setup/README.md) · Cursor snippets: [.cursor/mcp.json.example](../.cursor/mcp.json.example)

**Remote auth / TLS / laptop testing:** [README_REMOTE_MCP.md](../README_REMOTE_MCP.md) · Troubleshooting: [TROUBLESHOOTING_REMOTE.md](TROUBLESHOOTING_REMOTE.md)

---

## Remote host HTTP (EC2 / VM)

Use when you want a long-lived HTTP MCP on a server **without** Lambda. Clients send OvalEdge token+secret in **mcp.json headers**; the server `.env` needs only **`OVALEDGE_BASE_URL`**.

### Server setup

```bash
cd /path/to/oe_mcp
poetry install
# .env must include OVALEDGE_BASE_URL=https://your-ovaledge-host
# Do NOT put OVALEDGE_USER_TOKEN / OVALEDGE_USER_SECRET on the server for this mode

./scripts/run_remote_mcp_http.sh          # starts detached (nohup); survives SSH disconnect
./scripts/run_remote_mcp_http.sh --status
./scripts/run_remote_mcp_http.sh --stop
```

Optional env: `HOST` (default `0.0.0.0`), `PORT` (default `8000`), `MCP_PUBLIC_BASE_URL` (URL clients use).

Logs: `/tmp/oe-mcp-remote-http.log` · PID: `/tmp/oe-mcp-remote-http.pid`

Open **port 8000** (or your `PORT`) in the security group / firewall. Prefer a TLS reverse proxy (nginx/Caddy) in production.

### Cursor mcp.json

```json
{
  "mcpServers": {
    "ovaledge-remote-http": {
      "url": "http://YOUR_HOST_OR_IP:8000/mcp",
      "headers": {
        "X-Forwarded-Proto": "https",
        "X-OvalEdge-Token": "${env:OVALEDGE_USER_TOKEN}",
        "X-OvalEdge-Secret": "${env:OVALEDGE_USER_SECRET}"
      }
    }
  }
}
```

`X-Forwarded-Proto: https` is required when the client URL is plain `http://` (app TLS check). With real HTTPS at the proxy, you can omit that spoof.

Foreground debug: `./scripts/run_remote_mcp_http.sh --foreground`

---

## AWS Lambda + HTTP API

Guide for deploying **oe_mcp** to AWS Lambda behind API Gateway HTTP API.

**Two SAM templates, one script:**

| Artifact | Purpose |
|----------|---------|
| [template.yaml](template.yaml) | Lambda **container image** (ECR + Dockerfile) — default |
| [template-zip.yaml](template-zip.yaml) | Lambda **ZIP** (no Docker/ECR at deploy time) |
| [../scripts/deploy.sh](../scripts/deploy.sh) | Unified build + deploy with optional `--zip`, `--waf` |

Related docs: [TROUBLESHOOTING_REMOTE.md](TROUBLESHOOTING_REMOTE.md).

## Prerequisites

- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured (`aws configure`, SSO, or `AWS_PROFILE`)
- [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- **Container deploy (default):** Docker running
- IAM permissions for CloudFormation, Lambda, API Gateway, S3 (`--resolve-s3`), and ECR
- **`OVALEDGE_BASE_URL`** — your OvalEdge tenant origin (no trailing slash)

The deploy script does not prompt for credentials; configure AWS CLI before running.

**Mangum + Streamable HTTP:** The Lambda entrypoint uses `Mangum(..., lifespan="off")` and pins FastMCP’s `mcp_http` lifespan on a background task. Default Mangum `lifespan=auto` runs full ASGI startup/shutdown **every** invocation, which exits `StreamableHTTPSessionManager.run()` and causes `RuntimeError: ... can only be called once per instance` on the next request (500 from API Gateway). See `entrypoints/lambda_handler.py`.

**GitHub Actions deploy (`.github/workflows/ci.yml`):** Configure repository secret **`OVALEDGE_BASE_URL`**. Optional repo variables: **`SAM_AUTH_MODE`**, **`SAM_ENVIRONMENT`**.

**CloudWatch log retention:** The SAM template does not declare a `LogGroup` (avoids conflicts with log groups Lambda already created). Set retention in the console or extend the template once per environment.

## Quick start (container image)

From the repository root:

```bash
export OVALEDGE_BASE_URL=https://your-oval-edge-host.example.com
./scripts/deploy.sh
```

First run creates ECR repository `oe-mcp` (override with `ECR_REPO`) if missing. The script prints CloudFormation outputs including **`MCPEndpointUrl`**.

### Common environment variables

```bash
export STACK_NAME=oe-mcp-prod
export AWS_REGION=ap-south-1
export AUTH_MODE=remote_credentials   # or remote (OAuth WIP)
export ENVIRONMENT=prod
export MCP_HTTP_STATELESS=true        # false if your MCP client needs GET/SSE on /mcp
```

CLI equivalents: `./scripts/deploy.sh --help`

## Deploy flag matrix

| Goal | Command |
|------|---------|
| Container image (default) | `./scripts/deploy.sh` |
| Lambda ZIP (no ECR) | `./scripts/deploy.sh --zip` |
| WAF IP allowlist | `./scripts/deploy.sh --waf --allowed-cidrs 203.0.113.0/24` |
| ZIP + WAF | `./scripts/deploy.sh --zip --waf --allowed-cidrs 10.0.0.0/8` |

WAF CIDRs can also be set via env: `export ALLOWED_SOURCE_CIDRS=203.0.113.0/24`

## Lambda ZIP (`--zip`)

Same HTTP API routes, handler, and auth as the image stack. SAM packages Python 3.12 dependencies into a ZIP artifact.

```bash
export OVALEDGE_BASE_URL=https://your-oval-edge-host.example.com
./scripts/deploy.sh --zip
```

- **Native build (default):** `sam build --no-use-container` — no Docker required; good for Linux CI.
- **Containerized pip:** `SAM_USE_CONTAINER=true ./scripts/deploy.sh --zip` — wheels match Amazon Linux (useful on macOS).
- **`deploy.sh` stages** `server/`, `entrypoints/`, and `requirements.txt` into a temp directory before `sam build` so `CodeUri` resolves correctly and dev artifacts (e.g. `.codegraph/`) are not packaged.

Runtime dependencies: [lambda-requirements.txt](lambda-requirements.txt) (also referenced from repo [requirements.txt](../requirements.txt)).

**Stack naming:** `template-zip.yaml` uses `{StackName}-{Environment}-lambda` and `{StackName}-{Environment}-httpapi` so a second stack (e.g. `oe-mcp-zip`) does not collide with the image stack.

Switching **image ↔ ZIP** on the same stack changes Lambda `PackageType`; prefer a new `STACK_NAME` or plan a deliberate stack update.

## WAF IP allowlist (`--waf`)

Both templates support optional **regional AWS WAF** via CloudFormation parameters `EnableWaf` and `AllowedSourceCidrs`.

**Behavior:**

- WAF **default action = block**
- Only IPv4 CIDRs in the allowlist reach Lambda (`/mcp`, `/health`, OAuth routes, etc.)
- Other clients receive **403** from WAF before application auth

```bash
export OVALEDGE_BASE_URL=https://your-oval-edge-host.example.com
export STACK_NAME=oe-mcp-waf
./scripts/deploy.sh --waf --allowed-cidrs 203.0.113.0/24,198.51.100.10/32
```

Stack outputs (when WAF enabled): **`WAFWebAclArn`**, **`WAFAllowedSourceCidrs`**.

**Caveats:**

- SaaS MCP clients (Cursor, Claude) often use **dynamic egress IPs** — WAF works best with a **fixed corporate egress** (proxy, ZTNA, VPN).
- WAF is regional and billed separately from Lambda/API Gateway.
- App-layer auth is still required for allowed IPs.

## SAM template parameters

Key parameters (full list in [template.yaml](template.yaml)):

| Parameter | Default | Notes |
|-----------|---------|-------|
| `AuthMode` | `remote_credentials` | `remote` for OAuth (WIP) |
| `OvalEdgeBaseUrl` | *(required)* | From `OVALEDGE_BASE_URL` |
| `Environment` | `dev` | Suffixes resource names |
| `McpHttpStateless` | `true` | Set `false` for GET/SSE clients |
| `LambdaArchitecture` | `x86_64` | `arm64` for Graviton |
| `EnableWaf` | `false` | Set via `--waf` |
| `AllowedSourceCidrs` | `127.0.0.1/32` | Ignored when WAF disabled |
| `TelemetryBackend` | `none` | `phoenix` or `langfuse` to enable OTLP export |
| `TelemetryServiceName` | `oe-mcp` | OTLP `service.name` |
| `TelemetryProjectName` | *(empty)* | Phoenix/Langfuse project routing; defaults to service name |
| `PhoenixHost` / `PhoenixApiKey` | *(empty)* | When `TelemetryBackend=phoenix` |
| `LangfuseHost` / keys | *(empty)* | When `TelemetryBackend=langfuse` (NoEcho in console) |

## Telemetry (OpenTelemetry)

The server can export MCP tool traces to **Phoenix** or **Langfuse** over OTLP HTTP. Default deploy: **disabled** (`TELEMETRY_BACKEND=none`).

### Enable at deploy time

Set env vars before `./scripts/deploy.sh` (passed as SAM parameter overrides):

```bash
export TELEMETRY_BACKEND=langfuse
export TELEMETRY_PROJECT_NAME=oe-mcp-prod
export LANGFUSE_HOST=https://langfuse.example.com
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
./scripts/deploy.sh
```

Phoenix example:

```bash
export TELEMETRY_BACKEND=phoenix
export TELEMETRY_PROJECT_NAME=oe-mcp-prod
export PHOENIX_HOST=https://phoenix.example.com
export PHOENIX_API_KEY=...   # when Phoenix auth is enabled
./scripts/deploy.sh
```

Equivalent SAM parameters: `TelemetryBackend`, `TelemetryProjectName`, `PhoenixHost`, `LangfuseHost`, etc. (see [template.yaml](template.yaml)). API keys use **NoEcho** in the CloudFormation console.

### After deploy

1. Confirm Lambda env shows `TELEMETRY_BACKEND` and backend host/keys (Console → Configuration → Environment variables).
2. Ensure the function can reach the OTLP endpoint (public HTTPS, VPC endpoint, or NAT as appropriate).
3. Invoke a tool; check Phoenix/Langfuse for `mcp.tool.*` spans.

### Privacy

Exported spans may include **tool argument summaries** (search terms, object ids). Do not enable export to a third-party backend without reviewing your data-classification policy. Credentials are not included in spans.

Variable reference for local dev: [.env.example](../.env.example). Troubleshooting: [TROUBLESHOOTING_REMOTE.md](TROUBLESHOOTING_REMOTE.md#otlp-telemetry-phoenix--langfuse).

## Manual SAM (equivalent to default container deploy)

```bash
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export IMAGE_REPOSITORY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/oe-mcp"

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

sam build -t infra/template.yaml --use-container
sam deploy -t .aws-sam/build/template.yaml \
  --stack-name oe-mcp \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --image-repository "$IMAGE_REPOSITORY" \
  --parameter-overrides AuthMode=remote_credentials OvalEdgeBaseUrl="$OVALEDGE_BASE_URL" Environment=dev
```

## GitHub Actions

Workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) deploys on push to `main` using `infra/template.yaml`. Configure secret **`OVALEDGE_BASE_URL`**. Optional variables: **`SAM_AUTH_MODE`**, **`SAM_ENVIRONMENT`**.

## Lambda architecture (`x86_64` vs `arm64`)

SAM’s Docker build targets the **same architecture** as the Lambda resource. The template defaults to **`x86_64`** so typical laptops and **GitHub Actions `ubuntu-latest`** (amd64) match without `docker buildx`.

For **Graviton (`arm64`)** images:

```bash
export LAMBDA_ARCHITECTURE=arm64
./scripts/deploy.sh
```

Build on an **arm64** machine or use **buildx** with `--platform linux/arm64`.

## Docker build: `digest … not found` / `failed to read config content`

Usually a **stale BuildKit or SAM cache** pointing at an old layer blob, or a **pulled-then-pruned** Lambda base image.

From repo root, try in order:

```bash
docker pull public.ecr.aws/lambda/python:3.12
rm -rf .aws-sam/cache
export SAM_BUILD_NO_CACHED=true
./scripts/deploy.sh
```

If it still fails, build **without** the SAM container sandbox:

```bash
export SAM_USE_CONTAINER=false
export SAM_BUILD_NO_CACHED=true
./scripts/deploy.sh
```

Last resort: `docker builder prune -af` then rerun `./scripts/deploy.sh`.

## After deploy

1. Use **`MCPEndpointUrl`** as the MCP HTTP base (ends with `/mcp`).
2. Set Lambda env **`MCP_PUBLIC_BASE_URL`** to output **`MCPPublicBaseUrl`** (host only, no `/mcp`) for MCP metadata icons.
3. Verify **`MCPBrandIconUrl`** returns 200 (`image/png`).
4. HTTP API has **no gateway authorizer**; **`AuthMiddleware`** enforces credentials or Bearer tokens on the function.
5. For production hardening, use `./scripts/deploy.sh --waf` or add throttling / JWT authorizer.
6. Optional: enable OTLP telemetry via deploy env or SAM parameters — [Telemetry (OpenTelemetry)](#telemetry-opentelemetry).

## MCP branding icon (`/brand/ovaledge-mcp-icon.png`)

Both [template.yaml](template.yaml) and [template-zip.yaml](template-zip.yaml) register:

```text
GET /brand/ovaledge-mcp-icon.png   →  server/static/ovaledge-mcp-icon.png (no auth)
```

Stack outputs:

| Output | Use |
|--------|-----|
| **`MCPBrandIconUrl`** | Verify in browser or `curl` (expect **200** `image/png`) |
| **`MCPPublicBaseUrl`** | Value for Lambda env **`MCP_PUBLIC_BASE_URL`** (host only, **no** `/mcp`) |

### Set `MCP_PUBLIC_BASE_URL` on Lambda (required for MCP metadata)

The SAM template **does not** set `MCP_PUBLIC_BASE_URL` automatically (CloudFormation circular dependency with the HTTP API). After deploy:

1. AWS Console → **Lambda** → your function → **Configuration** → **Environment variables**
2. Add **`MCP_PUBLIC_BASE_URL`** = stack output **`MCPPublicBaseUrl`**
3. Save (Lambda cold-starts with the new value)

MCP `initialize` will then advertise `serverInfo.icons` with that HTTPS URL. Toggle the MCP server off/on in Cursor after changing env vars.

### Why Cursor still shows the AWS logo on `execute-api` URLs

If **`MCPEndpointUrl`** uses `*.execute-api.*.amazonaws.com`, **Cursor often shows the AWS badge** from the hostname — even when **`MCPBrandIconUrl`** returns **200**. That is client UI behavior, not a missing route.

To show the **OvalEdge** icon in Cursor (or avoid the AWS badge), put a **custom hostname** in front of the same HTTP API (below) and use that host in both Lambda env and `mcp.json`.

## Custom domain (recommended for Cursor branding)

Use when you want `https://mcp.example.com/mcp` instead of `https://<api-id>.execute-api.<region>.amazonaws.com/mcp`.

**Prerequisites:** DNS control for your domain; ACM certificate in the **same region** as the API (e.g. `ap-south-1` for Mumbai).

### 1. ACM certificate

```bash
export AWS_REGION=ap-south-1   # must match API region
# Request a public cert for mcp.example.com (DNS validation in ACM console)
```

### 2. API Gateway custom domain (HTTP API)

In **API Gateway** → **Custom domain names** → **Create**:

| Field | Value |
|-------|--------|
| Domain name | `mcp.example.com` |
| API type | HTTP |
| Certificate | ACM cert from step 1 |

Create an **API mapping**:

| Field | Value |
|-------|--------|
| API | Your stack’s HTTP API (e.g. `oe-mcp-zip-dev-httpapi`) |
| Stage | `$default` |
| Path | *(leave empty)* |

Note the **API Gateway domain target** (e.g. `d-xxxxx.execute-api.ap-south-1.amazonaws.com`).

### 3. DNS

Add a **CNAME** (or alias per your DNS provider):

```text
mcp.example.com  →  <API Gateway domain target from step 2>
```

### 4. Lambda + Cursor

| Where | Set |
|-------|-----|
| Lambda env | `MCP_PUBLIC_BASE_URL=https://mcp.example.com` |
| Cursor `mcp.json` | `"url": "https://mcp.example.com/mcp"` |
| Headers | Same `X-OvalEdge-Token` / `X-OvalEdge-Secret` as before |

Verify:

```bash
curl -sS -I https://mcp.example.com/brand/ovaledge-mcp-icon.png
curl -sS https://mcp.example.com/health
```

### ZIP stack example (`ap-south-1`)

```bash
export OVALEDGE_BASE_URL=https://your-pod.ovaledge.cloud/ovaledge
export STACK_NAME=oe-mcp-zip
export AWS_REGION=ap-south-1
./scripts/deploy.sh --zip
```

Then set **`MCP_PUBLIC_BASE_URL`** from output **`MCPPublicBaseUrl`**, or your custom domain after step 4.

## Uninstall (stack + optional ECR)

[`scripts/uninstall.sh`](../scripts/uninstall.sh) deletes the CloudFormation stack. It works the same for every deploy mode (`deploy.sh`, `--zip`, `--waf`) — set **`STACK_NAME`** to the stack you created.

| Deploy command | Typical `STACK_NAME` | ECR cleanup |
|----------------|----------------------|-------------|
| `./scripts/deploy.sh` | `oe-mcp` (default) | Yes — deletes `oe-mcp` ECR repo by default |
| `./scripts/deploy.sh --zip` | `oe-mcp` or `oe-mcp-zip` | No — ZIP deploys do not use ECR |
| `./scripts/deploy.sh --waf …` | `oe-mcp-waf` | Yes (container image) |

From repo root:

```bash
# Default container stack
./scripts/uninstall.sh --yes

# Keep ECR images for a later redeploy
./scripts/uninstall.sh --yes --keep-ecr

# ZIP stack — skip ECR (or use --keep-ecr; same effect)
STACK_NAME=oe-mcp-zip ./scripts/uninstall.sh --zip --yes

# Custom stack name from deploy
STACK_NAME=oe-mcp-waf ./scripts/uninstall.sh --yes
```

If ECR cleanup runs but no repository exists (common after `--zip`), the script skips it and continues.

## Troubleshooting remote MCP

502/500 on `POST /mcp`, stale API URLs, CloudWatch queries, and a **redeploy checklist**: [TROUBLESHOOTING_REMOTE.md](TROUBLESHOOTING_REMOTE.md).
