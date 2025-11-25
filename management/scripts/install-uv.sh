#!/usr/bin/env bash
# ================================================================
# Install uv Python Package Manager
# ================================================================
# Universal script for all platforms
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

print_banner "Installing uv"

if [[ "${FORCE_INSTALL:-false}" != "true" ]] && command -v uv >/dev/null 2>&1; then
  print_success "uv already installed: $(uv --version)"
else
  print_info "Installing uv Python package manager..."
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Add to PATH for current session
  export PATH="$HOME/.local/bin:$PATH"

  print_success "uv installed: $(uv --version)"
fi
