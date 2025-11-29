#!/usr/bin/env bash
# ================================================================
# Install NVM and Node.js
# ================================================================
# Installs nvm to ~/.config/nvm and Node.js version from packages.yml
# Universal script for all platforms
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

NVM_DIR="$HOME/.config/nvm"
NVM_INSTALL_SCRIPT="https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh"

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  log_error "packages.yml not found at $DOTFILES_DIR/management/packages.yml"
  exit 1
fi

print_section "Installing nvm" "cyan"

# Install nvm if not already installed
if [[ ! -d "$NVM_DIR" ]]; then
  echo "  Installing nvm to $NVM_DIR..."
  mkdir -p "$NVM_DIR"
  if curl -o- "$NVM_INSTALL_SCRIPT" | NVM_DIR="$NVM_DIR" bash; then
    echo "  ✓ nvm installed"
  else
    log_error "Failed to install nvm"
    exit 1
  fi
else
  echo "  nvm already installed"
fi

# Read Node version from packages.yml using Python parser
NODE_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --get=runtimes.node.version)

print_section "Installing Node.js ${NODE_VERSION}" "cyan"

# Install Node.js using the existing nvm-install-node.sh script
if NVM_DIR="$NVM_DIR" bash "$DOTFILES_DIR/management/common/install/language-tools/nvm-install-node.sh" "${NODE_VERSION}"; then
  log_success "Node.js ${NODE_VERSION} installed and set as default"
else
  log_error "Failed to install Node.js"
  exit 1
fi
