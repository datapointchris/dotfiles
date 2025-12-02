#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"

BINARY_NAME="terraformer"
REPO="GoogleCloudPlatform/terraformer"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
PROVIDER="all"  # Install all-provider version

print_banner "Installing Terraformer"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
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
  log_fatal "Failed to download from $DOWNLOAD_URL" "${BASH_SOURCE[0]}" "$LINENO"
fi

chmod +x "$TARGET_BIN"

# Verify
if command -v terraformer >/dev/null 2>&1; then
  log_success "terraformer installed successfully"
else
  log_fatal "terraformer not found in PATH after installation" "${BASH_SOURCE[0]}" "$LINENO"
fi

print_banner_success "Terraformer installation complete"
exit_success
