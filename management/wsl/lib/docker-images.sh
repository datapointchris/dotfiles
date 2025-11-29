#!/usr/bin/env bash
# ================================================================
# WSL Docker Image Management Script
# ================================================================
# Manages WSL rootfs Docker images for testing
# ================================================================

set -euo pipefail

# Source formatting library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$DOTFILES_DIR/management/common/lib/structured-logging.sh"

WSL_CACHE_DIR="${DOTFILES_DIR}/.wsl-rootfs-cache"

# Show usage
show_usage() {
  echo "Usage: $(basename "$0") COMMAND [OPTIONS]"
  echo ""
  echo "Manage WSL Ubuntu Docker images for testing"
  echo ""
  echo "Commands:"
  echo "  list              List available WSL Docker images"
  echo "  build VERSION     Build/rebuild Docker image (currently only 22.04)"
  echo "  remove VERSION    Remove Docker image"
  echo "  clean             Remove all cached rootfs files"
  echo "  clean-all         Remove both images and cached files"
  echo "  info              Show cache and image information"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0") list"
  echo "  $(basename "$0") build 22.04"
  echo "  $(basename "$0") remove 22.04"
  echo "  $(basename "$0") clean"
  exit 0
}

# Get codename from version
get_codename() {
  local version=$1
  case "$version" in
    22.04) echo "jammy" ;;
    24.04) die "Ubuntu 24.04 uses .wsl format (not tar.gz), only 22.04 is currently supported" ;;
    *) die "Unsupported version: $version (only 22.04 is supported)" ;;
  esac
}

# List Docker images
list_images() {
  print_section "WSL Docker Images"

  if docker image ls --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep -q "wsl-ubuntu"; then
    docker image ls --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep -E "REPOSITORY|wsl-ubuntu"
  else
    echo "No WSL Docker images found"
    echo ""
    echo "Build an image with: $(basename "$0") build 24.04"
  fi
}

# Build Docker image
build_image() {
  local version=${1:-22.04}
  local codename
  codename=$(get_codename "$version")

  local docker_image="wsl-ubuntu:${version}"
  # Note: Ubuntu 24.04+ uses .wsl format, only 22.04 has tar.gz rootfs
  local rootfs_url="https://cloud-images.ubuntu.com/wsl/${codename}/current/ubuntu-${codename}-wsl-amd64-ubuntu${version}lts.rootfs.tar.gz"
  local rootfs_file="${WSL_CACHE_DIR}/ubuntu-${codename}-wsl-amd64-ubuntu${version}lts.rootfs.tar.gz"

  print_section "Building WSL Docker Image"
  echo "Version: Ubuntu ${version} (${codename})"
  echo "Image: ${docker_image}"
  echo ""

  # Create cache directory
  mkdir -p "$WSL_CACHE_DIR"

  # Download rootfs if not cached
  if [[ -f "$rootfs_file" ]]; then
    print_success "Using cached rootfs: $rootfs_file"
  else
    echo "Downloading WSL rootfs (~340MB, one-time download)..."
    echo "URL: $rootfs_url"
    echo ""
    curl -L --progress-bar "$rootfs_url" -o "$rootfs_file"
    print_success "Downloaded and cached rootfs"
  fi

  echo ""
  echo "Importing rootfs into Docker..."

  # Remove existing image if present
  if docker image inspect "$docker_image" >/dev/null 2>&1; then
    echo "Removing existing image: $docker_image"
    docker rmi "$docker_image" >/dev/null
  fi

  # Import rootfs
  gunzip -c "$rootfs_file" | docker import - "$docker_image"

  echo ""
  print_success "Built Docker image: $docker_image"

  # Show image info
  echo ""
  docker image ls --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep -E "REPOSITORY|$docker_image"
}

# Remove Docker image
remove_image() {
  local version=${1:-}
  if [[ -z "$version" ]]; then
    die "Version required. Usage: $(basename "$0") remove VERSION"
  fi

  local codename
  codename=$(get_codename "$version")
  local docker_image="wsl-ubuntu:${version}"

  print_section "Removing WSL Docker Image"
  echo "Image: ${docker_image}"
  echo ""

  if docker image inspect "$docker_image" >/dev/null 2>&1; then
    docker rmi "$docker_image"
    print_success "Removed image: $docker_image"
  else
    print_warning "Image not found: $docker_image"
  fi
}

# Clean cached rootfs files
clean_cache() {
  print_section "Cleaning Cached Rootfs Files"

  if [[ -d "$WSL_CACHE_DIR" ]]; then
    local cache_size
    cache_size=$(du -sh "$WSL_CACHE_DIR" 2>/dev/null | cut -f1 || echo "0")
    echo "Cache directory: $WSL_CACHE_DIR"
    echo "Current size: $cache_size"
    echo ""

    if [[ -n "$(ls -A "$WSL_CACHE_DIR" 2>/dev/null)" ]]; then
      echo "Removing cached files:"
      ls -lh "$WSL_CACHE_DIR"
      echo ""
      rm -rf "${WSL_CACHE_DIR:?}"/*
      print_success "Cleaned cache directory"
    else
      print_info "Cache directory is already empty"
    fi
  else
    print_info "Cache directory does not exist"
  fi
}

# Clean everything
clean_all() {
  print_section "Cleaning All WSL Docker Resources"
  echo ""

  # Remove images
  echo "Checking for WSL Docker images..."
  if docker image ls --format "{{.Repository}}:{{.Tag}}" | grep -q "wsl-ubuntu"; then
    docker image ls --format "{{.Repository}}:{{.Tag}}" | grep "wsl-ubuntu" | while read -r image; do
      echo "Removing image: $image"
      docker rmi "$image" >/dev/null
    done
    print_success "Removed all WSL Docker images"
  else
    print_info "No WSL Docker images found"
  fi

  echo ""

  # Clean cache
  clean_cache

  echo ""
  print_success "Cleanup complete"
}

# Show info
show_info() {
  print_section "WSL Docker Testing Information"
  echo ""

  # Docker images
  echo "Docker Images:"
  if docker image ls --format "{{.Repository}}:{{.Tag}}" | grep -q "wsl-ubuntu"; then
    docker image ls --format "  • {{.Repository}}:{{.Tag}} - {{.Size}}" | grep "wsl-ubuntu"
  else
    echo "  None found"
  fi
  echo ""

  # Cache directory
  echo "Cache Directory: $WSL_CACHE_DIR"
  if [[ -d "$WSL_CACHE_DIR" ]] && [[ -n "$(ls -A "$WSL_CACHE_DIR" 2>/dev/null)" ]]; then
    local cache_size
    cache_size=$(du -sh "$WSL_CACHE_DIR" 2>/dev/null | cut -f1 || echo "0")
    echo "Cache Size: $cache_size"
    echo "Cached Files:"
    # shellcheck disable=SC2012  # Using ls for human-readable output (size, name)
    ls -lh "$WSL_CACHE_DIR" | tail -n +2 | awk '{print "  • " $9 " - " $5}'
  else
    echo "Cache Size: 0"
    echo "Cached Files: None"
  fi
  echo ""

  # Running containers
  echo "Running Test Containers:"
  if docker ps --format "{{.Names}}" | grep -q "dotfiles-wsl-test"; then
    docker ps --format "  • {{.Names}} ({{.Status}})" | grep "dotfiles-wsl-test"
  else
    echo "  None"
  fi
}

# Main command handler
main() {
  if [[ $# -eq 0 ]] || [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    show_usage
  fi

  local command=$1
  shift

  case "$command" in
    list)
      list_images
      ;;
    build)
      build_image "${1:-24.04}"
      ;;
    remove)
      remove_image "$@"
      ;;
    clean)
      clean_cache
      ;;
    clean-all)
      clean_all
      ;;
    info)
      show_info
      ;;
    *)
      echo "Unknown command: $command"
      echo ""
      show_usage
      ;;
  esac
}

main "$@"
