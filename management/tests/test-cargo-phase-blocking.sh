#!/usr/bin/env bash
# ================================================================
# Quick Cargo Phase Test with Network Blocking
# ================================================================
# Tests just the cargo package installation phase with GitHub CDN blocked
# Should take ~2-3 minutes instead of full 12-minute integration test
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Configuration
UBUNTU_VERSION="24.04"
DOCKER_IMAGE="wsl-ubuntu:${UBUNTU_VERSION}"
CONTAINER_NAME="dotfiles-cargo-test-$(date '+%Y%m%d-%H%M%S')"
LOG_FILE="${DOTFILES_DIR}/test-cargo-phase.log"

# Overwrite log file
: > "$LOG_FILE"

log_info "Quick Cargo Phase Test with Network Blocking"
log_info "Container: ${CONTAINER_NAME}"
echo ""

# Cleanup function
cleanup() {
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_info "Cleaning up container: $CONTAINER_NAME"
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# ================================================================
# Step 1: Ensure Docker image exists
# ================================================================
log_section "STEP 1/4: Checking Docker Image"
if ! docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
  echo "Docker image not found. Run the full test first to create it:"
  echo "  bash management/tests/test-install-wsl-network-restricted.sh"
  exit 1
fi
log_success "Docker image exists: $DOCKER_IMAGE"
echo ""

# ================================================================
# Step 2: Start container with network restrictions
# ================================================================
log_section "STEP 2/4: Starting Container with Network Restrictions"

docker run -d \
  --name "$CONTAINER_NAME" \
  --env HOME="/root" \
  --env DOTFILES_DOCKER_TEST=true \
  --mount type=bind,source="$DOTFILES_DIR",target=/dotfiles,readonly \
  "$DOCKER_IMAGE" \
  /usr/bin/sleep infinity

log_success "Container started"

# Block GitHub CDN domains
log_info "Blocking GitHub CDN domains..."
docker exec "$CONTAINER_NAME" bash -c "
  echo '127.0.0.1 objects.githubusercontent.com' >> /etc/hosts
  echo '127.0.0.1 release-assets.githubusercontent.com' >> /etc/hosts
  echo '127.0.0.1 github-releases.githubusercontent.com' >> /etc/hosts
  echo '127.0.0.1 raw.githubusercontent.com' >> /etc/hosts
"

log_success "GitHub CDN blocked (API still accessible)"
echo ""

# ================================================================
# Step 3: Prepare environment and install prerequisites
# ================================================================
log_section "STEP 3/4: Preparing Environment"

docker exec "$CONTAINER_NAME" bash -c "
  export HOME=/root

  # Copy dotfiles to writable location
  cp -r /dotfiles /root/dotfiles

  # Install minimal dependencies
  apt-get update >/dev/null 2>&1
  apt-get install -y curl build-essential >/dev/null 2>&1

  # Install Rust
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y >/dev/null 2>&1
  source ~/.cargo/env

  # Install cargo-binstall
  curl -L --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh | bash >/dev/null 2>&1
"

log_success "Environment ready, Rust and cargo-binstall installed"
echo ""

# ================================================================
# Step 4: Run cargo package installation with blocking
# ================================================================
log_section "STEP 4/4: Installing Cargo Packages (with blocking)"

echo "This will test if:"
echo "  1. Downloads fail (CDN is blocked)"
echo "  2. Packages fall back to source compilation"
echo "  3. Failures are reported to registry"
echo ""

docker exec "$CONTAINER_NAME" bash -c "
  export HOME=/root
  export DOTFILES_DIR=/root/dotfiles
  source ~/.cargo/env
  cd /root/dotfiles

  # Source libraries
  source platforms/common/.local/shell/logging.sh
  source platforms/common/.local/shell/formatting.sh
  source management/common/lib/install-helpers.sh

  # Initialize failure registry
  init_failure_registry

  # Run cargo installation script
  bash management/common/install/language-tools/cargo-tools.sh 2>&1

  # Display summary
  display_failure_summary
" | tee -a "$LOG_FILE"

echo ""

# ================================================================
# Verify results
# ================================================================
log_section "Verifying Results"

# Check for failure log
if docker exec "$CONTAINER_NAME" ls /tmp/dotfiles-installation-failures-*.txt >/dev/null 2>&1; then
  FAILURE_LOG=$(docker exec "$CONTAINER_NAME" bash -c "ls /tmp/dotfiles-installation-failures-*.txt | head -1")
  log_success "✓ Failure log created: $FAILURE_LOG"

  # Count failures
  FAILURE_COUNT=$(docker exec "$CONTAINER_NAME" bash -c "grep -c \"^TOOL='\" $FAILURE_LOG || echo 0")
  log_info "  Found $FAILURE_COUNT cargo package failures"

  # Show failures
  echo ""
  echo "Failed packages:"
  docker exec "$CONTAINER_NAME" bash -c "grep \"^TOOL=\" $FAILURE_LOG | sed \"s/TOOL='//g\" | sed \"s/'//g\" | sed 's/^/  - /'"

else
  log_warning "No failure log found (all packages may have succeeded or fallen back to source)"
fi

echo ""
log_success "Cargo phase test complete!"
log_info "Full log: $LOG_FILE"
