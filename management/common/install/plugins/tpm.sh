#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

TPM_DIR="$HOME/.config/tmux/plugins/tpm"

if [[ -d "$TPM_DIR" ]]; then
  log_success "TPM already installed: $TPM_DIR"
else
  log_info "Installing TPM..."
  git clone https://github.com/tmux-plugins/tpm "$TPM_DIR"
  log_success "TPM installed: $TPM_DIR"
fi
