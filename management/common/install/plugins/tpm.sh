#!/usr/bin/env bash
# ================================================================
# Install Tmux Plugin Manager (TPM)
# ================================================================
# Universal script for all platforms
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/management/common/lib/structured-logging.sh"

TPM_DIR="$HOME/.config/tmux/plugins/tpm"

if [[ -d "$TPM_DIR" ]]; then
  print_success "TPM already installed"
else
  print_info "Installing TPM..."
  git clone https://github.com/tmux-plugins/tpm "$TPM_DIR"
  print_success "TPM installed"
fi
