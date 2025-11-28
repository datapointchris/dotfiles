#!/usr/bin/env bash
# ================================================================
# Install zk from GitHub Releases
# ================================================================
# Downloads and installs zk note-taking assistant
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/zk
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
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=zk --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    PLATFORM="macos"
    PLATFORM_ARCH="x86_64"
  else
    PLATFORM="macos"
    PLATFORM_ARCH="arm64"
  fi
else
  PLATFORM="linux"
  ARCH=$(uname -m)
  if [[ "$ARCH" == "aarch64" ]]; then
    PLATFORM_ARCH="arm64"
  else
    PLATFORM_ARCH="amd64"
  fi
fi

ZK_BIN="$HOME/.local/bin/zk"

print_banner "Installing zk"

# Check if zk is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$ZK_BIN" ]] && command -v zk >/dev/null 2>&1; then
  CURRENT_VERSION=$(zk --version 2>&1 | head -n1 || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$ZK_BIN" ]] && command -v zk >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v zk)
  print_warning " zk found at $ALTERNATE_LOCATION"
  print_info "Installing to $ZK_BIN anyway (PATH priority will use this one)"
fi

# Download URL
ZK_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/zk-${LATEST_VERSION}-${PLATFORM}-${PLATFORM_ARCH}.tar.gz"
ZK_TARBALL="/tmp/zk.tar.gz"

# Download
if ! download_file "$ZK_URL" "$ZK_TARBALL" "zk"; then
  print_manual_install "zk" "$ZK_URL" "$LATEST_VERSION" "zk-${LATEST_VERSION}-${PLATFORM}-${PLATFORM_ARCH}.tar.gz" \
    "tar -xzf ~/Downloads/zk-${LATEST_VERSION}-${PLATFORM}-${PLATFORM_ARCH}.tar.gz -C /tmp && mv /tmp/zk ~/.local/bin/ && chmod +x ~/.local/bin/zk"
  exit 1
fi

# Extract
print_info "Extracting..."
tar -xzf "$ZK_TARBALL" -C /tmp

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/zk "$ZK_BIN"
chmod +x "$ZK_BIN"

# Cleanup
rm -f "$ZK_TARBALL"

# Verify installation
if command -v zk >/dev/null 2>&1; then
  INSTALLED_VERSION=$(zk --version 2>&1 | head -n1 || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - zk command not found in PATH"
  exit 1
fi
