#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

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
    manual_steps="1. Download nvm install script in your browser:
   $NVM_INSTALL_SCRIPT

2. After downloading, install manually:
   curl -o- ~/Downloads/install.sh | NVM_DIR=\"$NVM_DIR\" bash

3. Verify installation:
   source $NVM_DIR/nvm.sh
   nvm --version"
    output_failure_data "nvm" "$NVM_INSTALL_SCRIPT" "v0.40.0" "$manual_steps" "Download failed"
    log_error "Failed to install nvm"
    return 1
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
  manual_steps="1. First ensure nvm is installed (see above)

2. Then install Node.js manually:
   source $NVM_DIR/nvm.sh
   nvm install ${NODE_VERSION}
   nvm alias default ${NODE_VERSION}

3. Verify installation:
   node --version"
  output_failure_data "nodejs" "https://nodejs.org" "$NODE_VERSION" "$manual_steps" "Node.js installation failed"
  log_error "Failed to install Node.js"
  return 1
fi
