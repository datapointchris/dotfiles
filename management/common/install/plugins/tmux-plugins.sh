#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

log_info "Installing tmux plugins..."

TPM_DIR="$HOME/.config/tmux/plugins/tpm"

if [[ -f "$TPM_DIR/bin/install_plugins" ]]; then
  if "$TPM_DIR/bin/install_plugins"; then
    log_success "Tmux plugins installed"
  else
    manual_steps="Run TPM installation manually:
   $TPM_DIR/bin/install_plugins

Or install plugins from within tmux:
   Press prefix + I (capital i) in tmux

Verify TPM is installed:
   ls -la $TPM_DIR"

    output_failure_data "tmux-plugins" "unknown" "latest" "$manual_steps" "TPM plugin installation failed"
    log_warning "Tmux plugin installation failed (see summary)"
  fi
else
  manual_steps="TPM install script not found. Install TPM first:
   bash $DOTFILES_DIR/management/common/install/plugins/tpm.sh

Then run plugin installation:
   $TPM_DIR/bin/install_plugins"

  output_failure_data "tmux-plugins" "unknown" "latest" "$manual_steps" "TPM not found"
  log_error "TPM install script not found at $TPM_DIR/bin/install_plugins"
fi
