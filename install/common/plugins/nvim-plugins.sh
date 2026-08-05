#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

log_info "Installing Neovim plugins via Lazy.nvim..."

# Lazy's headless output is every plugin's raw git and build spew, which is far
# too much to watch — but sending all of it to a file left a fresh install
# cloning fifty repos with nothing on screen for minutes. The full log still
# goes to the file the failure path reports; the terminal gets the one line
# Lazy prints as each plugin task starts, which is the progress signal.
#
# Lazy colors its own prefix whatever headless.colors says, so the filter has to
# strip escape codes before it can see the ` | ` separating prefix from message.
nvim_output=$(mktemp)
if nvim --headless -c "Lazy! sync" -c "qa" 2>&1 \
  | tee "$nvim_output" \
  | awk '{ gsub(/\033\[[0-9;]*m/, ""); if (sub(/ \| Running task .*/, "")) print "  " $0 }'; then
  log_success "Neovim plugins synced"
  if [[ "${DEBUG:-}" == "true" ]]; then
    cat "$nvim_output"
  fi
  rm -f "$nvim_output"
else
  output_failure_data "neovim-plugins" "" "latest" "Lazy.nvim plugin sync failed" "$(<"$nvim_output")"
  log_warning "Neovim plugin installation failed (see summary)"
  log_warning "Full output:"
  cat "$nvim_output" >&2
  rm -f "$nvim_output"
fi
