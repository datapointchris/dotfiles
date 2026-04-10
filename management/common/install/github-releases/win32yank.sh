#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="win32yank.exe"
REPO="equalsraf/win32yank"

get_download_url() {
  local version="$1"
  echo "https://github.com/${REPO}/releases/download/${version}/win32yank-x64.zip"
}

if [[ "${1:-}" == "--print-url" ]]; then
  VERSION=$(fetch_github_latest_version "$REPO")
  URL=$(get_download_url "$VERSION")
  echo "$BINARY_NAME|$VERSION|$URL"
  exit 0
fi

# WSL only - win32yank is a Windows clipboard bridge
if ! grep -qE "Microsoft|WSL" /proc/version 2>/dev/null; then
  echo "Skipping win32yank: not running in WSL"
  exit 0
fi

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

UPDATE_MODE=false
[[ "${1:-}" == "--update" ]] && UPDATE_MODE=true

VERSION=$(get_latest_version "$REPO") || exit 1
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

DOWNLOAD_URL=$(get_download_url "$VERSION")

install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "win32yank.exe" "$VERSION"
