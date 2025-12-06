#!/usr/bin/env bash
# ================================================================
# Install Glow from GitHub Releases
# ================================================================
# Downloads and installs Glow markdown renderer
# Installation location: ~/.local/bin/glow
# No sudo required (user space)
# ================================================================

set -uo pipefail

# Source error handling (includes structured logging)
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"

# Source GitHub release installer library and failure reporting
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="glow"
REPO="charmbracelet/glow"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing Glow"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# Glow uses: glow_1.5.1_Darwin_x86_64.tar.gz with nested directory
PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/glow_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

# Binary is in nested directory: glow_*_Darwin_x86_64/glow
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "glow_*_${PLATFORM_ARCH}/glow" "$VERSION"

print_banner_success "Glow installation complete"
exit_success
