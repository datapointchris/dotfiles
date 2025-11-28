#!/usr/bin/env bash
# ================================================================
# Setup Xcode
# ================================================================
# Accept Xcode license and run first launch setup
# macOS-specific
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

if ! command -v xcodebuild &>/dev/null; then
  print_warning "Xcode not installed (install via: mas install 497799835)"
  exit 0
fi

print_section "Setting up Xcode" "cyan"

# Check if license is already accepted
if sudo -n xcodebuild -license status &>/dev/null; then
  echo "  ✓ Xcode license already accepted"
else
  print_warning "Xcode license not accepted"
  echo "  ℹ️  Run manually: sudo xcodebuild -license accept"
  exit 0
fi

# Run first launch setup
echo "  Running first launch setup..."
xcodebuild -runFirstLaunch 2>/dev/null || true

print_success "Xcode setup complete"
