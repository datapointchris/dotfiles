#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$(git rev-parse --show-toplevel)}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
source "$DOTFILES_DIR/install/common/lib/wsl-rootfs.sh"

WSL_CACHE_DIR="${DOTFILES_DIR}/.wsl-rootfs-cache"

show_usage() {
  help_header "docker-images" "Manage WSL Ubuntu Docker images for testing"
  help_usage "$(basename "$0") COMMAND [OPTIONS]"

  help_section "Commands"
  help_row "list" "" "List available WSL Docker images"
  help_row "build" "VERSION" "Build/rebuild Docker image (any Ubuntu release publishing a WSL image)"
  help_row "remove" "VERSION" "Remove Docker image"
  help_row "clean" "" "Remove all cached rootfs files"
  help_row "clean-all" "" "Remove both images and cached files"
  help_row "info" "" "Show cache and image information"

  help_section "Examples"
  help_row "$(basename "$0") list"
  help_row "$(basename "$0") build 26.04"
  help_row "$(basename "$0") remove 26.04"
  help_row "$(basename "$0") clean"

  help_end
  exit 0
}

# List Docker images
list_images() {
  print_section "WSL Docker Images"

  if docker image ls --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep -q "wsl-ubuntu"; then
    docker image ls --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep -E "REPOSITORY|wsl-ubuntu"
  else
    echo "No WSL Docker images found"
    echo ""
    echo "Build an image with: $(basename "$0") build $DEFAULT_UBUNTU_VERSION"
  fi
}

# Build Docker image
build_image() {
  local version=${1:-$DEFAULT_UBUNTU_VERSION}
  local docker_image="wsl-ubuntu:${version}"
  local rootfs_file

  print_section "Building WSL Docker Image"
  echo "Version: Ubuntu ${version}"
  echo "Image: ${docker_image}"
  echo ""

  rootfs_file=$(wsl_rootfs_fetch "$version" "$WSL_CACHE_DIR") || die "Could not fetch a rootfs for Ubuntu $version"

  echo ""
  log_info "Importing rootfs into Docker..."
  wsl_rootfs_import "$rootfs_file" "$docker_image"

  echo ""
  log_success "Built Docker image: $docker_image"

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

  local docker_image="wsl-ubuntu:${version}"

  print_section "Removing WSL Docker Image"
  echo "Image: ${docker_image}"
  echo ""

  if docker image inspect "$docker_image" >/dev/null 2>&1; then
    docker rmi "$docker_image"
    log_success "Removed image: $docker_image"
  else
    log_warning "Image not found: $docker_image"
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
      log_success "Cleaned cache directory"
    else
      log_info "Cache directory is already empty"
    fi
  else
    log_info "Cache directory does not exist"
  fi
}

# Clean everything
clean_all() {
  print_section "Cleaning All WSL Docker Resources"
  echo ""

  # Remove images
  log_info "Checking for WSL Docker images..."
  if docker image ls --format "{{.Repository}}:{{.Tag}}" | grep -q "wsl-ubuntu"; then
    docker image ls --format "{{.Repository}}:{{.Tag}}" | grep "wsl-ubuntu" | while read -r image; do
      log_info "Removing image: $image"
      docker rmi "$image" >/dev/null
    done
    log_success "Removed all WSL Docker images"
  else
    log_info "No WSL Docker images found"
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
      build_image "${1:-$DEFAULT_UBUNTU_VERSION}"
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
