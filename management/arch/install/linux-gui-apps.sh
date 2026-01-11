#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"

export TERM=${TERM:-xterm}
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"

print_section "Installing Linux GUI apps (Flatpak)"

if ! command -v flatpak &>/dev/null; then
  log_info "Installing flatpak..."
  sudo pacman -S --needed --noconfirm flatpak
  log_success "Flatpak installed"
fi

log_info "Adding Flathub repository..."
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

log_info "Installing GUI apps from packages.yml..."
APPS=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse_packages.py" --type=linux-gui)

for app in $APPS; do
  if flatpak list --app | grep -q "$app"; then
    log_success "$app already installed"
  else
    log_info "Installing $app..."
    if flatpak install -y flathub "$app"; then
      log_success "$app installed"
    else
      log_warning "$app installation failed"
    fi
  fi
done

log_success "Linux GUI apps installed"
