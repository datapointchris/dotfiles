#!/usr/bin/env bash
# ================================================================
# macOS-Specific Updates
# ================================================================
# Updates Homebrew packages and Mac App Store apps
# Called by management/update.sh wrapper
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by update.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Step 1 - Homebrew" "cyan"
log_info "Updating Homebrew..."
brew update
log_info "Upgrading formulas and casks..."
brew upgrade
brew upgrade --cask --greedy
log_success "Homebrew packages updated"
echo ""

print_banner "Step 2 - Mac App Store" "blue"
if ! command -v mas >/dev/null 2>&1; then
  log_warning "mas not found - install with: brew install mas"
else
  log_info "Updating Mac App Store apps..."
  if mas upgrade 2>&1; then
    log_success "Mac App Store apps updated"
  else
    log_warning "Update failed (mas may be incompatible with your macOS version)"
    log_info "You can update apps manually via the App Store GUI"
  fi
fi
echo ""
