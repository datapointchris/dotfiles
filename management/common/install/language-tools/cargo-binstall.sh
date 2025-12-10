#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

# Ensure cargo is available
source "$HOME/.cargo/env"

if command -v cargo-binstall >/dev/null 2>&1; then
  log_success "cargo-binstall already installed"
else
  log_info "Installing cargo-binstall..."
  cargo install cargo-binstall
  log_success "cargo-binstall installed"
fi
