#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="terraformer"
REPO="GoogleCloudPlatform/terraformer"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
PROVIDER="all"  # Install all-provider version

print_banner "Installing Terraformer"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit 0
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# Detect platform (lowercase)
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="darwin"
else
  PLATFORM="linux"
fi
ARCH=$(uname -m)
[[ "$ARCH" == "x86_64" ]] && ARCH="amd64"

# Terraformer is a raw binary (no archive)
# Format: terraformer-all-darwin-amd64
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/terraformer-${PROVIDER}-${PLATFORM}-${ARCH}"

log_info "Downloading terraformer..."
if ! curl -fsSL "$DOWNLOAD_URL" -o "$TARGET_BIN"; then
  manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. After downloading, install:
   mv ~/Downloads/terraformer-${PROVIDER}-${PLATFORM}-${ARCH} ~/.local/bin/terraformer
   chmod +x ~/.local/bin/terraformer

3. Verify installation:
   terraformer --version"

  output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Download failed"
  log_error "Failed to download from $DOWNLOAD_URL"
  exit 1
fi

chmod +x "$TARGET_BIN"

# Verify
if command -v terraformer >/dev/null 2>&1; then
  log_success "terraformer installed successfully"
else
  manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/terraformer"

  output_failure_data "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Binary not found in PATH after installation"
  log_error "terraformer not found in PATH after installation"
  exit 1
fi
