#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(git rev-parse --show-toplevel)"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

print_header() {
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "  $1"
  echo "════════════════════════════════════════════════════════════════"
  echo ""
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Build reusable Docker base image with system packages installed"
  echo ""
  echo "Options:"
  echo "  --no-cache     Force rebuild without using Docker cache"
  echo "  -h, --help     Show this help message"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")              # Build with cache"
  echo "  $(basename "$0") --no-cache   # Force clean rebuild"
  exit 0
fi

USE_CACHE=true
while [[ $# -gt 0 ]]; do
  case $1 in
    --no-cache)
      USE_CACHE=false
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
  esac
done

print_header "Building Docker Base Image"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="dotfiles-test-base:ubuntu-24.04"

log_info "Building system-packages stage"
log_info "Image: $IMAGE_NAME"
log_info "Context: $DOTFILES_DIR"

START_TIME=$(date +%s)

BUILD_ARGS=(
  "build"
  "--target=system-packages"
  "--tag=$IMAGE_NAME"
  "--file=$SCRIPT_DIR/Dockerfile"
)

if [[ "$USE_CACHE" == "false" ]]; then
  log_info "Cache disabled - forcing clean rebuild"
  BUILD_ARGS+=("--no-cache")
fi

BUILD_ARGS+=("$DOTFILES_DIR")

if docker "${BUILD_ARGS[@]}"; then
  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))

  IMAGE_SIZE=$(docker images "$IMAGE_NAME" --format "{{.Size}}")

  echo ""
  log_success "Base image built successfully"
  log_info "Image: $IMAGE_NAME"
  log_info "Size: $IMAGE_SIZE"
  log_info "Build time: ${DURATION}s"

  echo ""
  log_info "Image ready for testing. Run:"
  echo "  ./run-installer-test.sh <installer-script-path>"
else
  log_error "Failed to build base image"
  exit 1
fi
