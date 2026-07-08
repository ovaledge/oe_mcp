#!/usr/bin/env bash
# One-shot SAM build + CloudFormation deploy for OvalEdge MCP.
#
# Templates (infra/):
#   template.yaml      — Lambda container image (ECR) — default
#   template-zip.yaml  — Lambda ZIP (no ECR) — use --zip
#
# Optional flags on the same templates (WAF is a CloudFormation parameter):
#   --zip              ZIP package instead of container image
#   --waf              Enable regional AWS WAF IP allowlist on the HTTP API
#   --allowed-cidrs    Comma-separated IPv4 CIDRs (required with --waf)
#
# Required:
#   OVALEDGE_BASE_URL   OvalEdge tenant base URL (no trailing slash)
#
# See infra/DEPLOY.md for full guide.
#
set -euo pipefail

DEPLOY_ZIP=false
ENABLE_WAF=false
ALLOWED_SOURCE_CIDRS="${ALLOWED_SOURCE_CIDRS:-}"

usage() {
  cat <<'EOF'
One-shot Lambda deploy (SAM build + CloudFormation).

Required env:
  OVALEDGE_BASE_URL   e.g. https://tenant.example.com (no trailing slash)

Deploy mode (pick one package type):
  (default)           Container image → ECR (infra/template.yaml)
  --zip               Lambda ZIP, no ECR (infra/template-zip.yaml)

Optional hardening:
  --waf               Attach regional WAF IP allowlist (default action: block)
  --allowed-cidrs <list>  IPv4 CIDRs for WAF (required with --waf), e.g. 203.0.113.0/24,10.0.0.0/8

Optional env:
  STACK_NAME, AWS_REGION, AUTH_MODE, ENVIRONMENT, ECR_REPO, MCP_HTTP_STATELESS,
  OVALEDGE_HTTP_AUTH_SCHEME, CREDENTIALS_CACHE_MAX_ENTRIES,
  SAM_USE_CONTAINER, SAM_BUILD_NO_CACHED, SAM_SKIP_DOCKER_PULL_BASE,
  OE_MCP_SAM_BUILD_DIR, IMAGE_REPOSITORY, SAM_OAUTH_ISSUER, SAM_OAUTH_AUDIENCE, ALLOWED_SOURCE_CIDRS,
  LAMBDA_ARCHITECTURE, LAMBDA_MEMORY_SIZE, LAMBDA_TIMEOUT,
  TELEMETRY_BACKEND, TELEMETRY_SERVICE_NAME, TELEMETRY_PROJECT_NAME,
  PHOENIX_HOST, PHOENIX_API_KEY, LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY,
  TELEMETRY_OTLP_ENDPOINT, TELEMETRY_API_KEY

Optional CLI flags (override env for this invocation):
  --oval-edge-auth-scheme <scheme>
  --credentials-cache-max-entries <n>
  --mcp-http-stateless <true|false>
  --environment <dev|staging|prod>
  --auth-mode <remote|remote_credentials>

Examples:
  export OVALEDGE_BASE_URL=https://app.example.com
  ./scripts/deploy.sh

  ./scripts/deploy.sh --zip
  ./scripts/deploy.sh --waf --allowed-cidrs 203.0.113.0/24
  ./scripts/deploy.sh --zip --waf --allowed-cidrs 10.0.0.0/8
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h | --help)
      usage
      exit 0
      ;;
    --zip)
      DEPLOY_ZIP=true
      shift
      ;;
    --waf)
      ENABLE_WAF=true
      shift
      ;;
    --allowed-cidrs)
      ALLOWED_SOURCE_CIDRS="${2:-}"
      shift 2
      ;;
    --oval-edge-auth-scheme)
      OVALEDGE_HTTP_AUTH_SCHEME="${2:-}"
      shift 2
      ;;
    --credentials-cache-max-entries)
      CREDENTIALS_CACHE_MAX_ENTRIES="${2:-}"
      shift 2
      ;;
    --mcp-http-stateless)
      MCP_HTTP_STATELESS="${2:-}"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="${2:-}"
      shift 2
      ;;
    --auth-mode)
      AUTH_MODE="${2:-}"
      shift 2
      ;;
    *)
      echo "error: unknown argument: $1 (try --help)" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${OVALEDGE_BASE_URL:-}" ]]; then
  echo "error: set OVALEDGE_BASE_URL (see --help)" >&2
  exit 1
fi

if [[ "$ENABLE_WAF" == true && -z "$ALLOWED_SOURCE_CIDRS" ]]; then
  echo "error: --waf requires --allowed-cidrs or ALLOWED_SOURCE_CIDRS env" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STACK_NAME="${STACK_NAME:-oe-mcp}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="$AWS_REGION"
AUTH_MODE="${AUTH_MODE:-remote_credentials}"
OVALEDGE_HTTP_AUTH_SCHEME="${OVALEDGE_HTTP_AUTH_SCHEME:-jwt}"
CREDENTIALS_CACHE_MAX_ENTRIES="${CREDENTIALS_CACHE_MAX_ENTRIES:-10000}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
ECR_REPO="${ECR_REPO:-oe-mcp}"
MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-true}"
LAMBDA_ARCHITECTURE="${LAMBDA_ARCHITECTURE:-x86_64}"
LAMBDA_MEMORY_SIZE="${LAMBDA_MEMORY_SIZE:-1024}"
LAMBDA_TIMEOUT="${LAMBDA_TIMEOUT:-30}"
TELEMETRY_BACKEND="${TELEMETRY_BACKEND:-none}"
TELEMETRY_SERVICE_NAME="${TELEMETRY_SERVICE_NAME:-oe-mcp}"
TELEMETRY_PROJECT_NAME="${TELEMETRY_PROJECT_NAME:-}"
PHOENIX_HOST="${PHOENIX_HOST:-}"
PHOENIX_API_KEY="${PHOENIX_API_KEY:-}"
LANGFUSE_HOST="${LANGFUSE_HOST:-}"
LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-}"
LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-}"
TELEMETRY_OTLP_ENDPOINT="${TELEMETRY_OTLP_ENDPOINT:-}"
TELEMETRY_API_KEY="${TELEMETRY_API_KEY:-}"

read_mcp_server_version() {
  if [[ -n "${MCP_SERVER_VERSION:-}" ]]; then
    echo "$MCP_SERVER_VERSION"
    return 0
  fi
  if command -v poetry >/dev/null 2>&1; then
    local from_poetry
    from_poetry="$(poetry version -s 2>/dev/null || true)"
    if [[ -n "$from_poetry" ]]; then
      echo "$from_poetry"
      return 0
    fi
  fi
  local from_toml
  from_toml="$(
    grep -E '^version[[:space:]]*=' pyproject.toml 2>/dev/null | head -1 |
      sed -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/'
  )"
  if [[ -n "$from_toml" ]]; then
    echo "$from_toml"
    return 0
  fi
  echo "0.0.0-dev"
}

MCP_SERVER_VERSION="$(read_mcp_server_version)"
echo "==> MCP server version: $MCP_SERVER_VERSION" >&2

if [[ "$DEPLOY_ZIP" == true ]]; then
  BASE_TEMPLATE="infra/template-zip.yaml"
  DEPLOY_MODE="ZIP"
else
  BASE_TEMPLATE="infra/template.yaml"
  DEPLOY_MODE="container"
fi

ZIP_STAGE_DIR=""
SAM_TEMPLATE_IS_TEMP=false
SAM_WORK_DIR="$ROOT/.aws-sam"
ZIP_STAGE_DIR="$SAM_WORK_DIR/zip-stage"
OE_MCP_SAM_BUILD_DIR="${OE_MCP_SAM_BUILD_DIR:-$SAM_WORK_DIR/build}"

cleanup_deploy_artifacts() {
  if [[ "$DEPLOY_ZIP" == true ]]; then
    rm -rf "$ZIP_STAGE_DIR"
  fi
  if [[ "$SAM_TEMPLATE_IS_TEMP" == true ]]; then
    rm -f "$SAM_TEMPLATE"
  fi
}

prepare_zip_stage() {
  rm -rf "$ZIP_STAGE_DIR"
  mkdir -p "$ZIP_STAGE_DIR/infra"
  cp -r server entrypoints "$ZIP_STAGE_DIR/"
  cp requirements.txt pyproject.toml "$ZIP_STAGE_DIR/"
  cp infra/lambda-requirements.txt "$ZIP_STAGE_DIR/infra/"
  echo "==> Staged ZIP source at $ZIP_STAGE_DIR" >&2
}

prepare_sam_template() {
  local src="$1"
  if [[ "$DEPLOY_ZIP" != true ]]; then
    echo "$ROOT/$src"
    return
  fi
  prepare_zip_stage
  local out="$SAM_WORK_DIR/template-zip.deploy.yaml"
  mkdir -p "$SAM_WORK_DIR"
  cp "$ROOT/$src" "$out"
  # CodeUri: ../ is relative to infra/; point at the clean staging tree (avoids /tmp
  # template resolving ../ to filesystem root, and skips dev artifacts like .codegraph).
  sed -i "s|CodeUri: \\.\\./|CodeUri: ${ZIP_STAGE_DIR}/|" "$out"
  SAM_TEMPLATE_IS_TEMP=true
  echo "$out"
}

resolve_built_template() {
  local candidate
  for candidate in \
    "$OE_MCP_SAM_BUILD_DIR/template.yaml" \
    "$SAM_WORK_DIR/build/template.yaml" \
    "$ROOT/.aws-sam/build/template.yaml"; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

SAM_TEMPLATE="$(prepare_sam_template "$BASE_TEMPLATE")"
trap cleanup_deploy_artifacts EXIT

command -v sam >/dev/null 2>&1 || {
  echo "error: AWS SAM CLI ('sam') not found. Install: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html" >&2
  exit 1
}

IMAGE_REPOSITORY=""
if [[ "$DEPLOY_ZIP" == false ]]; then
  command -v docker >/dev/null 2>&1 || {
    echo "error: docker not found (required for container sam build)" >&2
    exit 1
  }

  ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
  IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}}"

  if ! aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" &>/dev/null; then
    echo "==> Creating ECR repository: $ECR_REPO"
    aws ecr create-repository \
      --repository-name "$ECR_REPO" \
      --region "$AWS_REGION" \
      --image-scanning-configuration scanOnPush=true \
      --encryption-configuration encryptionType=AES256 \
      >/dev/null
  fi

  echo "==> Docker login to ECR ($AWS_REGION)"
  aws ecr get-login-password --region "$AWS_REGION" |
    docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

  if [[ "${SAM_SKIP_DOCKER_PULL_BASE:-false}" != "true" ]]; then
    echo "==> Refresh Lambda base image (avoids stale digest NotFound from cache)"
    docker pull public.ecr.aws/lambda/python:3.12
  fi
fi

BUILD_ARGS=( -t "$SAM_TEMPLATE" )
if [[ "$DEPLOY_ZIP" == true ]]; then
  if [[ "${SAM_USE_CONTAINER:-false}" == "true" ]]; then
    if ! command -v docker >/dev/null 2>&1; then
      echo "error: SAM_USE_CONTAINER=true requires Docker" >&2
      exit 1
    fi
    BUILD_ARGS+=( --use-container )
  else
    BUILD_ARGS+=( --no-use-container )
  fi
else
  if [[ "${SAM_USE_CONTAINER:-true}" != "false" ]]; then
    BUILD_ARGS+=( --use-container )
  fi
fi
if [[ "${SAM_BUILD_NO_CACHED:-false}" == "true" ]]; then
  BUILD_ARGS+=( --no-cached )
fi

echo "==> sam build ($DEPLOY_MODE) ${BUILD_ARGS[*]}"
mkdir -p "$OE_MCP_SAM_BUILD_DIR"
sam build "${BUILD_ARGS[@]}" --build-dir "$OE_MCP_SAM_BUILD_DIR"

BUILT_TEMPLATE="$(resolve_built_template || true)"
if [[ -z "$BUILT_TEMPLATE" ]]; then
  echo "error: SAM build did not produce template.yaml" >&2
  echo "  expected one of:" >&2
  echo "    $OE_MCP_SAM_BUILD_DIR/template.yaml" >&2
  echo "    $SAM_WORK_DIR/build/template.yaml" >&2
  echo "    $ROOT/.aws-sam/build/template.yaml" >&2
  exit 1
fi
echo "==> Using built template: $BUILT_TEMPLATE" >&2

OVERRIDES=(
  "AuthMode=${AUTH_MODE}"
  "OvalEdgeBaseUrl=${OVALEDGE_BASE_URL}"
  "Environment=${ENVIRONMENT}"
  "McpHttpStateless=${MCP_HTTP_STATELESS}"
  "LambdaArchitecture=${LAMBDA_ARCHITECTURE}"
  "OvalEdgeHttpAuthScheme=${OVALEDGE_HTTP_AUTH_SCHEME}"
  "CredentialsCacheMaxEntries=${CREDENTIALS_CACHE_MAX_ENTRIES}"
  "LambdaMemorySize=${LAMBDA_MEMORY_SIZE}"
  "LambdaTimeout=${LAMBDA_TIMEOUT}"
  "McpServerVersion=${MCP_SERVER_VERSION}"
  "TelemetryBackend=${TELEMETRY_BACKEND}"
  "TelemetryServiceName=${TELEMETRY_SERVICE_NAME}"
  "TelemetryProjectName=${TELEMETRY_PROJECT_NAME}"
  "PhoenixHost=${PHOENIX_HOST}"
  "PhoenixApiKey=${PHOENIX_API_KEY}"
  "LangfuseHost=${LANGFUSE_HOST}"
  "LangfusePublicKey=${LANGFUSE_PUBLIC_KEY}"
  "LangfuseSecretKey=${LANGFUSE_SECRET_KEY}"
  "TelemetryOtlpEndpoint=${TELEMETRY_OTLP_ENDPOINT}"
  "TelemetryApiKey=${TELEMETRY_API_KEY}"
)
if [[ "$ENABLE_WAF" == true ]]; then
  OVERRIDES+=("EnableWaf=true" "AllowedSourceCidrs=${ALLOWED_SOURCE_CIDRS}")
else
  OVERRIDES+=("EnableWaf=false")
fi
if [[ -n "${SAM_OAUTH_ISSUER:-}" ]]; then
  OVERRIDES+=("OAuthIssuer=${SAM_OAUTH_ISSUER}")
fi
if [[ -n "${SAM_OAUTH_AUDIENCE:-}" ]]; then
  OVERRIDES+=("OAuthAudience=${SAM_OAUTH_AUDIENCE}")
fi

DEPLOY_ARGS=(
  -t "$BUILT_TEMPLATE"
  --stack-name "$STACK_NAME"
  --region "$AWS_REGION"
  --capabilities CAPABILITY_IAM
  --resolve-s3
  --no-confirm-changeset
  --no-fail-on-empty-changeset
  --parameter-overrides "${OVERRIDES[@]}"
)
if [[ "$DEPLOY_ZIP" == false ]]; then
  DEPLOY_ARGS+=( --image-repository "$IMAGE_REPOSITORY" )
fi

echo "==> sam deploy (stack=$STACK_NAME region=$AWS_REGION mode=$DEPLOY_MODE waf=$ENABLE_WAF)"
sam deploy "${DEPLOY_ARGS[@]}"

echo ""
echo "==> Stack outputs"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

echo ""
echo "Tip: point MCP clients at MCPEndpointUrl (https). API Gateway has no authorizer; auth is in the app."
echo "Branding: set Lambda env MCP_PUBLIC_BASE_URL to output MCPPublicBaseUrl (no /mcp suffix)."
echo "Telemetry: default disabled (TELEMETRY_BACKEND=none). See infra/DEPLOY.md#telemetry-opentelemetry."
echo "Guide: infra/DEPLOY.md"
if [[ "$ENABLE_WAF" == true ]]; then
  echo ""
  echo "WAF: only allowlisted CIDRs reach the API; others receive 403. App auth is still required."
fi
