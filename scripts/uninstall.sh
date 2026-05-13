#!/usr/bin/env bash
# One-shot uninstall: delete CloudFormation stack and optional ECR repository.
#
# Optional env:
#   STACK_NAME   CloudFormation stack name (default: oe-mcp)
#   AWS_REGION   (default: AWS_DEFAULT_REGION or us-east-1)
#   ECR_REPO     ECR repository name (default: oe-mcp)
#
# CLI:
#   --keep-ecr      Keep ECR repository and images
#   --yes           Skip interactive confirmation
#   -h|--help       Show help
#
# Usage:
#   ./scripts/uninstall.sh
#   ./scripts/uninstall.sh --yes
#   ./scripts/uninstall.sh --keep-ecr --yes

set -euo pipefail

usage() {
  cat <<'EOF'
One-shot uninstall (CloudFormation + optional ECR cleanup).

Optional env:
  STACK_NAME, AWS_REGION, ECR_REPO

Optional flags:
  --keep-ecr      Keep ECR repository and images
  --yes           Skip confirmation prompt
  -h, --help      Show this help

Examples:
  ./scripts/uninstall.sh
  ./scripts/uninstall.sh --yes
  ./scripts/uninstall.sh --keep-ecr --yes
EOF
}

DELETE_ECR=true
ASSUME_YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep-ecr)
      DELETE_ECR=false
      shift
      ;;
    --yes)
      ASSUME_YES=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1 (try --help)" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STACK_NAME="${STACK_NAME:-oe-mcp}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="$AWS_REGION"
ECR_REPO="${ECR_REPO:-oe-mcp}"

if [[ "$ASSUME_YES" != "true" ]]; then
  echo "This will uninstall AWS resources:"
  echo "  - CloudFormation stack: $STACK_NAME (region: $AWS_REGION)"
  if [[ "$DELETE_ECR" == "true" ]]; then
    echo "  - ECR repository: $ECR_REPO (including all images)"
  else
    echo "  - ECR repository: kept"
  fi
  echo ""
  read -r -p "Continue? [y/N] " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "==> Deleting CloudFormation stack: $STACK_NAME"
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$AWS_REGION"
  echo "==> Waiting for stack deletion to complete..."
  aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$AWS_REGION"
  echo "==> Stack deleted."
else
  echo "==> Stack not found, skipping: $STACK_NAME"
fi

if [[ "$DELETE_ECR" == "true" ]]; then
  if aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "==> Deleting ECR repository (force): $ECR_REPO"
    aws ecr delete-repository \
      --repository-name "$ECR_REPO" \
      --region "$AWS_REGION" \
      --force \
      >/dev/null
    echo "==> ECR repository deleted."
  else
    echo "==> ECR repository not found, skipping: $ECR_REPO"
  fi
fi

echo "Done."
