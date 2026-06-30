#!/usr/bin/env bash
# One-shot: build container image with SAM, push to ECR, deploy with regional WAF IP allowlist.
#
# Same as scripts/deploy.sh but uses infra/template-waf.yaml (AWS WAFv2 on the HTTP API stage).
#
# Required:
#   OVALEDGE_BASE_URL
#   ALLOWED_SOURCE_CIDRS   Comma-separated IPv4 CIDRs, e.g. 203.0.113.0/24,198.51.100.10/32
#
# Usage:
#   export OVALEDGE_BASE_URL=https://your-tenant.example.com
#   export ALLOWED_SOURCE_CIDRS=203.0.113.0/24
#   ./scripts/deploy-waf.sh
#
set -euo pipefail

if [[ -z "${OVALEDGE_BASE_URL:-}" ]]; then
  echo "error: set OVALEDGE_BASE_URL" >&2
  exit 1
fi
if [[ -z "${ALLOWED_SOURCE_CIDRS:-}" ]]; then
  echo "error: set ALLOWED_SOURCE_CIDRS (comma-separated IPv4 CIDRs allowed through WAF)" >&2
  exit 1
fi

export SAM_TEMPLATE="${SAM_TEMPLATE:-infra/template-waf.yaml}"

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

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}}"

command -v sam >/dev/null 2>&1 || {
  echo "error: AWS SAM CLI ('sam') not found." >&2
  exit 1
}
command -v docker >/dev/null 2>&1 || {
  echo "error: docker not found (required for sam build --use-container)" >&2
  exit 1
}

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
  echo "==> Refresh Lambda base image"
  docker pull public.ecr.aws/lambda/python:3.12
fi

BUILD_ARGS=( -t "$SAM_TEMPLATE" )
if [[ "${SAM_USE_CONTAINER:-true}" != "false" ]]; then
  BUILD_ARGS+=( --use-container )
fi
if [[ "${SAM_BUILD_NO_CACHED:-false}" == "true" ]]; then
  BUILD_ARGS+=( --no-cached )
fi

echo "==> sam build (WAF template) ${BUILD_ARGS[*]}"
sam build "${BUILD_ARGS[@]}"

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
  "AllowedSourceCidrs=${ALLOWED_SOURCE_CIDRS}"
)
if [[ -n "${SAM_OAUTH_ISSUER:-}" ]]; then
  OVERRIDES+=("OAuthIssuer=${SAM_OAUTH_ISSUER}")
fi
if [[ -n "${SAM_OAUTH_AUDIENCE:-}" ]]; then
  OVERRIDES+=("OAuthAudience=${SAM_OAUTH_AUDIENCE}")
fi

echo "==> sam deploy (stack=$STACK_NAME region=$AWS_REGION WAF allowlist=$ALLOWED_SOURCE_CIDRS)"
sam deploy \
  -t .aws-sam/build/template.yaml \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --image-repository "$IMAGE_REPOSITORY" \
  --parameter-overrides "${OVERRIDES[@]}"

echo ""
echo "==> Stack outputs"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

echo ""
echo "WAF: only ALLOWED_SOURCE_CIDRS may reach the API; others receive 403 from WAF."
echo "     MCP clients must egress from an allowlisted IP (e.g. corporate proxy/VPN)."
echo "     App auth (credentials / Bearer) is still required after WAF allows the request."
echo ""
echo "Template: $SAM_TEMPLATE. Public API (no WAF): ./scripts/deploy.sh"
