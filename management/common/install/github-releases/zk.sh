#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="zk"
REPO="zk-org/zk"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing zk"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# zk uses: zk-{version}-{platform}-{arch}.tar.gz
# Platform: macos or linux
# Arch: x86_64, arm64 (mac), amd64/arm64 (linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="macos"
  ARCH=$(uname -m)  # x86_64 or arm64
else
  PLATFORM="linux"
  ARCH=$(uname -m)
  [[ "$ARCH" == "x86_64" ]] && ARCH="amd64"
  [[ "$ARCH" == "aarch64" ]] && ARCH="arm64"
fi

# zk keeps the 'v' in the asset filename
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/zk-${VERSION}-${PLATFORM}-${ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "zk" "$VERSION"
