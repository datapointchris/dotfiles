#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

log_info "Installing Neovim plugins via Lazy.nvim..."

# Run nvim headless to install all plugins
# --headless: run without UI
# +Lazy! sync: sync all plugins (! suppresses the UI)
# +qa: quit all windows
# Output is captured and only shown on failure or in DEBUG mode
nvim_output=$(mktemp)
if nvim --headless "+Lazy! sync" +qa &>"$nvim_output"; then
  log_success "Neovim plugins synced"
  if [[ "${DEBUG:-}" == "true" ]]; then
    cat "$nvim_output"
  fi
  rm -f "$nvim_output"
else
  manual_steps="Install plugins manually from within Neovim:
   nvim
   :Lazy sync

Or run headless again:
   nvim --headless \"+Lazy! sync\" +qa

Check Neovim config:
   nvim --version
   ls -la ~/.config/nvim"

  output_failure_data "neovim-plugins" "unknown" "latest" "$manual_steps" "Lazy.nvim plugin sync failed"
  log_warning "Neovim plugin installation failed (see summary)"
  log_warning "Full output:"
  cat "$nvim_output"
  rm -f "$nvim_output"
fi
