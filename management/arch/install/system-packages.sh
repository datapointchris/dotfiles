#!/usr/bin/env bash
set -euo pipefail

# NOTE: Use exported DOTFILES_DIR from install.sh for consistency.
DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_section "Installing Arch Linux packages"

log_info "Performing full system upgrade (Arch best practice)..."
sudo pacman -Syu --noconfirm

# Bootstrap: Install python-yaml first (needed for parse_packages.py)
log_info "Installing bootstrap packages..."
sudo pacman -S --needed --noconfirm python-yaml

# Install system packages from packages.yml
log_info "Installing system packages from packages.yml..."
PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=system --manager=pacman | tr '\n' ' ')
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

# Install AUR packages
log_info "Installing AUR packages from packages.yml..."

# Ensure gnupg directory exists (required for AUR package signature verification)
# Match XDG location set in .zshrc: GNUPGHOME="$XDG_DATA_HOME/gnupg"
export GNUPGHOME="${XDG_DATA_HOME:-$HOME/.local/share}/gnupg"
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

AUR_PACKAGES=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=system --manager=aur | tr '\n' ' ')
if [[ -n "$AUR_PACKAGES" ]]; then
  # shellcheck disable=SC2086
  yay -S --needed --noconfirm $AUR_PACKAGES
  log_success "AUR packages installed"
else
  log_info "No AUR packages to install"
fi

log_success "Arch packages installed"

# Configure TTY1 auto-login for Hyprland
print_section "Configuring TTY auto-login"

# Disable GDM if enabled (has issues with Hyprland)
if systemctl is-enabled gdm &>/dev/null; then
  log_info "Disabling GDM (using TTY auto-login instead)..."
  sudo systemctl disable gdm
  log_success "GDM disabled"
fi

# Enable auto-login on TTY1
log_info "Configuring auto-login on TTY1..."
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf >/dev/null << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty -o '-p -f -- \\u' --noclear --autologin chris %I $TERM
EOF
log_success "TTY1 auto-login configured"

log_success "Arch system configuration complete"
