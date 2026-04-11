#!/usr/bin/env bash
# ================================================================
# Docker Helper Functions for Bats Integration Tests
# ================================================================
# Provides container lifecycle management for testing installers
# with real network calls in isolated Docker environments
# ================================================================

# Configuration
DOCKER_IMAGE="dotfiles-test-base:ubuntu-24.04"
DOCKER_CONTAINER_PREFIX="bats-test"

# Start a test container and return its ID
# Usage: container_id=$(start_test_container)
start_test_container() {
  local container_name="${DOCKER_CONTAINER_PREFIX}-$(date +%s)-$$"

  docker run -d \
    --name "$container_name" \
    --user testuser \
    --mount type=bind,source="$DOTFILES_DIR",target=/home/testuser/dotfiles,readonly \
    "$DOCKER_IMAGE" \
    sleep infinity >/dev/null

  echo "$container_name"
}

# Execute command in container with proper environment
# Usage: docker_exec "$container_id" "command"
docker_exec() {
  local container_id="$1"
  shift

  docker exec \
    --user testuser \
    --workdir /home/testuser/dotfiles \
    -e DOTFILES_DOCKER_TEST=true \
    -e PATH=/home/testuser/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    ${GITHUB_TOKEN:+-e GITHUB_TOKEN="$GITHUB_TOKEN"} \
    "$container_id" \
    bash -c "$@"
}

# Clean up test container
# Usage: cleanup_test_container "$container_id"
cleanup_test_container() {
  local container_id="$1"

  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
}

# Verify base image exists
# Usage: verify_docker_base_image
verify_docker_base_image() {
  if ! docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    echo "Error: Docker base image not found: $DOCKER_IMAGE" >&2
    echo "Build it with: cd tests/install/docker && ./build-base.sh" >&2
    return 1
  fi
  return 0
}

# Setup function for Bats tests
# Call this in setup_file() to verify Docker is available
docker_test_setup() {
  # Check if Docker is available
  if ! command -v docker >/dev/null 2>&1; then
    skip "Docker not available"
  fi

  # Verify base image exists
  if ! verify_docker_base_image; then
    skip "Docker base image not built"
  fi

  # Resolve GitHub token for authenticated API calls inside containers.
  # docker_exec passes GITHUB_TOKEN when set; gh CLI is not available inside
  # the container, so we must resolve it here on the host.
  if [[ -z "${GITHUB_TOKEN:-}" ]] && command -v gh &>/dev/null; then
    GITHUB_TOKEN=$(gh auth token 2>/dev/null || true)
    export GITHUB_TOKEN
  fi
}

# Cleanup function for per-test containers
# Call this in teardown() to ensure container is removed
docker_test_teardown() {
  if [[ -n "${BATS_TEST_CONTAINER:-}" ]]; then
    cleanup_test_container "$BATS_TEST_CONTAINER"
    unset BATS_TEST_CONTAINER
  fi
}

# Cleanup function for per-file shared containers
# Call this in teardown_file() when using BATS_SHARED_CONTAINER
#
# Shared container pattern: start one container in setup_file() with
#   BATS_SHARED_CONTAINER=$(start_test_container)
# All tests in the file reuse it, then teardown_file() cleans up.
docker_shared_test_teardown() {
  if [[ -n "${BATS_SHARED_CONTAINER:-}" ]]; then
    cleanup_test_container "$BATS_SHARED_CONTAINER"
    unset BATS_SHARED_CONTAINER
  fi
}
