#!/usr/bin/env bash
#
# Resolving and importing an Ubuntu WSL rootfs, for the Docker-based WSL install
# tests.
#
# Usage:
#   source "$DOTFILES_DIR/install/common/lib/wsl-rootfs.sh"
#
#   url=$(wsl_rootfs_url 26.04)
#   file=$(wsl_rootfs_fetch 26.04 "$cache_dir")
#   wsl_rootfs_import 26.04 "$file" wsl-ubuntu:26.04
#
# The asset filename is DISCOVERED from the release directory, never built from
# the version. It cannot be constructed: 24.04 ships as ubuntu-24.04.4-wsl-amd64
# (point release in the name, and it was .3 until recently), while 26.04 ships as
# ubuntu-26.04-wsl-amd64 with no point release at all. Two callers each hardcoded
# a guess, and both were wrong for a different version — 24.04 pinned to a point
# release that gets superseded, 26.04 unsupported outright.
#
# releases.ubuntu.com serves .wsl for every supported release including 22.04, so
# the older cloud-images.ubuntu.com tar.gz path this replaced is not needed. The
# .wsl file is an uncompressed tar, which docker import reads directly.

WSL_ROOTFS_RELEASES_BASE="https://releases.ubuntu.com"

# The release the work machine runs. Both the image manager and the e2e test read
# it from here so there is one place to bump when that machine moves again.
export DEFAULT_UBUNTU_VERSION="26.04"

# Echoes the newest .wsl asset filename published for an Ubuntu version.
# Returns 1 when the version has no release directory or publishes no WSL image.
wsl_rootfs_filename() {
  local version="$1" listing filename

  listing=$(curl -fsSL --connect-timeout 10 "$WSL_ROOTFS_RELEASES_BASE/$version/" 2>/dev/null) || return 1

  # sort -V, because 24.04 lists several point releases at once and the newest is
  # the one WSL would actually hand you.
  filename=$(echo "$listing" | grep -oE 'ubuntu-[0-9.]+-wsl-amd64\.wsl' | sort -Vu | tail -1)

  [[ -n "$filename" ]] || return 1
  echo "$filename"
}

wsl_rootfs_url() {
  local version="$1" filename
  filename=$(wsl_rootfs_filename "$version") || return 1
  echo "$WSL_ROOTFS_RELEASES_BASE/$version/$filename"
}

# Echoes the path to a cached rootfs, downloading it first if absent. Progress
# and status go to stderr so the path stays the only thing on stdout.
wsl_rootfs_fetch() {
  local version="$1" cache_dir="$2" filename url target

  filename=$(wsl_rootfs_filename "$version") || {
    echo "No WSL image published for Ubuntu $version at $WSL_ROOTFS_RELEASES_BASE/$version/" >&2
    return 1
  }
  url="$WSL_ROOTFS_RELEASES_BASE/$version/$filename"
  target="$cache_dir/$filename"

  mkdir -p "$cache_dir"

  if [[ -f "$target" ]]; then
    echo "Using cached rootfs: $target" >&2
  else
    echo "Downloading $filename (~400MB, cached after the first run)..." >&2
    curl -fL --progress-bar "$url" -o "$target" || {
      rm -f "$target"
      echo "Failed to download $url" >&2
      return 1
    }
  fi

  echo "$target"
}

# Imports a rootfs as a Docker image, replacing any existing image of that tag.
#
# The rootfs ships with no login user — WSL creates one on first launch — so one
# is added here and committed. It has to be committed: the previous `docker run
# --rm ... useradd` created the user in a container that was then discarded, with
# 2>/dev/null and a || swallowing the evidence, so every WSL test ran as root
# against /root while the real machine runs as a sudo user against /home.
wsl_rootfs_import() {
  local rootfs_file="$1" image="$2"
  local build_container="wsl-rootfs-build-$$"

  if docker image inspect "$image" >/dev/null 2>&1; then
    docker rmi "$image" >/dev/null
  fi

  docker import - "$image" <"$rootfs_file" >/dev/null

  docker run --name "$build_container" "$image" /bin/bash -c '
    set -e
    useradd -m -s /bin/bash ubuntu
    getent group sudo >/dev/null || groupadd sudo
    usermod -aG sudo ubuntu
    echo "ubuntu ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/ubuntu
    chmod 0440 /etc/sudoers.d/ubuntu
  ' || {
    docker rm -f "$build_container" >/dev/null 2>&1
    echo "Failed to create the ubuntu user in $image" >&2
    return 1
  }

  docker commit "$build_container" "$image" >/dev/null
  docker rm "$build_container" >/dev/null
}
