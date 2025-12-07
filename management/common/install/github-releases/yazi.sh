#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="yazi"
REPO="sxyazi/yazi"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing Yazi"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  log_info "Proceeding to themes/plugins update..."
else
  VERSION=$(get_latest_version "$REPO")
  log_info "Latest version: $VERSION"

  OS=$(detect_os)
  RAW_ARCH=$(uname -m)

  if [[ "$OS" == "darwin" ]]; then
    YAZI_TARGET="${RAW_ARCH}-apple-darwin"
  else
    YAZI_TARGET="${RAW_ARCH}-unknown-linux-gnu"
  fi

  DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/yazi-${YAZI_TARGET}.zip"

  TEMP_ZIP="/tmp/${BINARY_NAME}.zip"
  EXTRACT_DIR="/tmp/yazi-extract"

  log_info "Downloading yazi..."
  if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_ZIP"; then
    manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. After downloading, extract and install:
   unzip ~/Downloads/yazi.zip
   mv yazi-${YAZI_TARGET}/yazi ~/.local/bin/
   mv yazi-${YAZI_TARGET}/ya ~/.local/bin/
   chmod +x ~/.local/bin/yazi ~/.local/bin/ya

3. Verify installation:
   yazi --version"
    output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Download failed"
    log_error "Failed to download from $DOWNLOAD_URL"
    exit 1
  fi

  log_info "Extracting..."
  mkdir -p "$EXTRACT_DIR"
  unzip -q "$TEMP_ZIP" -d "$EXTRACT_DIR"

  log_info "Installing to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"
  mv "$EXTRACT_DIR/yazi-${YAZI_TARGET}/yazi" "$TARGET_BIN"
  mv "$EXTRACT_DIR/yazi-${YAZI_TARGET}/ya" "$HOME/.local/bin/ya"
  chmod +x "$TARGET_BIN" "$HOME/.local/bin/ya"

  if command -v yazi >/dev/null 2>&1; then
    log_success "yazi and ya installed successfully"
  else
    manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/yazi"
    output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Binary not found in PATH after installation"
    log_error "yazi not found in PATH after installation"
    exit 1
  fi
fi

# Configure git to not prompt for credentials (prevents hanging)
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

log_info "Installing flavors..."
ya pkg add BennyOe/tokyo-night || true
ya pkg add dangooddd/kanagawa || true
ya pkg add bennyyip/gruvbox-dark || true
ya pkg add kmlupreti/ayu-dark || true
ya pkg add Chromium-3-Oxide/everforest-medium || true
ya pkg add gosxrgxx/flexoki-dark || true

log_info "Installing plugins..."
ya pkg add AnirudhG07/nbpreview || true
ya pkg add pirafrank/what-size || true
ya pkg add yazi-rs/plugins:git || true
