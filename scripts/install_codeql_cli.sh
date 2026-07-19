#!/usr/bin/env bash
# Install the CodeQL CLI into ~/.local/codeql (or CODEQL_INSTALL_DIR) and ensure
# the `codeql` binary is usable by scripts/run_codeql.sh / pre-commit.
#
# Usage:
#   ./scripts/install_codeql_cli.sh
#
# Env:
#   CODEQL_INSTALL_DIR  — default: $HOME/.local/codeql
#   CODEQL_BUNDLE_URL   — override download URL (advanced)

set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

INSTALL_DIR="${CODEQL_INSTALL_DIR:-${HOME}/.local/codeql}"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "${OS}-${ARCH}" in
  linux-x86_64|linux-amd64)
    ASSET="codeql-bundle-linux64.tar.gz"
    ;;
  linux-aarch64|linux-arm64)
    ASSET="codeql-bundle-linux64.tar.gz"
    echo "warning: using linux64 bundle on ${ARCH}; if extract fails, set CODEQL_BUNDLE_URL." >&2
    ;;
  darwin-arm64|darwin-aarch64)
    ASSET="codeql-bundle-osx64.tar.gz"
    ;;
  darwin-x86_64)
    ASSET="codeql-bundle-osx64.tar.gz"
    ;;
  *)
    die "unsupported platform ${OS}/${ARCH}; install manually: https://docs.github.com/en/code-security/codeql-cli"
    ;;
esac

BUNDLE_URL="${CODEQL_BUNDLE_URL:-https://github.com/github/codeql-action/releases/latest/download/${ASSET}}"

if [[ -x "${INSTALL_DIR}/codeql" ]]; then
  echo "==> CodeQL already installed at ${INSTALL_DIR}/codeql"
  "${INSTALL_DIR}/codeql" version
  exit 0
fi

command -v curl >/dev/null 2>&1 || die "curl is required"
command -v tar >/dev/null 2>&1 || die "tar is required"

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

echo "==> Downloading CodeQL CLI bundle (${ASSET}) ..."
echo "    ${BUNDLE_URL}"
curl -fsSL "${BUNDLE_URL}" -o "${TMP}/${ASSET}"

echo "==> Extracting to ${INSTALL_DIR} ..."
mkdir -p "$(dirname "${INSTALL_DIR}")"
# Bundle extracts as a top-level "codeql/" directory.
tar -xzf "${TMP}/${ASSET}" -C "${TMP}"
if [[ -d "${TMP}/codeql" ]]; then
  rm -rf "${INSTALL_DIR}"
  mv "${TMP}/codeql" "${INSTALL_DIR}"
else
  die "unexpected bundle layout (expected ${TMP}/codeql)"
fi

[[ -x "${INSTALL_DIR}/codeql" ]] || die "codeql binary missing after extract"

# Symlink into a common PATH location when possible.
BIN_DIR="${HOME}/.local/bin"
mkdir -p "${BIN_DIR}"
ln -sfn "${INSTALL_DIR}/codeql" "${BIN_DIR}/codeql"

echo "==> CodeQL installed:"
"${INSTALL_DIR}/codeql" version
echo ""
echo "Ensure ${BIN_DIR} is on your PATH, e.g.:"
echo "  export PATH=\"${BIN_DIR}:\$PATH\""
echo "Then verify: codeql version && ./scripts/run_codeql.sh"
