#!/usr/bin/env bash
set -uo pipefail

UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
  UPDATE_MODE=true
fi

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/install/platform-detection.sh"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

BINARY_NAME="terraform-ls"
REPO=$(PYTHONPATH="$DOTFILES_DIR/src" /usr/bin/python3 -m dotfiles.parse_packages \
  --custom-installer "$BINARY_NAME" --field repo) \
  || {
    log_error "Could not read $BINARY_NAME.repo from packages.yml"
    exit 1
  }
TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

# Released from releases.hashicorp.com, so create_bundle.py never caches it and
# the version cannot be resolved from the bundle manifest either. Same reasoning
# as tenv: failing the phase reports manual steps the machine cannot follow.
if [[ "${OFFLINE_MODE:-false}" == "true" ]]; then
  log_warning "Offline mode: skipping $BINARY_NAME (released from releases.hashicorp.com, not bundled)"
  exit 0
fi

# The asset filename is built from the version, so an unresolved version yields
# a URL with an empty segment that 404s instead of failing here.
VERSION=$(get_latest_version "$REPO") || exit 1
if [[ -z "$VERSION" ]]; then
  log_error "Could not resolve a $BINARY_NAME version from $REPO"
  exit 1
fi

if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! check_if_update_needed "$BINARY_NAME" "$VERSION"; then
    exit 0
  fi
else
  if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
    exit 0
  fi
fi

OS=$(detect_os)
ARCH=$(detect_arch)

DOWNLOAD_URL="https://releases.hashicorp.com/terraform-ls/${VERSION#v}/terraform-ls_${VERSION#v}_${OS}_${ARCH}.zip"

# Released from releases.hashicorp.com rather than the GitHub release, so the
# checksums file cannot be discovered from the release assets and has to be
# named directly.
export CHECKSUM_URL="https://releases.hashicorp.com/terraform-ls/${VERSION#v}/terraform-ls_${VERSION#v}_SHA256SUMS"

install_from_zip "$BINARY_NAME" "$DOWNLOAD_URL" "terraform-ls" "$VERSION"
