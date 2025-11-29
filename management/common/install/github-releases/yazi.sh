#!/usr/bin/env bash
# ================================================================
# Install Yazi from GitHub Releases
# ================================================================
# Downloads and installs Yazi file manager with flavors and plugins
# Configuration: Inline (see variables below)
# Installation location: ~/.local/bin/yazi, ~/.local/bin/ya
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source error handling (includes structured logging)
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps

# Source GitHub release installer library
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

# ================================================================
# Configuration
# ================================================================

BINARY_NAME="yazi"
REPO="sxyazi/yazi"

# Get latest version
LATEST_VERSION=$(get_latest_version "$REPO")

# Detect platform and arch for download URL
# Yazi uses format: yazi-{arch}-{platform}.zip
# Examples: yazi-x86_64-apple-darwin.zip, yazi-aarch64-apple-darwin.zip, yazi-x86_64-unknown-linux-gnu.zip
ARCH=$(uname -m)
if [[ "$OSTYPE" == "darwin"* ]]; then
  YAZI_TARGET="${ARCH}-apple-darwin"
else
  YAZI_TARGET="${ARCH}-unknown-linux-gnu"
fi

# Build download URL
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${LATEST_VERSION}/yazi-${YAZI_TARGET}.zip"

# Installation paths
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
TEMP_ZIP="/tmp/${BINARY_NAME}.zip"
EXTRACT_DIR="/tmp/yazi-${YAZI_TARGET}"

# ================================================================
# Installation
# ================================================================

print_banner "Installing Yazi"

# Check existing installation (simple check, no version comparison)
if check_existing_installation "$TARGET_BIN" "$BINARY_NAME"; then
  log_info "Yazi already installed, proceeding to themes/plugins..."
else
  log_info "Target version: $LATEST_VERSION"

  # Check for alternate installations
  check_alternate_installation "$TARGET_BIN" "$BINARY_NAME"

  # Download
  download_release "$DOWNLOAD_URL" "$TEMP_ZIP" "$BINARY_NAME"

  # Extract (zip file)
  extract_zip "$TEMP_ZIP" "/tmp"

  # Install binaries (yazi and ya)
  log_info "Installing binaries to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"
  mv "${EXTRACT_DIR}/yazi" "$TARGET_BIN"
  mv "${EXTRACT_DIR}/ya" "$HOME/.local/bin/ya"
  chmod +x "$TARGET_BIN" "$HOME/.local/bin/ya"

  # Verify
  verify_installation "$BINARY_NAME" "yazi --version"
  log_success "ya installed successfully"
fi

# ================================================================
# Install Themes and Plugins
# ================================================================

# Configure git to not prompt for credentials (prevents hanging in non-interactive environments)
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

log_info "Installing flavors..."
ya pkg add BennyOe/tokyo-night || true
ya pkg add dangooddd/kanagawa || true
ya pkg add bennyyip/gruvbox-dark || true
ya pkg add kmlupreti/ayu-dark || true
ya pkg add Chromium-3-Oxide/everforest-medium || true
ya pkg add gosxrgxx/flexoki-dark || true

log_info "Installing plugins..."
ya pkg add AnirudhG07/nbpreview || true
ya pkg add pirafrank/what-size || true
ya pkg add yazi-rs/plugins:git || true

print_banner_success "Yazi installation complete"
exit_success
