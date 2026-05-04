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

Help:

```bash
./scripts/deploy.sh --help
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
