#!/usr/bin/env bash
# ================================================================
# Install Arch Linux System Packages
# ================================================================
# Installs system packages from packages.yml via pacman
# Includes yay AUR helper installation
# Arch Linux-specific
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

print_section "Installing Arch Linux packages" "cyan"

echo "  Updating package database..."
sudo pacman -Sy

# Bootstrap: Install python-yaml first (needed for parse-packages.py)
echo "  Installing bootstrap packages..."
sudo pacman -S --needed --noconfirm python-yaml

# Install system packages from packages.yml
echo "  Installing system packages from packages.yml..."
PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=system --manager=pacman | tr '\n' ' ')
echo "  Packages: $PACKAGES"
sudo pacman -S --needed --noconfirm "$PACKAGES"

# Fix library linking issues
echo "  Fixing library links..."
# Fix pcre2 version symbols for git
sudo pacman -S --noconfirm pcre2 2>/dev/null || true
# Rebuild library cache to ensure proper linking
sudo ldconfig 2>/dev/null || true
echo "  ✓ Library links fixed"

# Install yay AUR helper
if command -v yay >/dev/null 2>&1; then
  echo "  yay already installed"
else
  echo "  Installing yay AUR helper..."
  cd /tmp
  git clone https://aur.archlinux.org/yay.git
  cd yay
  makepkg -si --noconfirm
  cd ~
  rm -rf /tmp/yay
  echo "  ✓ yay installed"
fi

print_success "Arch packages installed"
