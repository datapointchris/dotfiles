#!/usr/bin/env bash
# ================================================================
# Install Mac App Store Apps
# ================================================================
# Installs Mac App Store apps from packages.yml using mas CLI
# macOS-specific
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by install.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

print_section "Installing Mac App Store apps" "cyan"

# Check if mas is installed
if ! command -v mas >/dev/null 2>&1; then
  print_warning "mas not found - install with: brew install mas"
  echo "  ℹ️  Apps can be manually installed via the App Store GUI"
  exit 0
fi

# Check if signed in
if ! mas account >/dev/null 2>&1; then
  print_warning "Not signed into Mac App Store"
  echo "  ℹ️  Sign in via System Settings > Apple ID"
  echo "  ℹ️  Apps can be manually installed via the App Store GUI"
  exit 0
fi

INSTALLED=0
FAILED=0
SKIPPED=0

# Install each app
/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=mas | while read -r app_id; do
  # Check if already installed
  if mas list | grep -q "^$app_id "; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  echo "  Installing app ID: $app_id..."
  if mas install "$app_id" 2>&1; then
    INSTALLED=$((INSTALLED + 1))
    echo "    ✓ Installed"
  else
    FAILED=$((FAILED + 1))
    echo "    ✗ Failed (possibly requires manual purchase or macOS compatibility issue)"
  fi
done

echo ""
echo "  Summary:"
[ $INSTALLED -gt 0 ] && echo "    Installed: $INSTALLED"
[ $SKIPPED -gt 0 ] && echo "    Already installed: $SKIPPED"
[ $FAILED -gt 0 ] && echo "    Failed: $FAILED (can install manually via App Store)"
echo ""
echo "  ℹ️  Note: mas may fail on certain macOS versions (15.7.2, 26.1+)"
echo "  ℹ️  Failed apps can be manually installed via the App Store GUI"

print_success "Mac App Store installation complete"
