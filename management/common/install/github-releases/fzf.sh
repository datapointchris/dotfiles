#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="fzf"
REPO="junegunn/fzf"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing fzf (Fuzzy Finder)"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit 0
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

OS=$(detect_os)
ARCH=$(detect_arch)

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/fzf-${VERSION#v}-${OS}_${ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "fzf" "$VERSION"
