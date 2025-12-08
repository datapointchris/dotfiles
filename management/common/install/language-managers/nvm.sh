#!/usr/bin/env bash
set -uo pipefail

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

NVM_DIR="$HOME/.config/nvm"
NVM_INSTALL_SCRIPT="https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh"

if [[ "$UPDATE_MODE" == "true" ]]; then
  print_banner "Checking nvm and Node.js for updates"
else
  print_banner "Installing nvm and Node.js"
fi

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  log_error "packages.yml not found at $DOTFILES_DIR/management/packages.yml"
  exit 1
fi

# Install or update nvm
if [[ "$UPDATE_MODE" == "true" ]]; then
  # Update mode: always re-run install script (it's idempotent)
  log_info "Updating nvm..."
  if ! curl -o- "$NVM_INSTALL_SCRIPT" | NVM_DIR="$NVM_DIR" bash; then
    manual_steps="1. Download nvm install script in your browser:
   $NVM_INSTALL_SCRIPT

2. After downloading, install manually:
   curl -o- ~/Downloads/install.sh | NVM_DIR=\"$NVM_DIR\" bash

3. Verify installation:
   source $NVM_DIR/nvm.sh
   nvm --version"
    output_failure_data "nvm" "$NVM_INSTALL_SCRIPT" "v0.40.0" "$manual_steps" "curl install script failed"
    log_error "Failed to update nvm"
    exit 1
  fi
  log_success "nvm updated"
else
  # Install mode: only install if not already installed
  if [[ ! -d "$NVM_DIR" ]] || [[ "${FORCE_INSTALL:-false}" == "true" ]]; then
    log_info "Installing nvm to $NVM_DIR..."
    mkdir -p "$NVM_DIR"
    if ! curl -o- "$NVM_INSTALL_SCRIPT" | NVM_DIR="$NVM_DIR" bash; then
      manual_steps="1. Download nvm install script in your browser:
   $NVM_INSTALL_SCRIPT

2. After downloading, install manually:
   curl -o- ~/Downloads/install.sh | NVM_DIR=\"$NVM_DIR\" bash

3. Verify installation:
   source $NVM_DIR/nvm.sh
   nvm --version"
      output_failure_data "nvm" "$NVM_INSTALL_SCRIPT" "v0.40.0" "$manual_steps" "curl install script failed"
      log_error "Failed to install nvm"
      exit 1
    fi
    log_success "nvm installed"
  else
    log_info "nvm already installed"
  fi
fi

# Read Node version from packages.yml using Python parser
NODE_VERSION=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --get=runtimes.node.version)

# Source nvm to check current version
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  source "$NVM_DIR/nvm.sh"
fi

# Check if Node.js update needed
if [[ "$UPDATE_MODE" == "true" ]]; then
  log_info "Target Node.js version: ${NODE_VERSION}"

  if command -v node >/dev/null 2>&1; then
    CURRENT_NODE=$(node --version)
    CURRENT_NODE=${CURRENT_NODE#v}
    TARGET_NODE=${NODE_VERSION#v}
    log_info "Current Node.js version: $CURRENT_NODE"

    if [[ "$CURRENT_NODE" == "$TARGET_NODE" ]]; then
      log_success "Already at target Node.js version ($TARGET_NODE)"
      print_banner_success "nvm and Node.js are up to date"
      exit 0
    fi

    log_info "Updating Node.js from $CURRENT_NODE to $TARGET_NODE..."
  else
    log_info "Node.js not installed, installing..."
  fi
fi

# Install Node.js using the existing nvm-install-node.sh script
if ! NVM_DIR="$NVM_DIR" bash "$DOTFILES_DIR/management/common/install/language-tools/nvm-install-node.sh" "${NODE_VERSION}"; then
  manual_steps="1. First ensure nvm is installed (see above)

2. Then install Node.js manually:
   source $NVM_DIR/nvm.sh
   nvm install ${NODE_VERSION}
   nvm alias default ${NODE_VERSION}

3. Verify installation:
   node --version"
  output_failure_data "nodejs" "https://nodejs.org" "$NODE_VERSION" "$manual_steps" "Node.js installation failed"
  log_error "Failed to install Node.js"
  exit 1
fi

log_success "Node.js ${NODE_VERSION} installed and set as default"

if [[ "$UPDATE_MODE" == "true" ]]; then
  print_banner_success "nvm and Node.js update complete"
else
  print_banner_success "nvm and Node.js installation complete"
fi
