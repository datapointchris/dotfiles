#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"

print_section "Installing macOS casks"

log_info "Installing casks from packages.yml..."
CASKS=$(PYTHONPATH="$DOTFILES_DIR/src" /usr/bin/python3 -m dotfiles.parse_packages --type=macos-casks | tr '\n' ' ')

# shellcheck disable=SC2086
if brew install --quiet --cask $CASKS; then
  log_success "Casks installed"
else
  log_warning "Some casks may have failed to install"
fi

log_success "macOS casks installed"
