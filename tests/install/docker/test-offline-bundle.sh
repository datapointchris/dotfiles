#!/usr/bin/env bash
#
# End-to-end test of the offline bundle on a clean Ubuntu 26.04 container with
# no network.
#
# This is the only way to find out whether a bundle installs before carrying it
# to a machine that cannot reach GitHub. Everything the installers would
# normally resolve online — versions, checksum file names, asset downloads —
# has to come out of the bundle, and `--network none` is what proves it does.
#
# Usage:
#   ./test-offline-bundle.sh [BUNDLE.tar.gz]
#
# Defaults to the newest dotfiles-offline-*.tar.gz in the repo root.

set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"

IMAGE_TAG="dotfiles-offline-test"
DOCKERFILE="$DOTFILES_DIR/tests/install/docker/Dockerfile.offline"

BUNDLE="${1:-}"
if [[ -z "$BUNDLE" ]]; then
  BUNDLE=$(find "$DOTFILES_DIR" -maxdepth 1 -name 'dotfiles-offline-*.tar.gz' -type f 2>/dev/null |
    sort | tail -1)
fi

if [[ -z "$BUNDLE" || ! -f "$BUNDLE" ]]; then
  log_error "No bundle found. Create one first:"
  log_info "  ./install.sh --create-offline-bundle --manifest wsl-work-workstation"
  exit 1
fi

log_info "Bundle: $BUNDLE ($(du -h "$BUNDLE" | cut -f1))"

log_info "Building $IMAGE_TAG from ubuntu:26.04..."
docker build -q -f "$DOCKERFILE" -t "$IMAGE_TAG" "$DOTFILES_DIR/tests/install/docker" > /dev/null

# --network none is the whole test. The repo is read-only because an installer
# writing into it would be a bug in its own right.
log_info "Running installers with no network..."
#
# Mounted at ~/dotfiles rather than /dotfiles because logging.sh falls back to
# that literal path when $SHELL_DIR is not linked, which is exactly the state a
# first install is in.
docker run --rm \
  --network none \
  -v "$DOTFILES_DIR":/home/testuser/dotfiles:ro \
  -v "$BUNDLE":/home/testuser/bundle.tar.gz:ro \
  "$IMAGE_TAG" \
  bash /home/testuser/dotfiles/tests/install/docker/offline-install-check.sh
