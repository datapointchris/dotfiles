#!/usr/bin/env bash
# ================================================================
# Install Glow from GitHub Releases
# ================================================================
# Downloads and installs Glow markdown renderer
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/glow
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../lib/program-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=glow --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    PLATFORM_ARCH="Darwin_x86_64"
  else
    PLATFORM_ARCH="Darwin_arm64"
  fi
else
  PLATFORM_ARCH="Linux_x86_64"
fi

GLOW_BIN="$HOME/.local/bin/glow"

print_banner "Installing Glow"

# Check if Glow is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$GLOW_BIN" ]] && command -v glow >/dev/null 2>&1; then
  CURRENT_VERSION=$(glow --version 2>&1 | head -n1 || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$GLOW_BIN" ]] && command -v glow >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v glow)
  print_warning " glow found at $ALTERNATE_LOCATION"
  print_info "Installing to $GLOW_BIN anyway (PATH priority will use this one)"
fi

# Download URL
GLOW_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/glow_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz"
GLOW_TARBALL="/tmp/glow.tar.gz"

# Download
if ! download_file "$GLOW_URL" "$GLOW_TARBALL" "glow"; then
  print_manual_install "glow" "$GLOW_URL" "$LATEST_VERSION" "glow_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz" \
    "tar -xzf ~/Downloads/glow_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz -C /tmp && mv /tmp/glow ~/.local/bin/ && chmod +x ~/.local/bin/glow"
  exit 1
fi

# Extract
print_info "Extracting..."
tar -xzf "$GLOW_TARBALL" -C /tmp

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/glow_*_${PLATFORM_ARCH}/glow "$GLOW_BIN"
chmod +x "$GLOW_BIN"

# Cleanup
rm -f "$GLOW_TARBALL"

# Verify installation
if command -v glow >/dev/null 2>&1; then
  INSTALLED_VERSION=$(glow --version 2>&1 | head -n1 || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - glow command not found in PATH"
  exit 1
fi
