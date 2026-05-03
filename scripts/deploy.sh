#!/usr/bin/env bash
# One-shot: build container image with SAM, push to ECR, deploy CloudFormation stack.
#
# Required:
#   OVALEDGE_BASE_URL   OvalEdge tenant base URL (no trailing slash), e.g. https://app.example.com
#
# Common optional env:
#   STACK_NAME          CloudFormation stack name (default: oe-mcp)
#   AWS_REGION          (default: AWS_DEFAULT_REGION or us-east-1)
#   AUTH_MODE           remote_credentials | remote (default: remote_credentials)
#   ENVIRONMENT         dev | staging | prod — suffixes Lambda name (default: dev)
#   ECR_REPO            ECR repository name (default: oe-mcp); created if missing
#   MCP_HTTP_STATELESS  true | false (default: true) — see README_REMOTE_MCP.md
#
# OAuth remote mode extras (only when AUTH_MODE=remote):
#   SAM_OAUTH_ISSUER      maps to template OAuthIssuer
#   SAM_OAUTH_AUDIENCE  maps to template OAuthAudience
#
# Usage:
#   export OVALEDGE_BASE_URL=https://your-tenant.example.com
#   ./scripts/deploy.sh
#
set -euo pipefail

usage() {
  cat <<'EOF'
One-shot Lambda deploy (SAM build + ECR + CloudFormation).

Required env:
  OVALEDGE_BASE_URL   e.g. https://tenant.example.com (no trailing slash)

Optional env:
  STACK_NAME, AWS_REGION, AUTH_MODE, ENVIRONMENT, ECR_REPO, MCP_HTTP_STATELESS,
  IMAGE_REPOSITORY, SAM_OAUTH_ISSUER, SAM_OAUTH_AUDIENCE

Example:
  export OVALEDGE_BASE_URL=https://app.example.com
  ./scripts/deploy.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "${OVALEDGE_BASE_URL:-}" ]]; then
  echo "error: set OVALEDGE_BASE_URL (see --help)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STACK_NAME="${STACK_NAME:-oe-mcp}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="$AWS_REGION"
AUTH_MODE="${AUTH_MODE:-remote_credentials}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
ECR_REPO="${ECR_REPO:-oe-mcp}"
MCP_HTTP_STATELESS="${MCP_HTTP_STATELESS:-true}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}}"

command -v sam >/dev/null 2>&1 || {
  echo "error: AWS SAM CLI ('sam') not found. Install: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html" >&2
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

echo "==> sam build (container image from Dockerfile)"
sam build -t infra/template.yaml --use-container

OVERRIDES=(
  "AuthMode=${AUTH_MODE}"
  "OvalEdgeBaseUrl=${OVALEDGE_BASE_URL}"
  "Environment=${ENVIRONMENT}"
  "McpHttpStateless=${MCP_HTTP_STATELESS}"
)
if [[ -n "${SAM_OAUTH_ISSUER:-}" ]]; then
  OVERRIDES+=("OAuthIssuer=${SAM_OAUTH_ISSUER}")
fi
if [[ -n "${SAM_OAUTH_AUDIENCE:-}" ]]; then
  OVERRIDES+=("OAuthAudience=${SAM_OAUTH_AUDIENCE}")
fi

echo "==> sam deploy (stack=$STACK_NAME region=$AWS_REGION image=$IMAGE_REPOSITORY)"
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
echo "Tip: point Cursor MCP 'url' at MCPEndpointUrl (https). For remote_credentials, send the same"
echo "     X-OvalEdge-* headers as locally. API Gateway has no authorizer; auth is in the app."
