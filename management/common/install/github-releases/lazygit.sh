#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="lazygit"
REPO="jesseduffield/lazygit"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing LazyGit"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit 0
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

PLATFORM_ARCH=$(get_platform_arch "Darwin_x86_64" "Darwin_arm64" "Linux_x86_64")

# Format: lazygit_{version}_{platform}.tar.gz
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/lazygit_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

# Binary is at root of tarball
install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "lazygit" "$VERSION"
