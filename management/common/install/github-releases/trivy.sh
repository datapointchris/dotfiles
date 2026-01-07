#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="trivy"
REPO="aquasecurity/trivy"

get_download_url() {
  local version="$1" os="$2" arch="$3"
  local platform
  if [[ "$os" == "darwin" ]]; then
    [[ "$arch" == "arm64" ]] && platform="macOS-ARM64" || platform="macOS-64bit"
  else
    platform="Linux-64bit"
  fi
  echo "https://github.com/${REPO}/releases/download/${version}/trivy_${version#v}_${platform}.tar.gz"
}

if [[ "${1:-}" == "--print-url" ]]; then
  OS="${2:-linux}"
  ARCH="${3:-x86_64}"
  VERSION=$(fetch_github_latest_version "$REPO")
  URL=$(get_download_url "$VERSION" "$OS" "$ARCH")
  echo "$BINARY_NAME|$VERSION|$URL"
  exit 0
fi

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

UPDATE_MODE=false
[[ "${1:-}" == "--update" ]] && UPDATE_MODE=true

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

OS=$([[ "$OSTYPE" == "darwin"* ]] && echo "darwin" || echo "linux")
ARCH=$(uname -m | sed 's/x86_64/x86_64/;s/aarch64/arm64/;s/arm64/arm64/')
DOWNLOAD_URL=$(get_download_url "$VERSION" "$OS" "$ARCH")

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "trivy" "$VERSION"
