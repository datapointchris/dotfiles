#!/usr/bin/env bash
# ================================================================
# Install Yazi from GitHub Releases
# ================================================================
# Downloads and installs latest Yazi release with flavors/plugins
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/yazi
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
source "$(dirname "$0")/install-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=yazi --field=repo)

print_banner "Installing Yazi"

# Install yazi binary if needed
if ! command -v yazi >/dev/null 2>&1; then
  # Fetch latest version
  print_info "Fetching latest version..."
  YAZI_VERSION=$(fetch_latest_version "$REPO")
  if [[ -z "$YAZI_VERSION" ]]; then
    print_manual_install "yazi" "https://github.com/${REPO}/releases/latest" "latest" "yazi-x86_64-unknown-linux-gnu.zip" \
      "unzip ~/Downloads/yazi-x86_64-unknown-linux-gnu.zip -d /tmp && mv /tmp/yazi-x86_64-unknown-linux-gnu/yazi ~/.local/bin/ && mv /tmp/yazi-x86_64-unknown-linux-gnu/ya ~/.local/bin/"
    exit 1
  fi

  YAZI_URL="https://github.com/${REPO}/releases/download/${YAZI_VERSION}/yazi-x86_64-unknown-linux-gnu.zip"

  # Download
  print_info "Downloading..."
  YAZI_ZIP="/tmp/yazi.zip"
  if ! download_file "$YAZI_URL" "$YAZI_ZIP" "yazi"; then
    print_manual_install "yazi" "$YAZI_URL" "$YAZI_VERSION" "yazi-x86_64-unknown-linux-gnu.zip" \
      "unzip ~/Downloads/yazi-x86_64-unknown-linux-gnu.zip -d /tmp && mv /tmp/yazi-x86_64-unknown-linux-gnu/yazi ~/.local/bin/ && mv /tmp/yazi-x86_64-unknown-linux-gnu/ya ~/.local/bin/"
    exit 1
  fi

  # Extract and install
  print_info "Installing to ~/.local/bin..."
  cd /tmp
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

print_info "Installing flavors..."
ya pkg add BennyOe/tokyo-night || true
ya pkg add dangooddd/kanagawa || true
ya pkg add bennyyip/gruvbox-dark || true
ya pkg add kmlupreti/ayu-dark || true
ya pkg add Chromium-3-Oxide/everforest-medium || true
ya pkg add gosxrgxx/flexoki-dark || true

print_info "Installing plugins..."
ya pkg add AnirudhG07/nbpreview || true
ya pkg add pirafrank/what-size || true
ya pkg add yazi-rs/plugins:git || true

print_banner "Yazi installation complete"
