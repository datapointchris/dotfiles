#!/usr/bin/env bash
set -uo pipefail

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

BINARY_NAME="terraform-ls"
REPO="hashicorp/terraform-ls"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

VERSION=$(get_latest_version "$REPO")

if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! check_if_update_needed "$BINARY_NAME" "$VERSION"; then
    exit 0
  fi
else
  if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
    exit 0
  fi
fi

OS=$(detect_os)
ARCH=$(detect_arch)

DOWNLOAD_URL="https://releases.hashicorp.com/terraform-ls/${VERSION#v}/terraform-ls_${VERSION#v}_${OS}_${ARCH}.zip"

install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "terraform-ls" "$VERSION"
