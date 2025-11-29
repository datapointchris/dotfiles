#!/usr/bin/env bash
# ================================================================
# WSL-Specific Updates
# ================================================================
# Updates system packages via apt
# Called by management/update.sh wrapper
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

print_banner "Step 1 - System Packages" "cyan"
echo "  Updating system packages..."
sudo apt update && sudo apt upgrade -y
echo "  ✓ System packages updated"
echo ""
