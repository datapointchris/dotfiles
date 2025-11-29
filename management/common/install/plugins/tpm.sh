#!/usr/bin/env bash
# ================================================================
# Install Tmux Plugin Manager (TPM)
# ================================================================
# Universal script for all platforms
# ================================================================

set -euo pipefail

# Source formatting library
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

TPM_DIR="$HOME/.config/tmux/plugins/tpm"

if [[ -d "$TPM_DIR" ]]; then
  log_success "TPM already installed"
else
  log_info "Installing TPM..."
  git clone https://github.com/tmux-plugins/tpm "$TPM_DIR"
  log_success "TPM installed"
fi
