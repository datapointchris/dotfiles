#!/usr/bin/env bash
# ================================================================
# Install Neovim Plugins via Lazy.nvim
# ================================================================
# Universal script for all platforms
# Runs nvim in headless mode to install all plugins
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

print_banner "Installing Neovim Plugins"

print_info "Installing Neovim plugins via Lazy.nvim..."

# Run nvim headless to install all plugins
# --headless: run without UI
# +Lazy! sync: sync all plugins
# +qa: quit all windows
nvim --headless "+Lazy! sync" +qa 2>&1 | grep -v "^$" || true

print_success "Neovim plugins installed"
