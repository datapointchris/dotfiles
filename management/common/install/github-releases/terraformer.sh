#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"

BINARY_NAME="terraformer"
REPO="GoogleCloudPlatform/terraformer"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"
PROVIDER="all"  # Install all-provider version

print_banner "Installing Terraformer"

# Initialize failure registry
init_failure_registry

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
  # Report failure if registry exists
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="1. Download in your browser (bypasses firewall):
   $DOWNLOAD_URL

2. After downloading, install:
   mv ~/Downloads/terraformer-${PROVIDER}-${PLATFORM}-${ARCH} ~/.local/bin/terraformer
   chmod +x ~/.local/bin/terraformer

3. Verify installation:
   terraformer --version"
    report_failure "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Download failed"
  fi
  log_fatal "Failed to download from $DOWNLOAD_URL" "${BASH_SOURCE[0]}" "$LINENO"
fi

chmod +x "$TARGET_BIN"

# Verify
if command -v terraformer >/dev/null 2>&1; then
  log_success "terraformer installed successfully"
else
  # Report failure if registry exists
  if [[ -n "${DOTFILES_FAILURE_REGISTRY:-}" ]]; then
    manual_steps="Binary installed but not found in PATH.

Check that ~/.local/bin is in your PATH:
   echo \$PATH | grep -q \"\$HOME/.local/bin\" || export PATH=\"\$HOME/.local/bin:\$PATH\"

Verify the binary exists:
   ls -la ~/.local/bin/terraformer"
    report_failure "$BINARY_NAME" "$DOWNLOAD_URL" "$VERSION" "$manual_steps" "Binary not found in PATH after installation"
  fi
  log_fatal "terraformer not found in PATH after installation" "${BASH_SOURCE[0]}" "$LINENO"
fi

print_banner_success "Terraformer installation complete"
exit_success
