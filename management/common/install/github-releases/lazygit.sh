#!/usr/bin/env bash
# ================================================================
# Install LazyGit from GitHub Releases
# ================================================================
# Downloads and installs stable LazyGit release
# Configuration: Inline (see variables below)
# Installation location: ~/.local/bin/lazygit
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

BINARY_NAME="lazygit"
REPO="jesseduffield/lazygit"
VERSION="0.40.2"  # Pinned version

# Detect platform_arch for download URL
# LazyGit uses format: lazygit_{version}_{platform}_{arch}.tar.gz
# Examples: lazygit_0.40.2_Darwin_x86_64.tar.gz, lazygit_0.40.2_Linux_x86_64.tar.gz
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")

# Build download URL
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/v${VERSION}/lazygit_${VERSION}_${PLATFORM_ARCH}.tar.gz"

# Installation paths
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
TEMP_TARBALL="/tmp/${BINARY_NAME}.tar.gz"

# ================================================================
# Installation
# ================================================================

print_banner "Installing LazyGit"

# Check existing installation
# Extract just the version number (e.g., "0.56.0" from "version=0.56.0")
VERSION_CMD="lazygit --version 2>&1 | grep -oE 'version=[0-9.]+' | cut -d= -f2 | head -n1"
if check_existing_installation "$TARGET_BIN" "$BINARY_NAME" "$VERSION_CMD" "$VERSION"; then
  exit_success
fi

log_info "Target version: v$VERSION"

# Check for alternate installations
check_alternate_installation "$TARGET_BIN" "$BINARY_NAME"

# Download
download_release "$DOWNLOAD_URL" "$TEMP_TARBALL" "$BINARY_NAME"

# Extract (binary is at root of tarball)
extract_tarball "$TEMP_TARBALL" "/tmp" "$BINARY_NAME"

# Install
install_binary "/tmp/$BINARY_NAME" "$TARGET_BIN"

# Verify
verify_installation "$BINARY_NAME" "$VERSION_CMD"

print_banner_success "LazyGit installation complete"
exit_success
