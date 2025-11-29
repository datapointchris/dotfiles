#!/usr/bin/env bash
# ================================================================
# Install Tmux Plugins via TPM
# ================================================================
# Universal script for all platforms
# ================================================================

set -euo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

log_info "Installing tmux plugins..."

TPM_DIR="$HOME/.config/tmux/plugins/tpm"

if [[ -f "$TPM_DIR/bin/install_plugins" ]]; then
  "$TPM_DIR/bin/install_plugins"
  log_success "Tmux plugins installed"
else
  log_error "TPM install script not found at $TPM_DIR/bin/install_plugins"
  exit 1
fi
