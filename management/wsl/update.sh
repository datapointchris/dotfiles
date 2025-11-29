#!/usr/bin/env bash
# ================================================================
# WSL-Specific Updates
# ================================================================
# Updates system packages via apt
# Called by management/update.sh wrapper
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by update.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_banner "Step 1 - System Packages" "cyan"
echo "  Updating system packages..."
sudo apt update && sudo apt upgrade -y
echo "  ✓ System packages updated"
echo ""
