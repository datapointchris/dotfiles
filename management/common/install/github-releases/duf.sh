#!/usr/bin/env bash
# ================================================================
# Install Duf from GitHub Releases
# ================================================================
# Downloads and installs Duf disk usage utility
# Installation location: ~/.local/bin/duf
# No sudo required (user space)
# ================================================================

set -euo pipefail

# Source error handling (includes structured logging)
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/error-handling.sh"
enable_error_traps

# Source GitHub release installer library
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="duf"
REPO="muesli/duf"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing Duf"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# Duf uses lowercase: duf_0.8.1_darwin_x86_64.tar.gz
PLATFORM_ARCH=$(get_platform_arch "darwin_x86_64" "darwin_arm64" "linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/duf_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "duf"

print_banner_success "Duf installation complete"
exit_success
