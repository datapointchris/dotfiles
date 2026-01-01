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

BINARY_NAME="shellcheck"
REPO="koalaman/shellcheck"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

VERSION=$(get_latest_version "$REPO")
log_info "Latest $BINARY_NAME version: $VERSION"

if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! check_if_update_needed "$BINARY_NAME" "$VERSION"; then
    exit 0
  fi
else
  if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
    exit 0
  fi
fi

# Platform naming: lowercase (darwin, linux) with arch (x86_64, aarch64)
PLATFORM_ARCH=$(get_platform_arch "darwin.x86_64" "darwin.aarch64" "linux.x86_64")

# Format: shellcheck-v{version}.{platform}.tar.xz
# Binary is inside shellcheck-v{version}/ directory in tarball
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/shellcheck-${VERSION}.${PLATFORM_ARCH}.tar.xz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "shellcheck-${VERSION}/shellcheck" "$VERSION"
