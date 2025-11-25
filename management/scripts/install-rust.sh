#!/usr/bin/env bash
# ================================================================
# Install Rust via rustup
# ================================================================
# Universal script for all platforms
# Uses --no-modify-path since we manage PATH in dotfiles
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

print_banner "Installing Rust"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v cargo >/dev/null 2>&1; then
  print_success "Rust already installed: $(rustc --version)"
else
  print_info "Installing Rust..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path

  # Source cargo env for current shell
  source "$HOME/.cargo/env"

  print_success "Rust installed: $(rustc --version)"
fi
