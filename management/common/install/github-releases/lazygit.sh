#!/usr/bin/env bash
# ================================================================
# Install LazyGit from GitHub Releases
# ================================================================
# Downloads and installs latest LazyGit release
# Installation location: ~/.local/bin/lazygit
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source error handling (includes structured logging)
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps

# Source GitHub release installer library and failure reporting
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"

# ================================================================
# Configuration
# ================================================================

BINARY_NAME="lazygit"
REPO="jesseduffield/lazygit"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing LazyGit"

# Check if already installed
if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

# Get latest version and build URL
VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# Platform detection
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")

# Build download URL
# Format: lazygit_{version}_{platform}.tar.gz
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/lazygit_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

# Install (binary is at root of tarball)
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "lazygit" "$VERSION"

print_banner_success "LazyGit installation complete"
exit_success
