#!/usr/bin/env bash
# ================================================================
# Install npm global packages
# ================================================================

set -euo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

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

echo "Installing npm global packages from packages.yml..."

# Get npm packages from packages.yml via Python parser
DOTFILES_DIR="$HOME/dotfiles"
NPM_PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=npm)

# Install each package (skip if already installed at same version)
for package in $NPM_PACKAGES; do
  if npm list -g "$package" --depth=0 &>/dev/null; then
    echo "  $package already installed (skipping)"
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
    fi
  fi
done

echo ""
echo "npm global packages installed"
npm list -g --depth=0
