#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/management/lib/platform-detection.sh"
source "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/management/common/lib/install-helpers.sh"

BINARY_NAME="terraform-ls"
REPO="hashicorp/terraform-ls"
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

print_banner "Installing Terraform Language Server"

if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
  exit_success
fi

VERSION=$(get_latest_version "$REPO")
log_info "Latest version: $VERSION"

OS=$(detect_os)
ARCH=$(detect_arch)

DOWNLOAD_URL="https://releases.hashicorp.com/terraform-ls/${VERSION#v}/terraform-ls_${VERSION#v}_${OS}_${ARCH}.zip"

install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "terraform-ls" "$VERSION"

print_banner_success "Terraform Language Server installation complete"
exit_success
