#!/usr/bin/env bash
# ================================================================
# Install cargo-binstall
# ================================================================
# Universal script for all platforms
# Fast binary installation for Rust crates
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

print_banner "Installing cargo-binstall"

# Ensure cargo is available
source "$HOME/.cargo/env"

if command -v cargo-binstall >/dev/null 2>&1; then
  print_success "cargo-binstall already installed"
else
  print_info "Installing cargo-binstall..."
  cargo install cargo-binstall
  print_success "cargo-binstall installed"
fi
