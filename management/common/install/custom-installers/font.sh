#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

INSTALL_DIR="$HOME/.local/share/font"

if [[ -d "$INSTALL_DIR/.git" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
  log_success "font already installed at $INSTALL_DIR"
  exit 0
fi

log_info "Installing font via official installer..."

if curl -fsSL https://raw.githubusercontent.com/datapointchris/font/main/install.sh | bash; then
  log_success "font installed: $(command -v font 2>/dev/null || echo "$HOME/.local/bin/font")"
else
  log_error "font installation failed"
  exit 1
fi
