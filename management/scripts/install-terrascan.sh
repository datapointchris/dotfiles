#!/usr/bin/env bash
# ================================================================
# Install terrascan from GitHub Releases
# ================================================================
# Downloads and installs Terrascan (Terraform security scanner)
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/terrascan
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
source "$(dirname "$0")/install-program-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=terrascan --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="Darwin"
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    ARCH="x86_64"
  elif [[ "$ARCH" == "arm64" ]]; then
    ARCH="arm64"
  fi
else
  PLATFORM="Linux"
  ARCH="x86_64"
fi

TERRASCAN_BIN="$HOME/.local/bin/terrascan"

print_banner "Installing terrascan"

# Check if terrascan is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$TERRASCAN_BIN" ]] && command -v terrascan >/dev/null 2>&1; then
  CURRENT_VERSION=$(terrascan version 2>&1 | grep -oP 'version.*' || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$TERRASCAN_BIN" ]] && command -v terrascan >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v terrascan)
  print_warning " terrascan found at $ALTERNATE_LOCATION"
  print_info "Installing to $TERRASCAN_BIN anyway (PATH priority will use this one)"
fi

# Download URL
TERRASCAN_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/terrascan_${LATEST_VERSION#v}_${PLATFORM}_${ARCH}.tar.gz"
TERRASCAN_TARBALL="/tmp/terrascan.tar.gz"

# Download
if ! download_file "$TERRASCAN_URL" "$TERRASCAN_TARBALL" "terrascan"; then
  print_manual_install "terrascan" "$TERRASCAN_URL" "$LATEST_VERSION" "terrascan_${LATEST_VERSION#v}_${PLATFORM}_${ARCH}.tar.gz" \
    "tar -xzf ~/Downloads/terrascan_${LATEST_VERSION#v}_${PLATFORM}_${ARCH}.tar.gz -C /tmp && mv /tmp/terrascan ~/.local/bin/ && chmod +x ~/.local/bin/terrascan"
  exit 1
fi

# Extract
print_info "Extracting..."
tar -xzf "$TERRASCAN_TARBALL" -C /tmp

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/terrascan "$TERRASCAN_BIN"
chmod +x "$TERRASCAN_BIN"

# Cleanup
rm -f "$TERRASCAN_TARBALL"

# Verify installation
if command -v terrascan >/dev/null 2>&1; then
  INSTALLED_VERSION=$(terrascan version 2>&1 | grep -oP 'version.*' || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - terrascan command not found in PATH"
  exit 1
fi
