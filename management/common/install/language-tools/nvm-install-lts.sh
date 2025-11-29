#!/usr/bin/env bash
# ================================================================
# Install latest LTS Node.js via nvm
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/management/common/lib/structured-logging.sh"

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

# Install latest LTS
echo "Installing latest LTS Node.js..."
nvm install --lts
nvm use --lts
nvm alias default "lts/*"

echo "Latest LTS Node.js installed and set as default"
node --version
npm --version
