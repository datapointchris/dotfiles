#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
enable_error_traps
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/program-helpers.sh"

BINARY_NAME="terraform-ls"
REPO="hashicorp/terraform-ls"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing Terraform Language Server"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

# Platform detection (lowercase, amd64 for x86_64)
if [[ "$OSTYPE" == "darwin"* ]]; then
  PLATFORM="darwin"
  ARCH=$(uname -m)
  [[ "$ARCH" == "x86_64" ]] && ARCH="amd64"
else
  PLATFORM="linux"
  ARCH="amd64"
fi

# Hashicorp moved to releases.hashicorp.com
DOWNLOAD_URL="https://releases.hashicorp.com/terraform-ls/${VERSION#v}/terraform-ls_${VERSION#v}_${PLATFORM}_${ARCH}.zip"

install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "terraform-ls" "$VERSION"

print_banner_success "Terraform Language Server installation complete"
exit_success
