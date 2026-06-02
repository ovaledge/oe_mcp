#!/usr/bin/env bash
# Run NFD-48785 live API integration tests (requires OvalEdge + valid JWT).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -z "${OE_INTEGRATION_JWT:-}" ]]; then
  echo "Tip: export OE_INTEGRATION_JWT from OvalEdge My Profile → API token if .env secret is stale."
fi

poetry run pytest -c tests/integration/pytest.ini tests/integration -m integration "$@"
