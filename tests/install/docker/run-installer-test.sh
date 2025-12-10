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

if [[ $# -lt 1 ]] || [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") INSTALLER_SCRIPT [OPTIONS]"
  echo ""
  echo "Run an installer script in a Docker container with system packages pre-installed"
  echo ""
  echo "Arguments:"
  echo "  INSTALLER_SCRIPT   Path to installer script (relative to dotfiles root)"
  echo ""
  echo "Options:"
  echo "  --keep            Keep container after test (for debugging)"
  echo "  -h, --help        Show this help message"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0") management/wsl/install/system-packages.sh"
  echo "  $(basename "$0") management/common/install/github-releases/lazygit.sh"
  echo "  $(basename "$0") management/common/install/github-releases/lazygit.sh --keep"
  exit 0
fi

INSTALLER_SCRIPT="$1"
shift

KEEP_CONTAINER=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --keep)
      KEEP_CONTAINER=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
  esac
done

IMAGE_NAME="dotfiles-test-base:ubuntu-24.04"
CONTAINER_NAME="dotfiles-test-$(date +%s)"

if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
  log_error "Base image not found: $IMAGE_NAME"
  log_info "Build it first with: ./build-base.sh"
  exit 1
fi

if [[ ! -f "$DOTFILES_DIR/$INSTALLER_SCRIPT" ]]; then
  log_error "Installer script not found: $INSTALLER_SCRIPT"
  exit 1
fi

print_header "Running Installer Test"

log_info "Base image: $IMAGE_NAME"
log_info "Container: $CONTAINER_NAME"
log_info "Installer: $INSTALLER_SCRIPT"

START_TIME=$(date +%s)

# shellcheck disable=SC2317
cleanup_container() {
  if [[ "$KEEP_CONTAINER" == "true" ]]; then
    log_info "Container kept for debugging: $CONTAINER_NAME"
    log_info "Connect with: docker exec -it $CONTAINER_NAME /bin/bash"
    log_info "Remove with: docker rm -f $CONTAINER_NAME"
  else
    log_info "Cleaning up container..."
    docker rm -f "$CONTAINER_NAME" &>/dev/null || true
  fi
}

trap cleanup_container EXIT

log_info "Starting container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --user testuser \
  "$IMAGE_NAME" \
  sleep infinity >/dev/null

log_info "Copying current dotfiles to container..."
docker cp "$DOTFILES_DIR/." "$CONTAINER_NAME:/home/testuser/dotfiles/"

log_info "Fixing file ownership..."
docker exec --user root "$CONTAINER_NAME" chown -R testuser:testuser /home/testuser/dotfiles

log_info "Running installer script..."
echo ""
echo "────────────────────────────────────────────────────────────────"

if docker exec \
  --user testuser \
  --workdir /home/testuser/dotfiles \
  -e DOTFILES_DOCKER_TEST=true \
  "$CONTAINER_NAME" \
  bash "$INSTALLER_SCRIPT"; then

  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))

  echo "────────────────────────────────────────────────────────────────"
  echo ""
  log_success "Installer test completed"
  log_info "Duration: ${DURATION}s"

  exit 0
else
  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))

  echo "────────────────────────────────────────────────────────────────"
  echo ""
  log_error "Installer test failed"
  log_info "Duration: ${DURATION}s"

  if [[ "$KEEP_CONTAINER" == "false" ]]; then
    log_info "Tip: Run with --keep to inspect the container"
  fi

  exit 1
fi
