#!/usr/bin/env bash
set -uo pipefail

# meso — mesocycle programming, workout logging, measurements
#
# The CLI is a nested Go module inside the app repo, released under a `cli/v*`
# tag so it never collides with the app's own tag namespace. That is why this
# resolves the version with the prefixed lookup rather than /releases/latest,
# which would return whichever release is newest overall.

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"

BINARY_NAME="meso"
REPO="datapointchris/meso"
TAG_PREFIX="cli/"

# $1 = tag (cli/v1.2.0), $2 = os, $3 = go arch
get_download_url() {
  local tag="$1" os="$2" go_arch="$3"
  local version="${tag#"$TAG_PREFIX"}"
  echo "https://github.com/${REPO}/releases/download/${tag}/${BINARY_NAME}_${version#v}_${os}_${go_arch}.tar.gz"
}

go_arch_for() {
  [[ "$1" == "arm64" ]] && echo "arm64" || echo "amd64"
}

# --print-url mode for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  OS="${2:-linux}"
  ARCH="${3:-x86_64}"
  TAG=$(fetch_github_latest_version_prefixed "$REPO" "$TAG_PREFIX")
  URL=$(get_download_url "$TAG" "$OS" "$(go_arch_for "$ARCH")")
  echo "$BINARY_NAME|${TAG#"$TAG_PREFIX"}|$URL"
  exit 0
fi

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

UPDATE_MODE=false
[[ "${1:-}" == "--update" ]] && UPDATE_MODE=true

if ! TAG=$(fetch_github_latest_version_prefixed "$REPO" "$TAG_PREFIX"); then
  log_warning "No ${TAG_PREFIX}* release published for $REPO yet — skipping $BINARY_NAME"
  exit 0
fi

# Version comparison and the archive name both want the tag without its prefix.
VERSION="${TAG#"$TAG_PREFIX"}"
log_info "Latest $BINARY_NAME version: $VERSION ($TAG)"

if [[ "$UPDATE_MODE" == "true" ]]; then
  if ! check_if_update_needed "$BINARY_NAME" "$VERSION"; then
    exit 0
  fi
else
  if should_skip_install "$TARGET_BIN" "$BINARY_NAME"; then
    exit 0
  fi
fi

OS=$(get_os)
DOWNLOAD_URL=$(get_download_url "$TAG" "$OS" "$(go_arch_for "$(get_arch)")")

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "$BINARY_NAME" "$VERSION"
