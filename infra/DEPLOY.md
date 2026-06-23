# Deploy to AWS (Lambda + HTTP API)

Prerequisites: [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html), Docker running, IAM permission to create/update the stack, ECR, and Lambda.

**Credentials:** The deploy script does **not** run login or prompt for keys. Configure the AWS CLI first, for example `aws configure` (access key ID + secret access key in `~/.aws/credentials`) or `aws sso login` and `export AWS_PROFILE=your-profile`. The same identity is used for ECR, CloudFormation, and S3 (`--resolve-s3`).

**Mangum + Streamable HTTP:** The Lambda entrypoint uses `Mangum(..., lifespan="off")` and pins FastMCP’s `mcp_http` lifespan on a background task. Default Mangum `lifespan=auto` runs full ASGI startup/shutdown **every** invocation, which exits `StreamableHTTPSessionManager.run()` and causes `RuntimeError: ... can only be called once per instance` on the next request (500 from API Gateway). See `entrypoints/lambda_handler.py`.

**GitHub Actions deploy (`.github/workflows/ci.yml`):** Configure repository secret **`OVALEDGE_BASE_URL`** (required). Optional repo variables: **`SAM_AUTH_MODE`** (default `remote_credentials`), **`SAM_ENVIRONMENT`** (default `prod`).

**CloudWatch log retention:** The SAM template does not declare a `LogGroup` (avoids conflicts with log groups Lambda already created). Set retention in the console or extend the template once per environment.

## One-shot (recommended)

From the **repository root**:

```bash
export OVALEDGE_BASE_URL=https://your-oval-edge-host.example.com
./scripts/deploy.sh
```

Optional tuning (same shell, before `./scripts/deploy.sh`):

```bash
export STACK_NAME=oe-mcp-prod
export AWS_REGION=ap-south-1
export AUTH_MODE=remote_credentials   # or remote
export ENVIRONMENT=prod
export MCP_HTTP_STATELESS=true        # false if your MCP client needs GET/SSE
```

First run creates the **ECR** repository `oe-mcp` (override with `ECR_REPO`) if it does not exist. The script runs `sam build` then `sam deploy` with `--resolve-s3` and prints **CloudFormation outputs** (including `MCPEndpointUrl`).

## Lambda ZIP (no container image / no ECR)

Same HTTP API, routes, env vars, and handler as the image stack, but the function is packaged as a **Python 3.12 ZIP** built by SAM (`BuildMethod: python3.12`). Use this when you do not want ECR or a Dockerfile build.

From the repository root:

```bash
export OVALEDGE_BASE_URL=https://your-oval-edge-host.example.com
./scripts/deploy-zip.sh
```

Template: [template-zip.yaml](template-zip.yaml). Runtime dependencies are listed in [lambda-requirements.txt](lambda-requirements.txt); the repo root [requirements.txt](../requirements.txt) includes that file for SAM’s default pip manifest.

- **Native build (default):** `sam build --no-use-container` — no Docker required; suitable on many Linux CI hosts.
- **Containerized pip (optional):** `SAM_USE_CONTAINER=true ./scripts/deploy-zip.sh` — uses Docker so wheels match Amazon Linux (useful on macOS if native install fails).

Updating the same stack from **image → ZIP** (or the reverse) is a CloudFormation change to `PackageType`; prefer a new `STACK_NAME` or plan a one-time stack update.

**ZIP template physical names:** `infra/template-zip.yaml` names the Lambda and HTTP API as ``{StackName}-{Environment}-lambda`` and ``{StackName}-{Environment}-httpapi`` so a second stack (e.g. `oe-mcp-zip`) does not collide with the image stack’s fixed names (`oe-mcp-{Environment}`, `oe-mcp-api-{Environment}`).

Help:

```bash
./scripts/deploy.sh --help
```

## Uninstall (stack + optional ECR)

From repo root:

```bash
./scripts/uninstall.sh
```

Useful options:

```bash
./scripts/uninstall.sh --yes          # non-interactive
./scripts/uninstall.sh --keep-ecr     # remove stack only, keep container images
```

## Manual SAM (same result)

```bash
export AWS_REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export IMAGE_REPOSITORY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/oe-mcp"
# create repo once if needed:
# aws ecr create-repository --repository-name oe-mcp --region "$AWS_REGION"

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

sam build -t infra/template.yaml --use-container
sam deploy -t .aws-sam/build/template.yaml \
  --stack-name oe-mcp \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --image-repository "$IMAGE_REPOSITORY" \
  --parameter-overrides AuthMode=remote_credentials OvalEdgeBaseUrl="$OVALEDGE_BASE_URL" Environment=dev
```

Template parameters are defined in [template.yaml](template.yaml).

## Lambda architecture (`x86_64` vs `arm64`)

SAM’s Docker build targets the **same architecture** as the Lambda resource. The template defaults to **`x86_64`** so typical laptops and **GitHub Actions `ubuntu-latest`** (amd64) match without `docker buildx`.

For **Graviton (`arm64`)** images, deploy with:

```bash
export LAMBDA_ARCHITECTURE=arm64
```

and build on an **arm64** machine or use **buildx** with `--platform linux/arm64` (see AWS docs for cross-arch Lambda images).

## Docker build: `digest … not found` / `failed to read config content`

Usually a **stale BuildKit or SAM cache** pointing at an old layer blob, or a **pulled-then-pruned** Lambda base image.

From repo root, try in order:

```bash
docker pull public.ecr.aws/lambda/python:3.12
rm -rf .aws-sam/cache
export SAM_BUILD_NO_CACHED=true
./scripts/deploy.sh
```

If it still fails, build **without** the SAM container sandbox (works on many Linux hosts; matches Lambda glibc closely enough for pure-Python wheels):

```bash
export SAM_USE_CONTAINER=false
export SAM_BUILD_NO_CACHED=true
./scripts/deploy.sh
```

Last resort: `docker builder prune -af` (removes **all** build cache on the machine) then rerun `./scripts/deploy.sh`.

## After deploy

- Use output **`MCPEndpointUrl`** as the MCP HTTP base (ends with `/mcp`).
- HTTP API has **no gateway authorizer** in this template; **`AuthMiddleware`** enforces credentials or Bearer tokens on the function.
- For production hardening, consider WAF, throttling, or an HTTP API JWT authorizer in addition to app auth.

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
   Example: `https://ajh08u6ci3.execute-api.ap-south-1.amazonaws.com`
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
./scripts/deploy-zip.sh
```

Then set **`MCP_PUBLIC_BASE_URL`** from output **`MCPPublicBaseUrl`**, or your custom domain after step 4.

## Troubleshooting remote MCP

502/500 on `POST /mcp`, stale API URLs, CloudWatch queries, and a **redeploy checklist**: [TROUBLESHOOTING_REMOTE.md](TROUBLESHOOTING_REMOTE.md).

