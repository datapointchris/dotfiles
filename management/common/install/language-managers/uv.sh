#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

print_section "uv (Python Package Manager)"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v uv >/dev/null 2>&1; then
  log_success "uv already installed: $(uv --version)"
  exit 0
fi

log_info "Installing uv Python package manager..."

# Set XDG_BIN_HOME to ensure clean install path and prevent shell modification
if ! XDG_BIN_HOME="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 curl -LsSf https://astral.sh/uv/install.sh | sh; then
  manual_steps="1. Visit: https://docs.astral.sh/uv/getting-started/installation/
2. Run installer: curl -LsSf https://astral.sh/uv/install.sh | sh
3. Add to PATH: export PATH=\"\$HOME/.local/bin:\$PATH\"
4. Verify: uv --version"

  output_failure_data "uv" "https://astral.sh/uv/install.sh" "latest" "$manual_steps" "curl install script failed"
  log_error "uv installation failed"
  exit 1
fi

# Add to PATH for current session
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
if command -v uv >/dev/null 2>&1; then
  log_success "uv installed: $(uv --version)"
else
  manual_steps="Binary installed but not in PATH.

Add to PATH:
   export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify:
   uv --version"

  output_failure_data "uv" "https://astral.sh/uv/install.sh" "latest" "$manual_steps" "Not found in PATH after installation"
  log_error "uv not found in PATH"
  exit 1
fi

# Install Python 3.13 as default (uv skips if already installed)
log_info "Installing Python 3.13 as default..."
uv python install --preview-features python-install-default --default 3.13
log_success "Python 3.13 configured as default"
