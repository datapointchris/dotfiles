#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

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
# shellcheck disable=SC2086
sudo pacman -S --needed --noconfirm $PACKAGES

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
