#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_banner "Installing Rust"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v cargo >/dev/null 2>&1; then
  log_success "Rust already installed: $(rustc --version)"
  exit 0
fi

log_info "Installing Rust..."

if ! curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path; then
  manual_steps="1. Visit: https://rustup.rs/
2. Run installer: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
3. Follow prompts (use default options)
4. Source environment: source \$HOME/.cargo/env
5. Verify: rustc --version"

  output_failure_data "rust" "https://sh.rustup.rs" "latest" "$manual_steps" "rustup install script failed"
  log_error "Rust installation failed"
  exit 1
fi

# Source cargo env for current shell
source "$HOME/.cargo/env"

# Verify installation
if command -v cargo >/dev/null 2>&1 && command -v rustc >/dev/null 2>&1; then
  log_success "Rust installed: $(rustc --version)"
else
  manual_steps="Binary installed but not in PATH.

Source environment:
   source \$HOME/.cargo/env

Add to shell config (~/.zshrc or ~/.bashrc):
   source \$HOME/.cargo/env

Verify:
   rustc --version
   cargo --version"

  output_failure_data "rust" "https://sh.rustup.rs" "latest" "$manual_steps" "Not found in PATH after installation"
  log_error "Rust not found in PATH"
  exit 1
fi
