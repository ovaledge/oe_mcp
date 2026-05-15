#!/usr/bin/env bash
# One-shot: SAM build (Lambda ZIP from infra/template-zip.yaml) + CloudFormation deploy.
# Same parameters and stack shape as scripts/deploy.sh, but no Docker / ECR / container image.
#
# Required:
#   OVALEDGE_BASE_URL   OvalEdge tenant base URL (no trailing slash)
#
# Optional env (same semantics as deploy.sh where applicable):
#   STACK_NAME, AWS_REGION, AUTH_MODE, ENVIRONMENT, MCP_HTTP_STATELESS,
#   OVALEDGE_HTTP_AUTH_SCHEME, CREDENTIALS_CACHE_MAX_ENTRIES, LAMBDA_ARCHITECTURE,
#   SAM_OAUTH_ISSUER, SAM_OAUTH_AUDIENCE
#
# ZIP-specific:
#   SAM_USE_CONTAINER   if "true", run `sam build --use-container` (Docker) so pip wheels
#                       match Amazon Linux (recommended on macOS if native build fails).
#
# Usage:
#   export OVALEDGE_BASE_URL=https://your-tenant.example.com
#   ./scripts/deploy-zip.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${OVALEDGE_BASE_URL:-}" ]]; then
  echo "error: set OVALEDGE_BASE_URL (see scripts/deploy.sh --help)" >&2
  exit 1
fi

command -v sam >/dev/null 2>&1 || {
  echo "error: AWS SAM CLI ('sam') not found." >&2
  exit 1
}

STACK_NAME="${STACK_NAME:-oe-mcp}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="$AWS_REGION"
AUTH_MODE="${AUTH_MODE:-remote_credentials}"
OVALEDGE_HTTP_AUTH_SCHEME="${OVALEDGE_HTTP_AUTH_SCHEME:-jwt}"
CREDENTIALS_CACHE_MAX_ENTRIES="${CREDENTIALS_CACHE_MAX_ENTRIES:-10000}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-true}"
LAMBDA_ARCHITECTURE="${LAMBDA_ARCHITECTURE:-x86_64}"

TEMPLATE_ZIP="${TEMPLATE_ZIP:-infra/template-zip.yaml}"

BUILD_ARGS=( -t "$TEMPLATE_ZIP" )
if [[ "${SAM_USE_CONTAINER:-false}" == "true" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "error: SAM_USE_CONTAINER=true requires Docker" >&2
    exit 1
  fi
  BUILD_ARGS+=( --use-container )
else
  BUILD_ARGS+=( --no-use-container )
fi
if [[ "${SAM_BUILD_NO_CACHED:-false}" == "true" ]]; then
  BUILD_ARGS+=( --no-cached )
fi

echo "==> sam build (Lambda ZIP) ${BUILD_ARGS[*]}"
sam build "${BUILD_ARGS[@]}"

OVERRIDES=(
  "AuthMode=${AUTH_MODE}"
  "OvalEdgeBaseUrl=${OVALEDGE_BASE_URL}"
  "Environment=${ENVIRONMENT}"
  "McpHttpStateless=${MCP_HTTP_STATELESS}"
  "LambdaArchitecture=${LAMBDA_ARCHITECTURE}"
  "OvalEdgeHttpAuthScheme=${OVALEDGE_HTTP_AUTH_SCHEME}"
  "CredentialsCacheMaxEntries=${CREDENTIALS_CACHE_MAX_ENTRIES}"
)
if [[ -n "${SAM_OAUTH_ISSUER:-}" ]]; then
  OVERRIDES+=("OAuthIssuer=${SAM_OAUTH_ISSUER}")
fi
if [[ -n "${SAM_OAUTH_AUDIENCE:-}" ]]; then
  OVERRIDES+=("OAuthAudience=${SAM_OAUTH_AUDIENCE}")
fi

echo "==> sam deploy (stack=$STACK_NAME region=$AWS_REGION, ZIP artifact, no ECR)"
sam deploy \
  -t .aws-sam/build/template.yaml \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset \
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
echo "Deployed with infra/template-zip.yaml (Lambda ZIP). Image-based deploy: ./scripts/deploy.sh"
