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
source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"

log_info "Installing tmux plugins..."

# Initialize failure registry for resilient installation
init_failure_registry

TPM_DIR="$HOME/.config/tmux/plugins/tpm"

if [[ -f "$TPM_DIR/bin/install_plugins" ]]; then
  if "$TPM_DIR/bin/install_plugins"; then
    log_success "Tmux plugins installed"
  else
    # Report failure
    if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
      manual_steps="Run TPM installation manually:
   $TPM_DIR/bin/install_plugins

Or install plugins from within tmux:
   Press prefix + I (capital i) in tmux

Verify TPM is installed:
   ls -la $TPM_DIR"
      report_failure "tmux-plugins" "unknown" "latest" "$manual_steps" "TPM plugin installation failed"
    fi
    log_warning "Tmux plugin installation failed (see summary)"
  fi
else
  # Report failure - TPM not found
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="TPM install script not found. Install TPM first:
   bash $DOTFILES_DIR/management/common/install/plugins/tpm.sh

Then run plugin installation:
   $TPM_DIR/bin/install_plugins"
    report_failure "tmux-plugins" "unknown" "latest" "$manual_steps" "TPM not found"
  fi
  log_error "TPM install script not found at $TPM_DIR/bin/install_plugins"
fi

# Display failure summary if there were any failures
display_failure_summary
