#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

INSTALL_DIR="$HOME/tools/font"
REPO="https://github.com/datapointchris/font.git"

if [[ -d "$INSTALL_DIR/.git" ]] && [[ "${FORCE_INSTALL:-}" != "true" ]]; then
  log_success "font already installed at $INSTALL_DIR"
  exit 0
fi

log_info "Installing font..."

mkdir -p "$HOME/tools"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  log_info "Updating existing installation..."
  if git -C "$INSTALL_DIR" pull --quiet; then
    log_success "font updated"
  else
    log_warning "font update failed"
  fi
else
  log_info "Cloning font repository..."
  if git clone --quiet "$REPO" "$INSTALL_DIR"; then
    log_success "font cloned to $INSTALL_DIR"
  else
    log_error "Failed to clone font repository"
    exit 1
  fi
fi

log_info "Creating symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/bin/font" "$HOME/.local/bin/font"
log_success "font installed: $(command -v font 2>/dev/null || echo "$HOME/.local/bin/font")"
