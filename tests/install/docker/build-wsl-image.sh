#!/usr/bin/env bash
# Import Microsoft's published WSL rootfs as a Docker image.
#
# The rootfs is the real thing rather than an approximation of it — the same
# 563-package filesystem WSL unpacks — which is why the WSL install is tested
# against this and not against `ubuntu:26.04`. `docs/learnings/testing-bootstrap-dependencies.md`
# records what the approximation cost.
#
#   bash build-wsl-image.sh [VERSION]     # default: whatever wsl-rootfs.sh pins
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/install/common/lib/wsl-rootfs.sh"

VERSION="${1:-$DEFAULT_UBUNTU_VERSION}"
CACHE_DIR="$DOTFILES_DIR/.wsl-rootfs-cache"
IMAGE="wsl-ubuntu:${VERSION}"

if docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "$IMAGE already exists"
  exit 0
fi

rootfs=$(wsl_rootfs_fetch "$VERSION" "$CACHE_DIR")
wsl_rootfs_import "$rootfs" "$IMAGE"
echo "Created $IMAGE"
