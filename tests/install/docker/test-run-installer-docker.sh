#!/usr/bin/env bash
# ================================================================
# Test: run_installer Wrapper in Docker
# ================================================================
# Tests the complete install.sh flow in Docker with blocked network
# Validates: failure log creation, output visibility, proper exit codes
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"

echo "=========================================="
echo "Test: run_installer in Docker"
echo "=========================================="
echo ""

CONTAINER_NAME="test-run-installer-$(date +%s)"
DOCKER_IMAGE="ubuntu:24.04"

# Cleanup function
# shellcheck disable=SC2317  # Function invoked via trap
# shellcheck disable=SC2317  # Invoked via trap
cleanup() {
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_info "Removing container: $CONTAINER_NAME"
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

log_info "Creating Ubuntu container..."
docker run -d --name "$CONTAINER_NAME" "$DOCKER_IMAGE" sleep 3600 >/dev/null

log_info "Installing base dependencies..."
docker exec "$CONTAINER_NAME" bash -c "apt-get update -qq && apt-get install -y -qq curl tar gzip >/dev/null 2>&1"

log_info "Copying dotfiles to container..."
docker cp "$DOTFILES_DIR" "$CONTAINER_NAME:/root/dotfiles"

log_info "Blocking GitHub CDN in container..."
docker exec "$CONTAINER_NAME" bash -c "echo '127.0.0.1 objects.githubusercontent.com' >> /etc/hosts"
docker exec "$CONTAINER_NAME" bash -c "echo '127.0.0.1 github-releases.githubusercontent.com' >> /etc/hosts"
docker exec "$CONTAINER_NAME" bash -c "echo '127.0.0.1 api.github.com' >> /etc/hosts"

log_info "Copying test script to container..."
docker cp "$SCRIPT_DIR/docker-run-installer-test-script.sh" "$CONTAINER_NAME:/root/test-run-installer.sh"

log_info "Running test script in container..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker exec "$CONTAINER_NAME" bash /root/test-run-installer.sh
DOCKER_EXIT=$?
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


echo ""
if [[ $DOCKER_EXIT -eq 0 ]]; then
  log_success "=========================================="
  log_success "Docker run_installer test PASSED"
  log_success "  - run_installer wrapper works in Docker"
  log_success "  - Failure log created correctly"
  log_success "  - All structured fields captured"
  log_success "  - Output visible throughout"
  log_success "=========================================="
  exit 0
else
  log_error "=========================================="
  log_error "Docker run_installer test FAILED"
  log_error "  Exit code: $DOCKER_EXIT"
  log_error "=========================================="
  exit 1
fi
