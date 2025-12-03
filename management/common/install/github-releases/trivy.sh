#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"

BINARY_NAME="trivy"
REPO="aquasecurity/trivy"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing Trivy"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# trivy uses capital case with 64bit format
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="macOS"
  ARCH="64bit"
else
  PLATFORM="Linux"
  ARCH="64bit"
fi

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/trivy_${VERSION#v}_${PLATFORM}-${ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "trivy" "$VERSION"

print_banner_success "Trivy installation complete"
exit_success
