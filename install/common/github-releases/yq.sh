#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"

BINARY_NAME="yq"
REPO="mikefarah/yq"

get_download_url() {
  local version="$1" os="$2" arch="$3"
  # mikefarah/yq ships direct binaries named with Go arch (amd64/arm64)
  local goarch
  [[ "$arch" == "arm64" ]] && goarch="arm64" || goarch="amd64"
  echo "https://github.com/${REPO}/releases/download/${version}/yq_${os}_${goarch}"
}

if [[ "${1:-}" == "--print-url" ]]; then
  OS="${2:-linux}"
  ARCH="${3:-x86_64}"
  VERSION=$(fetch_github_latest_version "$REPO") || exit 1
  URL=$(get_download_url "$VERSION" "$OS" "$ARCH")
  echo "$BINARY_NAME|$VERSION|$URL"
  exit 0
fi

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

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

OS=$(get_os)
ARCH=$(get_arch)
DOWNLOAD_URL=$(get_download_url "$VERSION" "$OS" "$ARCH")

# yq releases are direct binaries (no archive)
url_filename=$(basename "$DOWNLOAD_URL")
cached_file="$OFFLINE_CACHE_DIR/$url_filename"
if [[ -d "$OFFLINE_CACHE_DIR" ]] && [[ -f "$cached_file" ]]; then
  log_info "Using cached file: $cached_file"
  mkdir -p "$HOME/.local/bin"
  cp "$cached_file" "$TARGET_BIN"
fi

if [[ ! -f "$TARGET_BIN" ]] || [[ ! -s "$TARGET_BIN" ]]; then
  log_info "Download URL: $DOWNLOAD_URL"
  log_info "Downloading yq..."
  mkdir -p "$HOME/.local/bin"
  if ! curl -fsSL "$DOWNLOAD_URL" -o "$TARGET_BIN"; then
    output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "Download failed"
    log_error "Failed to download from $DOWNLOAD_URL"
    exit 1
  fi
fi

chmod +x "$TARGET_BIN"

if command -v yq >/dev/null 2>&1; then
  log_success "yq installed to: $TARGET_BIN"
else
  output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "Binary not found in PATH after installation"
  log_error "yq not found in PATH after installation"
  exit 1
fi
