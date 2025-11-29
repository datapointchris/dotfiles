#!/usr/bin/env bash
# ================================================================
# Install WSL Ubuntu System Packages
# ================================================================
# Installs system packages from packages.yml via apt
# WSL Ubuntu-specific
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by install.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"

print_section "Installing WSL Ubuntu packages" "cyan"

echo "  Updating package lists..."
sudo apt update

# Bootstrap: Install python3-yaml first (needed for parse-packages.py)
echo "  Installing bootstrap packages..."
sudo apt install -y python3-yaml

# Install system packages from packages.yml
echo "  Installing system packages from packages.yml..."
PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=system --manager=apt | tr '\n' ' ')
echo "  Packages: $PACKAGES"

if sudo apt install -y "$PACKAGES"; then
  print_success "WSL packages installed"
else
  print_warning "Some packages may have failed to install"
fi
