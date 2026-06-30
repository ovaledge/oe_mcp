#!/usr/bin/env bash
# One-shot: SAM build (Lambda ZIP) + deploy with regional WAF IP allowlist.
#
# Same as scripts/deploy-zip.sh but uses infra/template-zip-waf.yaml.
#
# Required:
#   OVALEDGE_BASE_URL
#   ALLOWED_SOURCE_CIDRS   Comma-separated IPv4 CIDRs, e.g. 203.0.113.0/24,198.51.100.10/32
#
# Usage:
#   export OVALEDGE_BASE_URL=https://your-tenant.example.com
#   export ALLOWED_SOURCE_CIDRS=203.0.113.0/24
#   ./scripts/deploy-zip-waf.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${OVALEDGE_BASE_URL:-}" ]]; then
  echo "error: set OVALEDGE_BASE_URL" >&2
  exit 1
fi
if [[ -z "${ALLOWED_SOURCE_CIDRS:-}" ]]; then
  echo "error: set ALLOWED_SOURCE_CIDRS (comma-separated IPv4 CIDRs allowed through WAF)" >&2
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
LAMBDA_MEMORY_SIZE="${LAMBDA_MEMORY_SIZE:-1024}"
LAMBDA_TIMEOUT="${LAMBDA_TIMEOUT:-30}"

SAM_TEMPLATE="${SAM_TEMPLATE:-infra/template-zip-waf.yaml}"

BUILD_ARGS=( -t "$SAM_TEMPLATE" )
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

echo "==> sam build (ZIP + WAF) ${BUILD_ARGS[*]}"
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
echo ""
echo "Template: $SAM_TEMPLATE. Public ZIP (no WAF): ./scripts/deploy-zip.sh"
