#!/usr/bin/env bash
# ================================================================
# Install fzf (Fuzzy Finder) from GitHub Releases
# ================================================================
# Downloads pre-built fzf binary from GitHub releases
# Installation location: ~/.local/bin/fzf
# No build tools required
# ================================================================

set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="fzf"
REPO="junegunn/fzf"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing fzf (Fuzzy Finder)"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# fzf uses: fzf-{version}-{platform}_{arch}.tar.gz
# Platform: darwin or linux (lowercase)
# Arch: amd64, arm64
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="darwin"
  ARCH=$(uname -m)
  [[ "$ARCH" == "x86_64" ]] && ARCH="amd64"
else
  PLATFORM="linux"
  ARCH=$(uname -m)
  [[ "$ARCH" == "x86_64" ]] && ARCH="amd64"
  [[ "$ARCH" == "aarch64" ]] && ARCH="arm64"
fi

# fzf strips the 'v' from version in asset filename
DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/fzf-${VERSION#v}-${PLATFORM}_${ARCH}.tar.gz"

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "fzf" "$VERSION"
