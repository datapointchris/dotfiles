#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
source "$DOTFILES_DIR/install/common/lib/package-query.sh"

print_section "npm Global Packages"

# Node.js is installed as a system package, so npm should already be on PATH.
if ! command -v npm >/dev/null 2>&1; then
  log_error "npm not found on PATH (install the Node.js system package first)"
  exit 1
fi

# The prefix is set directly rather than through the npmrc that .zshrc points
# npm at, because that npmrc is a symlink created by the symlink phase, which
# runs after this one (it needs task, which needs Go). On a first install the
# file does not exist yet, npm falls back to its built-in prefix (/usr/local on
# Debian, /usr on Arch) and every global install dies with EACCES.
# NPM_CONFIG_PREFIX outranks every config file, so it holds in both orders.
export NPM_CONFIG_PREFIX="$HOME/.local/share/npm"
mkdir -p "$NPM_CONFIG_PREFIX"

log_info "Installing npm global packages from packages.yml..."

init_package_filters

# Get npm packages from packages.yml (filtered by manifest) via Python parser
NPM_PACKAGES=$(parse_packages --type=npm)

FAILURE_COUNT=0
for package in $NPM_PACKAGES; do
  if npm list -g "$package" --depth=0 &>/dev/null; then
    log_success "$package already installed, skipping"
  else
    log_info "Installing $package..."
    if npm_output=$(npm install -g "$package" 2>&1); then
      log_success "$package installed"
    else
      output_failure_data "$package" "https://www.npmjs.com/package/$package" "latest" "Failed to install via npm" "$npm_output"
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
fi
