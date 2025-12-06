#!/usr/bin/env bash
# ================================================================
# Install uv Python Package Manager
# ================================================================
# Universal script for all platforms
# ================================================================

set -uo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Installing uv"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v uv >/dev/null 2>&1; then
  log_success "uv already installed: $(uv --version)"
else
  log_info "Installing uv Python package manager..."

  # Set XDG_BIN_HOME to ensure clean install path and prevent shell modification
  XDG_BIN_HOME="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 curl -LsSf https://astral.sh/uv/install.sh | sh

  # Add to PATH for current session
  export PATH="$HOME/.local/bin:$PATH"

  log_success "uv installed: $(uv --version)"
fi

# Install Python 3.13 as default (uv skips if already installed)
log_info "Installing Python 3.13 as default..."
uv python install --preview-features python-install-default --default 3.13
log_success "Python 3.13 configured as default"
