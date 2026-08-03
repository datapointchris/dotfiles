#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v cargo >/dev/null 2>&1; then
  log_success "Rust already installed: $(rustc --version)"
  exit 0
fi

log_info "Installing Rust..."

if ! curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path; then
  output_failure_data "rust" "https://sh.rustup.rs" "latest" "rustup install script failed"
  log_error "Rust installation failed"
  exit 1
fi

# Source cargo env for current shell
# shellcheck source=/dev/null
source "$HOME/.cargo/env"

# Verify installation
if command -v cargo >/dev/null 2>&1 && command -v rustc >/dev/null 2>&1; then
  log_success "Rust installed: $(rustc --version)"
else
  output_failure_data "rust" "https://sh.rustup.rs" "latest" "Not found in PATH after installation"
  log_error "Rust not found in PATH"
  exit 1
fi
