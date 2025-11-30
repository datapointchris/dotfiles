#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/logging.sh"
source "$SHELL_DIR/formatting.sh"
source "$SHELL_DIR/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

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

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/zk-${VERSION#v}-${PLATFORM}-${ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "zk"

print_banner_success "zk installation complete"
exit_success
