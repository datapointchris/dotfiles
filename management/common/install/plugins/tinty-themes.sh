#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

if ! command -v tinty >/dev/null 2>&1; then
  manual_steps="Install tinty first:
   Visit: https://github.com/tinted-theming/tinty

Or use cargo:
   cargo install tinty

Then run:
   bash $DOTFILES_DIR/management/common/install/plugins/tinty-themes.sh"

  output_failure_data "tinty-themes" "https://github.com/tinted-theming/tinty" "latest" "$manual_steps" "tinty not found in PATH"
  log_error "tinty not found - install tinty first"
  exit 1
fi

log_info "Installing theme repositories..."
source "$HOME/.cargo/env"

INSTALL_OUTPUT=$(tinty install 2>&1)
echo "$INSTALL_OUTPUT" | while IFS= read -r line; do
  if [[ "$line" =~ "already installed" ]]; then
    log_success "$line"
  elif [[ "$line" =~ "installed" ]]; then
    log_success "$line"
  elif [[ -n "$line" ]]; then
    log_info "$line"
  fi
done

if echo "$INSTALL_OUTPUT" | grep -qi "error\|fail"; then
  manual_steps="Run tinty install manually:
   source ~/.cargo/env
   tinty install

Check tinty status:
   tinty --version
   tinty list"

  output_failure_data "tinty-themes" "https://github.com/tinted-theming/tinty" "latest" "$manual_steps" "tinty install failed"
  log_warning "tinty install encountered issues (see summary)"
else
  log_success "Theme repositories installed"
fi

log_info "Syncing current theme..."

SYNC_OUTPUT=$(tinty sync 2>&1)
echo "$SYNC_OUTPUT" | while IFS= read -r line; do
  if [[ "$line" =~ "up to date" ]]; then
    log_success "$line"
  elif [[ -n "$line" ]]; then
    log_info "$line"
  fi
done

if echo "$SYNC_OUTPUT" | grep -qi "error\|fail"; then
  manual_steps="Run tinty sync manually:
   source ~/.cargo/env
   tinty sync

Apply a theme manually:
   tinty apply rose-pine

Check current theme:
   tinty current"

  output_failure_data "tinty-themes" "https://github.com/tinted-theming/tinty" "latest" "$manual_steps" "tinty sync failed"
  log_warning "tinty sync encountered issues (see summary)"
else
  log_success "Theme sync complete"
fi
