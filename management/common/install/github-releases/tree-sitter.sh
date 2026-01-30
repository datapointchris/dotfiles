#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="tree-sitter"
REPO="tree-sitter/tree-sitter"

get_download_url() {
  local version="$1" os="$2" arch="$3"
  local platform_arch
  if [[ "$os" == "darwin" ]]; then
    [[ "$arch" == "arm64" ]] && platform_arch="macos-arm64" || platform_arch="macos-x64"
  else
    platform_arch="linux-x64"
  fi
  echo "https://github.com/${REPO}/releases/download/${version}/tree-sitter-${platform_arch}.gz"
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

# tree-sitter releases are .gz compressed binaries (not tarballs)
GZ_PATH="/tmp/${BINARY_NAME}.gz"
URL_FILENAME=$(basename "$DOWNLOAD_URL")

# Check offline cache first
if [[ -d "$OFFLINE_CACHE_DIR" ]]; then
  CACHED_FILE="$OFFLINE_CACHE_DIR/$URL_FILENAME"
  if [[ -f "$CACHED_FILE" ]]; then
    log_info "Using cached file: $CACHED_FILE"
    cp "$CACHED_FILE" "$GZ_PATH"
  fi
fi

# Download if not found in cache
if [[ ! -f "$GZ_PATH" ]]; then
  log_info "Download URL: $DOWNLOAD_URL"
  log_info "Downloading $BINARY_NAME..."
  if ! curl -fsSL "$DOWNLOAD_URL" -o "$GZ_PATH"; then
    manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. Save to: $OFFLINE_CACHE_DIR/$URL_FILENAME

3. Re-run this installer"

    output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Download failed"
    log_error "Failed to download $BINARY_NAME"
    exit 1
  fi
fi

log_info "Extracting..."
mkdir -p "$HOME/.local/bin"
gunzip -c "$GZ_PATH" > "$TARGET_BIN"
chmod +x "$TARGET_BIN"
rm -f "$GZ_PATH"

if command -v "$BINARY_NAME" >/dev/null 2>&1; then
  log_success "$BINARY_NAME installed to: $TARGET_BIN"
else
  manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/${BINARY_NAME}"

  output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Binary not found in PATH after installation"
  log_error "$BINARY_NAME not found in PATH after installation"
  exit 1
fi
