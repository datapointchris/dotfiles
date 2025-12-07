#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="terrascan"
REPO="tenable/terrascan"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing Terrascan"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit 0
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# terrascan uses capital case for platform and x86_64 for arch
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="Darwin"
  ARCH="x86_64"
else
  PLATFORM="Linux"
  ARCH="x86_64"
fi

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/terrascan_${VERSION#v}_${PLATFORM}_${ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "terrascan" "$VERSION"
