#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/install/common/lib/version-helpers.sh"
source "$DOTFILES_DIR/install/common/lib/github-release-installer.sh"

BINARY_NAME="atuin"
REPO="atuinsh/atuin"

# atuin's release assets differ from the usual shape in two ways: the version is
# absent from the filename, and the binary nests under a target-named directory
# (atuin-<target>/atuin). So both the URL builder and the extraction path need the
# resolved Rust target triple (musl for portability across Linux distros).
get_target() {
  local arch="$1"
  [[ "$arch" == "arm64" ]] && echo "aarch64-unknown-linux-musl" || echo "x86_64-unknown-linux-musl"
}

get_download_url() {
  local version="$1" arch="$2"
  local target
  target=$(get_target "$arch")
  echo "https://github.com/${REPO}/releases/download/${version}/atuin-${target}.tar.gz"
}

# --print-url mode for offline bundle creator
if [[ "${1:-}" == "--print-url" ]]; then
  ARCH="${3:-x86_64}"
  VERSION=$(fetch_github_latest_version "$REPO") || exit 1
  URL=$(get_download_url "$VERSION" "$ARCH")
  echo "$BINARY_NAME|$VERSION|$URL"
  exit 0
fi

# Real install path is Linux-only. atuin ships no Intel-macOS release binary (just
# aarch64-apple-darwin), so macOS installs atuin through brew instead — see the
# brew-only system_packages entry in packages.yml. --print-url above stays reachable
# from any host so the offline bundler can compute Linux URLs while run from a Mac.
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "atuin on macOS installs via brew (brew install atuin), not this script." >&2
  exit 1
fi

source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/error-handling.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

TARGET_BIN="$HOME/.local/bin/$BINARY_NAME"

UPDATE_MODE=false
[[ "${1:-}" == "--update" ]] && UPDATE_MODE=true

VERSION=$(get_latest_version "$REPO") || exit 1
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

ARCH=$(get_arch)
TARGET=$(get_target "$ARCH")
DOWNLOAD_URL=$(get_download_url "$VERSION" "$ARCH")

install_from_tarball "$BINARY_NAME" "$DOWNLOAD_URL" "atuin-${TARGET}/atuin" "$VERSION"
