#!/usr/bin/env bash
set -uo pipefail

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

BINARY_NAME="duf"
REPO="muesli/duf"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

if [[ "$UPDATE_MODE" == "true" ]]; then
  log_info "Checking for updates..."
else
  log_info "Installing..."
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! check_if_update_needed "$BINARY_NAME" "$VERSION"; then
    exit 0
  fi
else
  if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
    exit 0
  fi
fi

# Duf uses lowercase: duf_0.8.1_darwin_x86_64.tar.gz
PLATFORM_ARCH=$(get_platform_arch "darwin_x86_64" "darwin_arm64" "linux_x86_64")
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/duf_${VERSION#v}_${PLATFORM_ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "duf" "$VERSION"
