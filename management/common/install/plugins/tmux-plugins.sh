#!/usr/bin/env bash
# ================================================================
# Install Tmux Plugins via TPM
# ================================================================
# Universal script for all platforms
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/management/common/lib/structured-logging.sh"

print_info "Installing tmux plugins..."

TPM_DIR="$HOME/.config/tmux/plugins/tpm"

if [[ -f "$TPM_DIR/bin/install_plugins" ]]; then
  "$TPM_DIR/bin/install_plugins"
  print_success "Tmux plugins installed"
else
  print_error "TPM install script not found at $TPM_DIR/bin/install_plugins"
  exit 1
fi
