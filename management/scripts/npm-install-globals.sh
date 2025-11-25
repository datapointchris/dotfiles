#!/usr/bin/env bash
# ================================================================
# Install npm global packages
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

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
    print_info "Installing $package..."
    npm install -g "$package"
  fi
done

echo ""
echo "npm global packages installed"
npm list -g --depth=0
