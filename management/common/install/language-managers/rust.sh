#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Installing Rust"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v cargo >/dev/null 2>&1; then
  log_success "Rust already installed: $(rustc --version)"
else
  log_info "Installing Rust..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path

  # Source cargo env for current shell
  source "$HOME/.cargo/env"

  log_success "Rust installed: $(rustc --version)"
fi
