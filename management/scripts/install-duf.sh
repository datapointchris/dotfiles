#!/usr/bin/env bash
# ================================================================
# Install Duf from GitHub Releases
# ================================================================
# Downloads and installs Duf disk usage utility
# Configuration read from: management/packages.yml
# Installation location: ~/.local/bin/duf
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source formatting library
source "$HOME/dotfiles/platforms/common/shell/formatting.sh"

# Source helper functions
source "$(dirname "$0")/install-program-helpers.sh"

# Read configuration from packages.yml
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
REPO=$(/usr/bin/python3 "$DOTFILES_DIR/management/parse-packages.py" --github-binary=duf --field=repo)

# Detect platform and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
  ARCH=$(uname -m)
  if [[ "$ARCH" == "x86_64" ]]; then
    PLATFORM_ARCH="darwin_amd64"
  else
    PLATFORM_ARCH="darwin_arm64"
  fi
else
  PLATFORM_ARCH="linux_x86_64"
fi

DUF_BIN="$HOME/.local/bin/duf"

print_banner "Installing Duf"

# Check if Duf is already installed (skip check if FORCE_INSTALL=true)
if [[ "${FORCE_INSTALL:-false}" != "true" ]] && [[ -f "$DUF_BIN" ]] && command -v duf >/dev/null 2>&1; then
  CURRENT_VERSION=$(duf --version 2>&1 | head -n1 || echo "unknown")
  print_success "Current version: $CURRENT_VERSION, skipping"
  exit 0
fi

# Get latest version from GitHub API
LATEST_VERSION=$(get_latest_github_release "$REPO")
print_info "Target version: $LATEST_VERSION"

# Check for alternate installations
if [[ ! -f "$DUF_BIN" ]] && command -v duf >/dev/null 2>&1; then
  ALTERNATE_LOCATION=$(command -v duf)
  print_warning " duf found at $ALTERNATE_LOCATION"
  print_info "Installing to $DUF_BIN anyway (PATH priority will use this one)"
fi

# Download URL
DUF_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/duf_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz"
DUF_TARBALL="/tmp/duf.tar.gz"

# Download
if ! download_file "$DUF_URL" "$DUF_TARBALL" "duf"; then
  print_manual_install "duf" "$DUF_URL" "$LATEST_VERSION" "duf_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz" \
    "tar -xzf ~/Downloads/duf_${LATEST_VERSION#v}_${PLATFORM_ARCH}.tar.gz -C /tmp && mv /tmp/duf ~/.local/bin/ && chmod +x ~/.local/bin/duf"
  exit 1
fi

# Extract
print_info "Extracting..."
tar -xzf "$DUF_TARBALL" -C /tmp duf

# Install
print_info "Installing to ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
mv /tmp/duf "$DUF_BIN"
chmod +x "$DUF_BIN"

# Cleanup
rm -f "$DUF_TARBALL"

# Verify installation
if command -v duf >/dev/null 2>&1; then
  INSTALLED_VERSION=$(duf --version 2>&1 | head -n1 || echo "unknown")
  print_success "Installed: $INSTALLED_VERSION"
else
  print_error "Installation failed - duf command not found in PATH"
  exit 1
fi
