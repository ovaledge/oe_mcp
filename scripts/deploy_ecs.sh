#!/usr/bin/env bash
# Build Dockerfile.ecs, push to ECR, deploy infra/ecs/template.yaml (Fargate + ALB).
#
# Required:
#   OVALEDGE_BASE_URL
#   VPC_ID
#   SUBNET_IDS          comma-separated subnet IDs (min 2 AZs)
#
# Optional:
#   STACK_NAME, AWS_REGION, ENVIRONMENT, AUTH_MODE, ECR_REPO, IMAGE_TAG,
#   ASSIGN_PUBLIC_IP, DESIRED_COUNT, CPU, MEMORY, CERTIFICATE_ARN, ALLOWED_CIDR,
#   MCP_HTTP_STATELESS, TELEMETRY_*
#
# See infra/DEPLOY.md#aws-ecs-fargate--alb
#
set -euo pipefail

usage() {
  cat <<'EOF'
Build ECS image + deploy CloudFormation (Fargate + ALB).

Required env:
  OVALEDGE_BASE_URL   OvalEdge tenant URL (no trailing slash)
  VPC_ID              Existing VPC
  SUBNET_IDS          Comma-separated subnet IDs (at least two AZs)

Optional env:
  STACK_NAME=oe-mcp-ecs
  AWS_REGION / AWS_DEFAULT_REGION
  ENVIRONMENT=dev
  AUTH_MODE=remote_credentials
  ECR_REPO=oe-mcp-ecs
  IMAGE_TAG=latest   (also tags with git SHA when available)
  ASSIGN_PUBLIC_IP=ENABLED
  DESIRED_COUNT=1
  CPU=512 MEMORY=1024
  CERTIFICATE_ARN=   (ACM ARN for HTTPS; empty = HTTP :80 only)
  ALLOWED_CIDR=0.0.0.0/0
  MCP_HTTP_STATELESS=false

Examples:
  export OVALEDGE_BASE_URL=https://app.example.com
  export VPC_ID=vpc-xxx
  export SUBNET_IDS=subnet-aaa,subnet-bbb
  ./scripts/deploy_ecs.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "${OVALEDGE_BASE_URL:-}" ]]; then
  echo "error: set OVALEDGE_BASE_URL" >&2
  usage >&2
  exit 1
fi
if [[ -z "${VPC_ID:-}" ]]; then
  echo "error: set VPC_ID" >&2
  exit 1
fi
if [[ -z "${SUBNET_IDS:-}" ]]; then
  echo "error: set SUBNET_IDS (comma-separated, >=2)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STACK_NAME="${STACK_NAME:-oe-mcp-ecs}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="$AWS_REGION"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AUTH_MODE="${AUTH_MODE:-remote_credentials}"
ECR_REPO="${ECR_REPO:-oe-mcp-ecs}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ASSIGN_PUBLIC_IP="${ASSIGN_PUBLIC_IP:-ENABLED}"
DESIRED_COUNT="${DESIRED_COUNT:-1}"
CPU="${CPU:-512}"
MEMORY="${MEMORY:-1024}"
CERTIFICATE_ARN="${CERTIFICATE_ARN:-}"
ALLOWED_CIDR="${ALLOWED_CIDR:-0.0.0.0/0}"
MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-false}"
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

command -v aws >/dev/null 2>&1 || { echo "error: aws CLI required" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "error: docker required" >&2; exit 1; }

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

echo "==> Ensuring ECR repository ${ECR_REPO}"
if ! aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1; then
  aws ecr create-repository \
    --repository-name "$ECR_REPO" \
    --region "$AWS_REGION" \
    --image-scanning-configuration scanOnPush=true \
    >/dev/null
fi

echo "==> Login to ECR"
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo none)"
TAGS=("${IMAGE_TAG}")
if [[ "$GIT_SHA" != "none" && "$IMAGE_TAG" != "$GIT_SHA" ]]; then
  TAGS+=("$GIT_SHA")
fi

echo "==> docker build -f Dockerfile.ecs"
docker build -f Dockerfile.ecs -t "${ECR_REPO}:${IMAGE_TAG}" .
for tag in "${TAGS[@]}"; do
  docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}:${tag}"
  echo "==> docker push ${ECR_URI}:${tag}"
  docker push "${ECR_URI}:${tag}"
done

IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"
# CloudFormation List<SubnetId> via CLI: use space-separated quoted list with ParameterKey form,
# or comma-separated for simple overrides — CFN accepts "subnet-a,subnet-b" for List types.
SUBNET_PARAM="${SUBNET_IDS}"

OVERRIDES=(
  "Environment=${ENVIRONMENT}"
  "ImageUri=${IMAGE_URI}"
  "OvalEdgeBaseUrl=${OVALEDGE_BASE_URL}"
  "AuthMode=${AUTH_MODE}"
  "VpcId=${VPC_ID}"
  "SubnetIds=${SUBNET_PARAM}"
  "AssignPublicIp=${ASSIGN_PUBLIC_IP}"
  "DesiredCount=${DESIRED_COUNT}"
  "Cpu=${CPU}"
  "Memory=${MEMORY}"
  "McpHttpStateless=${MCP_HTTP_STATELESS}"
  "AllowedCidr=${ALLOWED_CIDR}"
  "TelemetryBackend=${TELEMETRY_BACKEND}"
  "TelemetryServiceName=${TELEMETRY_SERVICE_NAME}"
)

append_if_set() {
  local key="$1"
  local value="${2:-}"
  if [[ -n "$value" ]]; then
    OVERRIDES+=("${key}=${value}")
  fi
}
append_if_set CertificateArn "$CERTIFICATE_ARN"
append_if_set TelemetryProjectName "$TELEMETRY_PROJECT_NAME"
append_if_set PhoenixHost "$PHOENIX_HOST"
append_if_set PhoenixApiKey "$PHOENIX_API_KEY"
append_if_set LangfuseHost "$LANGFUSE_HOST"
append_if_set LangfusePublicKey "$LANGFUSE_PUBLIC_KEY"
append_if_set LangfuseSecretKey "$LANGFUSE_SECRET_KEY"
append_if_set TelemetryOtlpEndpoint "$TELEMETRY_OTLP_ENDPOINT"
append_if_set TelemetryApiKey "$TELEMETRY_API_KEY"
append_if_set OAuthIssuer "${OAUTH_ISSUER:-}"
append_if_set OAuthAllowedIssuers "${OAUTH_ALLOWED_ISSUERS:-}"
append_if_set OAuthAudience "${OAUTH_AUDIENCE:-}"
append_if_set OAuthClientId "${OAUTH_CLIENT_ID:-}"
append_if_set OAuthClientSecret "${OAUTH_CLIENT_SECRET:-}"
append_if_set OAuthIntrospectionUrl "${OAUTH_INTROSPECTION_URL:-}"
append_if_set OAuthScopes "${OAUTH_SCOPES:-}"
OVERRIDES+=("OvalEdgeForwardIdpToken=${OVALEDGE_REMOTE_FORWARD_IDP_TOKEN:-true}")

echo "==> cloudformation deploy stack=${STACK_NAME} region=${AWS_REGION}"
aws cloudformation deploy \
  --template-file infra/ecs/template.yaml \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --parameter-overrides "${OVERRIDES[@]}"

echo ""
echo "==> Stack outputs"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

echo ""
echo "Point MCP clients at McpEndpointUrl (HTTPS preferred)."
echo "Auth: AUTH_MODE=${AUTH_MODE} — send X-OvalEdge-Token / X-OvalEdge-Secret from mcp.json."
echo "Guide: infra/DEPLOY.md#aws-ecs-fargate--alb"
