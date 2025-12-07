#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="tflint"
REPO="terraform-linters/tflint"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing TFLint"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# Platform detection (lowercase, amd64 for x86_64)
OS=$(detect_os)
ARCH=$(detect_arch)

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/tflint_${OS}_${ARCH}.zip"

install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "tflint" "$VERSION"
