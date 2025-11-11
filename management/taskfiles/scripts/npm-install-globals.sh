#!/usr/bin/env bash
# ================================================================
# Install npm global packages
# ================================================================

set -euo pipefail

# Source nvm to get npm in PATH
export NVM_DIR="${NVM_DIR:-$HOME/.config/nvm}"
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  echo "Error: nvm not found at $NVM_DIR"
  exit 1
fi

# shellcheck disable=SC1091
source "$NVM_DIR/nvm.sh"

# Verify npm is available
if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm not found (Node.js may not be installed)"
  exit 1
fi

echo "Installing npm global packages..."

# Helper function to install package only if not already installed
install_if_missing() {
  local package=$1
  local command_name=${2:-$package}  # Use package name as command if not specified

  if command -v "$command_name" >/dev/null 2>&1; then
    echo "  $package already installed, skipping"
  else
    echo "  Installing $package..."
    npm install -g "$package"
  fi
}

# Language servers
install_if_missing typescript-language-server
install_if_missing typescript tsc
install_if_missing bash-language-server
install_if_missing yaml-language-server
install_if_missing vscode-langservers-extracted vscode-html-language-server
install_if_missing gh-actions-language-server

# Linters and formatters
install_if_missing eslint
install_if_missing prettier
install_if_missing markdownlint-cli markdownlint

echo ""
echo "npm global packages installed"
npm list -g --depth=0
