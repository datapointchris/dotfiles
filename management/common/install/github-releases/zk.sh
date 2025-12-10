#!/usr/bin/env bash
set -uo pipefail

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

BINARY_NAME="zk"
REPO="zk-org/zk"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

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
log_info "Latest version: $VERSION"

OS=$(detect_os)
ARCH=$(detect_arch)

if [[ "$OS" == "darwin" ]]; then
  PLATFORM="macos"
  RAW_ARCH=$(uname -m)
else
  PLATFORM="linux"
  RAW_ARCH="$ARCH"
fi

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/zk-${VERSION}-${PLATFORM}-${RAW_ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "zk" "$VERSION"
