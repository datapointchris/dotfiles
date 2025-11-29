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
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"

print_banner "Step 1 - Homebrew" "cyan"
echo "  Updating Homebrew..."
brew update
echo "  Upgrading formulas and casks..."
brew upgrade
brew upgrade --cask --greedy
echo "  ✓ Homebrew packages updated"
echo ""

print_banner "Step 2 - Mac App Store" "blue"
if ! command -v mas >/dev/null 2>&1; then
  echo "  ⚠️  mas not found - install with: brew install mas"
else
  echo "  Updating Mac App Store apps..."
  if mas upgrade 2>&1; then
    echo "  ✓ Mac App Store apps updated"
  else
    echo "  ⚠️  Update failed (mas may be incompatible with your macOS version)"
    echo "  ℹ️  You can update apps manually via the App Store GUI"
  fi
fi
echo ""
