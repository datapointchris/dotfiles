#!/usr/bin/env bash
# ================================================================
# Install cargo-binstall
# ================================================================
# Universal script for all platforms
# Fast binary installation for Rust crates
# ================================================================

set -euo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Installing cargo-binstall"

# Ensure cargo is available
source "$HOME/.cargo/env"

if command -v cargo-binstall >/dev/null 2>&1; then
  log_success "cargo-binstall already installed"
else
  log_info "Installing cargo-binstall..."
  cargo install cargo-binstall
  log_success "cargo-binstall installed"
fi
