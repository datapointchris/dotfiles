#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_section "Installing macOS casks"

log_info "Installing casks from packages.yml..."
CASKS=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=macos-casks | tr '\n' ' ')

# shellcheck disable=SC2086
if brew install --cask $CASKS; then
  log_success "Casks installed"
else
  log_warning "Some casks may have failed to install"
fi

log_success "macOS casks installed"
