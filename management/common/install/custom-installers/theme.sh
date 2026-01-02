#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

INSTALL_DIR="$HOME/tools/theme"
REPO="https://github.com/datapointchris/theme.git"

if [[ -d "$INSTALL_DIR/.git" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
  log_success "theme already installed at $INSTALL_DIR"
  exit 0
fi

log_info "Installing theme..."

mkdir -p "$HOME/tools"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  log_info "Updating existing installation..."
  if git -C "$INSTALL_DIR" pull --quiet; then
    log_success "theme updated"
  else
    log_warning "theme update failed"
  fi
else
  log_info "Cloning theme repository..."
  if git clone --quiet "$REPO" "$INSTALL_DIR"; then
    log_success "theme cloned to $INSTALL_DIR"
  else
    log_error "Failed to clone theme repository"
    exit 1
  fi
fi

log_info "Creating symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/bin/theme" "$HOME/.local/bin/theme"
log_success "theme installed: $(command -v theme 2>/dev/null || echo "$HOME/.local/bin/theme")"
