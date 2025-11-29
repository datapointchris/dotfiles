#!/usr/bin/env bash
# ================================================================
# Arch Linux-Specific Updates
# ================================================================
# Updates system packages via pacman and AUR via yay
# Called by management/update.sh wrapper
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

print_banner "Step 1 - System Packages" "cyan"
echo "  Updating system packages..."
sudo pacman -Syu --noconfirm
echo "  ✓ System packages updated"
echo ""

print_banner "Step 2 - AUR Packages" "blue"
if command -v yay >/dev/null 2>&1; then
  echo "  Updating AUR packages..."
  yay -Syu --noconfirm
  echo "  ✓ AUR packages updated"
else
  echo "  ⚠️  yay not installed - skipping AUR updates"
fi
echo ""
