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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../../utils/install-program-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=yazi --field=repo)

print_banner "Installing Yazi"

# Detect platform and architecture
PLATFORM=$(uname -s)
ARCH=$(uname -m)

case $PLATFORM in
  Darwin)
    if [[ "$ARCH" == "x86_64" ]]; then
      YAZI_TARGET="x86_64-apple-darwin"
    else
      YAZI_TARGET="aarch64-apple-darwin"
    fi
    ;;
  Linux)
    YAZI_TARGET="x86_64-unknown-linux-gnu"
    ;;
  *)
    print_error "Unsupported platform: $PLATFORM"
    exit 1
    ;;
esac

# Install yazi binary if needed
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [ -f "$HOME/.local/bin/yazi" ]; then
  print_success "yazi already installed, skipping"
  exit 0
fi

if [ ! -f "$HOME/.local/bin/yazi" ]; then
  # Check for alternate installations
  if command -v yazi >/dev/null 2>&1; then
    ALTERNATE_LOCATION=$(command -v yazi)
    print_warning " yazi found at $ALTERNATE_LOCATION"
    print_info "Installing to ~/.local/bin/yazi anyway (PATH priority will use this one)"
  fi

  # Fetch latest version
  print_info "Fetching latest version..."
  YAZI_VERSION=$(get_latest_github_release "$REPO")
  if [[ -z "$YAZI_VERSION" ]]; then
    print_manual_install "yazi" "https://github.com/${REPO}/releases/latest" "latest" "yazi-${YAZI_TARGET}.zip" \
      "unzip ~/Downloads/yazi-${YAZI_TARGET}.zip -d /tmp && mv /tmp/yazi-${YAZI_TARGET}/yazi ~/.local/bin/ && mv /tmp/yazi-${YAZI_TARGET}/ya ~/.local/bin/"
    exit 1
  fi

  print_info "Target: $YAZI_VERSION ($PLATFORM/$ARCH → $YAZI_TARGET)"
  YAZI_URL="https://github.com/${REPO}/releases/download/${YAZI_VERSION}/yazi-${YAZI_TARGET}.zip"

  # Download
  print_info "Downloading..."
  YAZI_ZIP="/tmp/yazi.zip"
  if ! download_file "$YAZI_URL" "$YAZI_ZIP" "yazi"; then
    print_manual_install "yazi" "$YAZI_URL" "$YAZI_VERSION" "yazi-${YAZI_TARGET}.zip" \
      "unzip ~/Downloads/yazi-${YAZI_TARGET}.zip -d /tmp && mv /tmp/yazi-${YAZI_TARGET}/yazi ~/.local/bin/ && mv /tmp/yazi-${YAZI_TARGET}/ya ~/.local/bin/"
    exit 1
  fi

  # Extract and install
  print_info "Installing to ~/.local/bin..."
  cd /tmp
  unzip -q yazi.zip
  mkdir -p ~/.local/bin
  mv "yazi-${YAZI_TARGET}/yazi" ~/.local/bin/
  mv "yazi-${YAZI_TARGET}/ya" ~/.local/bin/
  rm -rf yazi.zip "yazi-${YAZI_TARGET}"

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
