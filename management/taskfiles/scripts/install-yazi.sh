#!/usr/bin/env bash
set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Install yazi terminal file manager and packages (flavors + plugins)

print_banner "
Installing Yazi"
print_banner "

# Install yazi binary if needed
if ! command -v yazi >/dev/null 2>&1; then
  print_info "Fetching latest version..."
  YAZI_VERSION=$(curl -s https://api.github.com/repos/sxyazi/yazi/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
  YAZI_URL="https://github.com/sxyazi/yazi/releases/download/${YAZI_VERSION}/yazi-x86_64-unknown-linux-gnu.zip"

  print_info "Downloading..."
  cd /tmp
  curl -L "$YAZI_URL" -o yazi.zip

  print_info "Installing to ~/.local/bin..."
  unzip -q yazi.zip
  mkdir -p ~/.local/bin
  mv yazi-x86_64-unknown-linux-gnu/yazi ~/.local/bin/
  mv yazi-x86_64-unknown-linux-gnu/ya ~/.local/bin/
  rm -rf yazi.zip yazi-x86_64-unknown-linux-gnu

  print_success " Yazi and ya installed"
else
  print_success " Yazi already installed"
fi

# Configure git to not prompt for credentials (prevents hanging in non-interactive environments)
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

 Installing flavors..."
ya pkg add BennyOe/tokyo-night || true
ya pkg add dangooddd/kanagawa || true
ya pkg add bennyyip/gruvbox-dark || true
ya pkg add kmlupreti/ayu-dark || true
ya pkg add Chromium-3-Oxide/everforest-medium || true
ya pkg add gosxrgxx/flexoki-dark || true

 Installing plugins..."
ya pkg add AnirudhG07/nbpreview || true
ya pkg add pirafrank/what-size || true
ya pkg add yazi-rs/plugins:git || true

print_banner "
Yazi installation complete"
print_banner "
