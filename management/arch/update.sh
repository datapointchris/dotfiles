#!/usr/bin/env bash
# ================================================================
# Arch Linux-Specific Updates
# ================================================================
# Updates system packages via pacman and AUR via yay
# Called by management/update.sh wrapper
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by update.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Step 1 - System Packages" "cyan"
log_info "Updating system packages..."
sudo pacman -Syu --noconfirm
log_success "System packages updated"
echo ""

print_banner "Step 2 - AUR Packages" "blue"
if command -v yay >/dev/null 2>&1; then
  log_info "Updating AUR packages..."
  yay -Syu --noconfirm
  log_success "AUR packages updated"
else
  log_warning "yay not installed - skipping AUR updates"
fi
echo ""
