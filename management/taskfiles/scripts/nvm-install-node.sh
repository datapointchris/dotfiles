#!/usr/bin/env bash
# ================================================================
# Install Node.js via nvm
# ================================================================
# Usage: nvm-install-node.sh <version>
# Example: nvm-install-node.sh 24.11.0

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

NODE_VERSION="${1:-}"

if [[ -z "$NODE_VERSION" ]]; then
  echo "Error: Node.js version required"
  echo "Usage: $0 <version>"
  exit 1
fi

# Source nvm
export NVM_DIR="${NVM_DIR:-$HOME/.config/nvm}"
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  echo "Error: nvm not found at $NVM_DIR"
  exit 1
fi

# shellcheck disable=SC1091
source "$NVM_DIR/nvm.sh"

# Verify nvm loaded
if ! command -v nvm >/dev/null 2>&1; then
  echo "Error: nvm not loaded properly"
  exit 1
fi

# Install Node.js
echo "Installing Node.js ${NODE_VERSION}..."
nvm install "$NODE_VERSION"
nvm use "$NODE_VERSION"
nvm alias default "$NODE_VERSION"

echo "Node.js ${NODE_VERSION} installed and set as default"
node --version
npm --version
