#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="terraformer"
REPO="GoogleCloudPlatform/terraformer"
PROVIDER="all"

get_download_url() {
  local version="$1" os="$2" arch="$3"
  local platform_arch
  if [[ "$os" == "darwin" ]]; then
    [[ "$arch" == "arm64" ]] && platform_arch="darwin-arm64" || platform_arch="darwin-amd64"
  else
    platform_arch="linux-amd64"
  fi
  echo "https://github.com/${REPO}/releases/download/${version}/terraformer-${PROVIDER}-${platform_arch}"
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
source "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
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
# Detect platform (lowercase)
OS=$(detect_os)
ARCH=$(detect_arch)

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/terraformer-${PROVIDER}-${OS}-${ARCH}"

log_info "Download URL: $DOWNLOAD_URL"
log_info "Downloading terraformer..."
mkdir -p "$HOME/.local/bin"
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TARGET_BIN"; then
  manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. After downloading, install:
   mv ~/Downloads/terraformer-${PROVIDER}-${OS}-${ARCH} ~/.local/bin/terraformer
   chmod +x ~/.local/bin/terraformer

3. Verify installation:
   terraformer --version"

  output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Download failed"
  log_error "Failed to download from $DOWNLOAD_URL"
  exit 1
fi

chmod +x "$TARGET_BIN"

# Verify
if ! command -v terraformer >/dev/null 2>&1; then
  manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/terraformer"

  output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Binary not found in PATH after installation"
  log_error "terraformer not found in PATH after installation"
  exit 1
fi
