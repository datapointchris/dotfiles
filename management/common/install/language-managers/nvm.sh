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

print_section "Node.js (nvm)"

NVM_DIR="$HOME/.config/nvm"
NVM_VERSION="v0.40.0"
NVM_INSTALL_SCRIPT="https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh"

if [[ "$UPDATE_MODE" == "true" ]]; then
  log_info "Checking for nvm updates..."
else
  log_info "Installing nvm..."
fi

# Check if packages.yml exists
if [[ ! -f "$DOTFILES_DIR/management/packages.yml" ]]; then
  log_error "packages.yml not found at $DOTFILES_DIR/management/packages.yml"
  exit 1
fi

# Run nvm install script (download or use from home directory)
run_nvm_install() {
  local tmp_script="/tmp/nvm-install.sh"

  # Try to download
  log_info "Downloading nvm install script..."
  if curl -fsSL "$NVM_INSTALL_SCRIPT" -o "$tmp_script"; then
    chmod +x "$tmp_script"
    PROFILE=/dev/null NVM_DIR="$NVM_DIR" bash "$tmp_script"
    return $?
  fi

  # Download failed - check home directory for manual download
  log_warning "Download failed, checking home directory..."
  local home_script
  home_script=$(find "$HOME" -maxdepth 1 -name "*nvm*install*.sh" -type f 2>/dev/null | head -1)

  if [[ -n "$home_script" ]]; then
    log_info "Found in home directory: $home_script"
    PROFILE=/dev/null NVM_DIR="$NVM_DIR" bash "$home_script"
    return $?
  fi

  # Not found anywhere
  manual_steps="1. Download nvm install script in your browser:
   $NVM_INSTALL_SCRIPT

2. Save to home directory (e.g., ~/nvm-install.sh)

3. Re-run this installer:
   bash $DOTFILES_DIR/management/common/install/language-managers/nvm.sh"
  output_failure_data "nvm" "$NVM_INSTALL_SCRIPT" "$NVM_VERSION" "$manual_steps" "Failed to download install script"
  return 1
}

# Install or update nvm
if [[ "$UPDATE_MODE" == "true" ]]; then
  # Update mode: always re-run install script (it's idempotent)
  log_info "Updating nvm..."
  if ! run_nvm_install; then
    log_error "Failed to update nvm"
    exit 1
  fi
  log_success "nvm updated"
else
  # Install mode: only install if not already installed
  if [[ ! -d "$NVM_DIR" ]] || [[ "${FORCE_INSTALL:-false}" == "true" ]]; then
    log_info "Installing nvm to $NVM_DIR..."
    mkdir -p "$NVM_DIR"
    if ! run_nvm_install; then
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
