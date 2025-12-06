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
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

log_info "Installing tmux plugins..."

TPM_DIR="$HOME/.config/tmux/plugins/tpm"

if [[ -f "$TPM_DIR/bin/install_plugins" ]]; then
  if "$TPM_DIR/bin/install_plugins"; then
    log_success "Tmux plugins installed"
  else
    log_warning "Tmux plugin installation failed"
    log_info "Install manually: $TPM_DIR/bin/install_plugins"
    log_info "Or from within tmux: prefix + I"
  fi
else
  log_error "TPM install script not found at $TPM_DIR/bin/install_plugins"
  log_info "Install TPM first: bash $DOTFILES_DIR/management/common/install/plugins/tpm.sh"
fi
