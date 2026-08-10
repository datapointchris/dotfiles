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
  help_row "show" "" "Images, cached rootfs files and running test containers"
  help_row "build" "[VERSION]" "Build/rebuild Docker image (any Ubuntu release publishing a WSL image)"
  help_row "delete" "[VERSION]" "Delete one image, or every WSL image when no version is given"
  help_row "prune" "[VERSION]" "Delete one cached rootfs, or the whole cache when no version is given"

  help_section "Examples"
  help_row "$(basename "$0") list"
  help_row "$(basename "$0") build 26.04"
  help_row "$(basename "$0") delete 26.04"
  help_row "$(basename "$0") prune"

  help_end
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

# A version deletes that image; no version deletes every WSL image. Scope is the
# argument's presence rather than a flag, so deleting the images never implies
# discarding a ~400MB download that `prune` owns.
delete_image() {
  local version=${1:-}

  if [[ -n "$version" ]]; then
    local docker_image="wsl-ubuntu:${version}"
    print_section "Deleting WSL Docker Image"
    echo "Image: ${docker_image}"
    echo ""

    if docker image inspect "$docker_image" >/dev/null 2>&1; then
      docker rmi "$docker_image"
      log_success "Deleted image: $docker_image"
    else
      log_warning "Image not found: $docker_image"
    fi
    return
  fi

  print_section "Deleting Every WSL Docker Image"
  echo ""

  if ! docker image ls --format "{{.Repository}}:{{.Tag}}" | grep -q "wsl-ubuntu"; then
    log_info "No WSL Docker images found"
    return
  fi

  docker image ls --format "{{.Repository}}:{{.Tag}}" | grep "wsl-ubuntu" | while read -r image; do
    log_info "Deleting image: $image"
    docker rmi "$image" >/dev/null
  done
  log_success "Deleted every WSL Docker image"
}

# A version prunes that release's cached rootfs; no version prunes the whole
# cache. Each file is ~400MB and re-downloading is the cost, so deleting one
# release's is worth being able to say.
prune_cache() {
  local version=${1:-}

  if [[ ! -d "$WSL_CACHE_DIR" ]]; then
    log_info "Cache directory does not exist"
    return
  fi

  local cache_size
  cache_size=$(du -sh "$WSL_CACHE_DIR" 2>/dev/null | cut -f1 || echo "0")
  print_section "Pruning Cached Rootfs Files"
  echo "Cache directory: $WSL_CACHE_DIR"
  echo "Current size: $cache_size"
  echo ""

  if [[ -n "$version" ]]; then
    local matched=0
    for cached in "$WSL_CACHE_DIR"/ubuntu-"$version"*.wsl; do
      [[ -e "$cached" ]] || continue
      matched=1
      log_info "Deleting $(basename "$cached")"
      rm -f "$cached"
    done
    if [[ $matched -eq 0 ]]; then
      log_warning "Nothing cached for Ubuntu $version"
    else
      log_success "Pruned the Ubuntu $version rootfs"
    fi
    return
  fi

  if [[ -z "$(ls -A "$WSL_CACHE_DIR" 2>/dev/null)" ]]; then
    log_info "Cache directory is already empty"
    return
  fi

  echo "Deleting cached files:"
  ls -lh "$WSL_CACHE_DIR"
  echo ""
  rm -rf "${WSL_CACHE_DIR:?}"/*
  log_success "Pruned the cache directory"
}

show_wsl_resources() {
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

  # `dotfiles-e2e` is the prefix `harness.container_name` builds every name from,
  # worktree suffix included. This read `dotfiles-wsl-test`, which nothing has
  # been called since the harness took over naming, so it reported None against a
  # box with four containers up.
  echo "Running Test Containers:"
  if docker ps --format "{{.Names}}" | grep -q "dotfiles-e2e"; then
    docker ps --format "  • {{.Names}} ({{.Status}})" | grep "dotfiles-e2e"
  else
    echo "  None"
  fi
}

# Main command handler
main() {
  if [[ $# -eq 0 ]] || [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    show_usage
    exit 0
  fi

  local command=$1
  shift

  case "$command" in
    list)
      list_images
      ;;
    show)
      show_wsl_resources
      ;;
    build)
      build_image "${1:-$DEFAULT_UBUNTU_VERSION}"
      ;;
    delete)
      delete_image "${1:-}"
      ;;
    prune)
      prune_cache "${1:-}"
      ;;
    *)
      echo "Unknown command: $command"
      echo ""
      show_usage
      # 2 is a usage error. Printing help and exiting 0 reported a typo to the
      # caller as a successful run.
      exit 2
      ;;
  esac
}

main "$@"
