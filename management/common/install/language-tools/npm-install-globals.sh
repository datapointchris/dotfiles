#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_section "npm Global Packages"

# Source nvm to get npm in PATH
export NVM_DIR="${NVM_DIR:-$HOME/.local/share/nvm}"
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  log_error "nvm not found at $NVM_DIR"
  exit 1
fi

# shellcheck disable=SC1091
source "$NVM_DIR/nvm.sh"

# Verify npm is available
if ! command -v npm >/dev/null 2>&1; then
  log_error "npm not found (Node.js may not be installed)"
  exit 1
fi

log_info "Installing npm global packages from packages.yml..."

# Get npm packages from packages.yml via Python parser
NPM_PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=npm)

FAILURE_COUNT=0
for package in $NPM_PACKAGES; do
  if npm list -g "$package" --depth=0 &>/dev/null; then
    log_success "$package already installed, skipping"
  else
    log_info "Installing $package..."
    if npm install -g "$package"; then
      log_success "$package installed"
    else
      manual_steps="Install manually with npm:
   npm install -g $package

View package on npm:
   https://www.npmjs.com/package/$package"

      output_failure_data "$package" "https://www.npmjs.com/package/$package" "latest" "$manual_steps" "Failed to install via npm"
      log_warning "$package installation failed (see summary)"
      FAILURE_COUNT=$((FAILURE_COUNT + 1))
    fi
  fi
done

if [[ $FAILURE_COUNT -gt 0 ]]; then
  log_warning "$FAILURE_COUNT package(s) failed to install"
  npm list -g --depth=0
  exit 1
else
  log_success "All npm global packages installed successfully"
  npm list -g --depth=0
fi
