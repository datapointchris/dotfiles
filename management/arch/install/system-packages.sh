#!/usr/bin/env bash
# ================================================================
# Install Arch Linux System Packages
# ================================================================
# Installs system packages from packages.yml via pacman
# Includes yay AUR helper installation
# Arch Linux-specific
# ================================================================

set -euo pipefail

# Use DOTFILES_DIR if set (by install.sh), otherwise default to ~/dotfiles
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

# Source formatting library
export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_section "Installing Arch Linux packages" "cyan"

log_info "Updating package database..."
sudo pacman -Sy

# Bootstrap: Install python-yaml first (needed for parse-packages.py)
log_info "Installing bootstrap packages..."
sudo pacman -S --needed --noconfirm python-yaml

# Install system packages from packages.yml
log_info "Installing system packages from packages.yml..."
PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --type=system --manager=pacman | tr '\n' ' ')
log_info "Packages: $PACKAGES"
sudo pacman -S --needed --noconfirm "$PACKAGES"

# Fix library linking issues
log_info "Fixing library links..."
# Fix pcre2 version symbols for git
sudo pacman -S --noconfirm pcre2 2>/dev/null || true
# Rebuild library cache to ensure proper linking
sudo ldconfig 2>/dev/null || true
log_success "Library links fixed"

# Install yay AUR helper
if command -v yay >/dev/null 2>&1; then
  log_info "yay already installed"
else
  log_info "Installing yay AUR helper..."
  cd /tmp
  git clone https://aur.archlinux.org/yay.git
  cd yay
  makepkg -si --noconfirm
  cd ~
  rm -rf /tmp/yay
  log_success "yay installed"
fi

log_success "Arch packages installed"
