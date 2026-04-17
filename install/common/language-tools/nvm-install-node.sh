#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

NODE_VERSION="${1:-}"

if [[ -z "$NODE_VERSION" ]]; then
  echo "Error: Node.js version required"
  echo "Usage: $0 <version>"
  exit 1
fi

# Source nvm
export NVM_DIR="${NVM_DIR:-$HOME/.local/share/nvm}"
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

# Install Node.js (nvm install activates the version; no separate `nvm use` needed)
nvm install "$NODE_VERSION"
nvm alias default "$NODE_VERSION"
