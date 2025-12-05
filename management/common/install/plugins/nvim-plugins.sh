#!/usr/bin/env bash
# ================================================================
# Install Neovim Plugins via Lazy.nvim
# ================================================================
# Universal script for all platforms
# Runs nvim in headless mode to install all plugins
# ================================================================

set -euo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

print_banner "Installing Neovim Plugins"

log_info "Installing Neovim plugins via Lazy.nvim..."

# Run nvim headless to install all plugins
# --headless: run without UI
# +Lazy! sync: sync all plugins
# +qa: quit all windows
if nvim --headless "+Lazy! sync" +qa 2>&1 | grep -v "^$"; then
  log_success "Neovim plugins installed"
else
  # Report failure
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="Install plugins manually from within Neovim:
   nvim
   :Lazy sync

Or run headless again:
   nvim --headless \"+Lazy! sync\" +qa

Check Neovim config:
   nvim --version
   ls -la ~/.config/nvim"
    report_failure "neovim-plugins" "unknown" "latest" "$manual_steps" "Lazy.nvim plugin sync failed"
  fi
  log_warning "Neovim plugin installation failed (see summary)"
fi
