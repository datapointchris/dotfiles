#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
SHELL_DIR="${SHELL_DIR:-$HOME/.local/shell}"
source "$SHELL_DIR/logging.sh"
source "$SHELL_DIR/formatting.sh"
source "$SHELL_DIR/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="terrascan"
REPO="tenable/terrascan"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing Terrascan"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# Platform detection (lowercase, amd64 for x86_64)
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="darwin"
  ARCH=$(uname -m)
  [[ "$ARCH" == "x86_64" ]] && ARCH="amd64"
else
  PLATFORM="linux"
  ARCH="amd64"
fi

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/terrascan_${VERSION#v}_${PLATFORM}_${ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "terrascan"

print_banner_success "Terrascan installation complete"
exit_success
