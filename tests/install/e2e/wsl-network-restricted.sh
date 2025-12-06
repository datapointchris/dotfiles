#!/usr/bin/env bash
# ================================================================
# WSL Installation Testing Script (Network-Restricted)
# ================================================================
# Tests WSL installation using Docker with GitHub downloads blocked
# Simulates corporate firewall blocking githubusercontent.com domains
#
# Verifies refactored installation system (Option B):
#   - Installation continues despite failures
#   - Only ONE failure log file is created (/tmp/dotfiles-install-failures-*.txt)
#   - ALL failures are reported to that single log
#   - Summary is displayed at the end
#   - Structured failure data is properly captured
# ================================================================

set -euo pipefail

# Source shared test helpers (includes formatting library)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$DOTFILES_DIR/tests/install/helpers.sh"

# Show usage
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Test WSL installation with GitHub downloads blocked (simulates corporate firewall)"
  echo ""
  echo "Options:"
  echo "  -v, --version VERSION  Ubuntu version to test (22.04 or 24.04, default: 24.04)"
  echo "  -k, --keep            Keep container after test (for debugging)"
  echo "  -f, --test-fonts      Enable font installation testing (fonts skipped by default)"
  echo "  -h, --help            Show this help message"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")          # Test with Ubuntu 24.04 (default)"
  echo "  $(basename "$0") -v 22.04 # Test with Ubuntu 22.04"
  echo "  $(basename "$0") -k       # Keep container for debugging"
  exit 0
fi

# Parse arguments
UBUNTU_VERSION="24.04"
KEEP_CONTAINER=false
TEST_FONTS=false
while [[ $# -gt 0 ]]; do
  case $1 in
    -v|--version)
      UBUNTU_VERSION="${2:-24.04}"
      shift 2
      ;;
    -k|--keep)
      KEEP_CONTAINER=true
      shift
      ;;
    -f|--test-fonts)
      TEST_FONTS=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
  esac
done

# Configuration
WSL_CACHE_DIR="${DOTFILES_DIR}/.wsl-rootfs-cache"
LOG_FILE="${DOTFILES_DIR}/test-wsl-network-restricted.log"
CONTAINER_NAME="dotfiles-wsl-restricted-$(date '+%Y%m%d-%H%M%S')"

# Determine Ubuntu codename and file format
case "$UBUNTU_VERSION" in
  22.04)
    UBUNTU_CODENAME="jammy"
    ROOTFS_URL="https://cloud-images.ubuntu.com/wsl/${UBUNTU_CODENAME}/current/ubuntu-${UBUNTU_CODENAME}-wsl-amd64-ubuntu${UBUNTU_VERSION}lts.rootfs.tar.gz"
    ROOTFS_FILE="${WSL_CACHE_DIR}/ubuntu-${UBUNTU_CODENAME}-wsl-amd64-ubuntu${UBUNTU_VERSION}lts.rootfs.tar.gz"
    ;;
  24.04)
    UBUNTU_CODENAME="noble"
    ROOTFS_URL="https://releases.ubuntu.com/${UBUNTU_CODENAME}/ubuntu-${UBUNTU_VERSION}.3-wsl-amd64.wsl"
    ROOTFS_FILE="${WSL_CACHE_DIR}/ubuntu-${UBUNTU_VERSION}.3-wsl-amd64.wsl"
    ;;
  *)
    die "Unsupported Ubuntu version: $UBUNTU_VERSION (use 22.04 or 24.04)"
    ;;
esac

DOCKER_IMAGE="wsl-ubuntu:${UBUNTU_VERSION}"

# Test tracking
FAILURE_TRACKER="/tmp/test-failures-$$"
: > "$FAILURE_TRACKER"  # Create empty file
# shellcheck disable=SC2030,SC2031

# Cleanup function
cleanup() {
  local exit_code=$?

  if [[ "$KEEP_CONTAINER" == false ]]; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
      echo ""
      log_info "Cleaning up container: $CONTAINER_NAME"
      docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
  else
    if [[ $exit_code -ne 0 ]] || [[ $(wc -l < "$FAILURE_TRACKER" 2>/dev/null || echo 0) -gt 0 ]]; then
      echo ""
      log_info "Container kept for debugging: $CONTAINER_NAME"
      echo "  • Shell into container: docker exec -it $CONTAINER_NAME bash"
      echo "  • View failure log: docker exec $CONTAINER_NAME cat /tmp/dotfiles-install-failures-*.txt"
      echo "  • Remove container: docker rm -f $CONTAINER_NAME"
    fi
  fi
}

# Register cleanup on exit
trap cleanup EXIT

# Overwrite log file (not append)
: > "$LOG_FILE"

log_info "Testing WSL installation with network restrictions"
log_info "Ubuntu version: ${UBUNTU_VERSION} (${UBUNTU_CODENAME})"
log_info "Docker image: ${DOCKER_IMAGE}"
log_info "Container: ${CONTAINER_NAME}"
log_info "Log file: ${LOG_FILE}"
echo ""

# Track overall start time
OVERALL_START=$(date +%s)

# ================================================================
# STEP 1: Ensure Docker image exists
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 1/6: Preparing WSL Ubuntu Docker Image"

  # Check if Docker is running
  if ! docker info >/dev/null 2>&1; then
    die "Docker is not running. Please start Docker Desktop and try again."
  fi

  # Check if Docker image already exists
  if docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    log_success "Docker image already exists: $DOCKER_IMAGE"
  else
    echo "Docker image not found, will create from WSL rootfs..."
    echo ""

    # Create cache directory
    mkdir -p "$WSL_CACHE_DIR"

    # Download rootfs if not cached
    if [[ -f "$ROOTFS_FILE" ]]; then
      log_success "Using cached WSL rootfs: $ROOTFS_FILE"
    else
      echo "Downloading WSL Ubuntu ${UBUNTU_VERSION} rootfs..."
      echo "URL: $ROOTFS_URL"
      echo "This is a one-time download (~340MB)..."
      echo ""
      curl -L --progress-bar "$ROOTFS_URL" -o "$ROOTFS_FILE"
      log_success "Downloaded WSL rootfs to cache"
    fi

    # Import rootfs into Docker
    echo ""
    echo "Importing WSL rootfs into Docker..."
    if [[ "$ROOTFS_FILE" == *.wsl ]]; then
      docker import - "$DOCKER_IMAGE" < "$ROOTFS_FILE"
    else
      gunzip -c "$ROOTFS_FILE" | docker import - "$DOCKER_IMAGE"
    fi
    log_success "Created Docker image: $DOCKER_IMAGE"
  fi
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
{
  log_timing "Step 1: Prepare Docker image" "$((STEP_END - STEP_START))"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 2: Start container and configure network restrictions
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 2/6: Starting Container with Network Restrictions"
  echo "Starting container with dotfiles mounted..."

  # Determine user
  if docker run --rm "$DOCKER_IMAGE" id ubuntu &>/dev/null; then
    USER_FLAG="--user ubuntu"
    HOME_DIR="/home/ubuntu"
  else
    echo "Warning: Running as root (ubuntu user not found in image)"
    USER_FLAG=""
    HOME_DIR="/root"
  fi

  # Set SKIP_FONTS based on --test-fonts flag
  SKIP_FONTS_ENV=""
  if [[ "$TEST_FONTS" == "false" ]]; then
    SKIP_FONTS_ENV="--env SKIP_FONTS=1"
  fi

  # Start container
  # shellcheck disable=SC2086
  docker run -d \
    --name "$CONTAINER_NAME" \
    $USER_FLAG \
    --env PATH="$HOME_DIR/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    --env HOME="$HOME_DIR" \
    --env DOTFILES_DOCKER_TEST=true \
    $SKIP_FONTS_ENV \
    --mount type=bind,source="$DOTFILES_DIR",target=/dotfiles,readonly \
    "$DOCKER_IMAGE" \
    /usr/bin/sleep infinity

  log_success "Container started: $CONTAINER_NAME"
  echo ""

  # Block GitHub release downloads via DNS (simulates corporate firewall)
  # Note: We only block the CDN domains where binaries are served, not github.com itself
  # This allows API/metadata access but blocks actual downloads
  echo "Blocking GitHub release downloads (simulating corporate firewall)..."
  docker exec "$CONTAINER_NAME" bash -c "
    echo '127.0.0.1 objects.githubusercontent.com' >> /etc/hosts
    echo '127.0.0.1 release-assets.githubusercontent.com' >> /etc/hosts
    echo '127.0.0.1 github-releases.githubusercontent.com' >> /etc/hosts
    echo '127.0.0.1 raw.githubusercontent.com' >> /etc/hosts
  "

  # Verify blocking
  echo "Verifying network restrictions..."
  docker exec "$CONTAINER_NAME" bash -c "grep githubusercontent /etc/hosts"
  log_success "GitHub release downloads blocked (API access still allowed)"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
{
  log_timing "Step 2: Network restrictions" "$((STEP_END - STEP_START))"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 3: Prepare container environment
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 3/6: Preparing Container Environment"

  # Detect home directory
  CONTAINER_HOME=$(docker exec "$CONTAINER_NAME" bash -c 'echo $HOME')

  # Create ~/.env for testing
  echo "Creating ~/.env..."
  docker exec "$CONTAINER_NAME" bash -c 'cat > ~/.env <<EOF
PLATFORM=wsl
NVIM_AI_ENABLED=false
EOF'

  # Copy dotfiles to writable location
  echo "Copying dotfiles to writable location..."
  docker exec "$CONTAINER_NAME" bash -c "cp -r /dotfiles ${CONTAINER_HOME}/dotfiles"

  log_success "Container environment ready"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
{
  log_timing "Step 3: Prepare environment" "$((STEP_END - STEP_START))"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 4: Run installation script (expect failures)
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 4/6: Running install.sh with Blocked Downloads"
  echo "Executing WSL installation (GitHub downloads will fail)..."
  echo ""

  CONTAINER_HOME=$(docker exec "$CONTAINER_NAME" bash -c 'echo $HOME')
  # Continue even if install.sh exits with error (we expect failures)
  docker exec "$CONTAINER_NAME" bash "${CONTAINER_HOME}/dotfiles/install.sh" || {
    log_info "Installation completed with some failures (expected)"
  }
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
{
  log_timing "Step 4: Installation" "$((STEP_END - STEP_START))"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 5: Verify failure reporting
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 5/6: Verifying Failure Reporting"
  echo "Validating that all failures were properly logged..."
  echo ""

  CONTAINER_HOME=$(docker exec "$CONTAINER_NAME" bash -c 'echo $HOME')

  # Test 1: Verify only ONE failure log file exists
  echo "Test 1: Checking for single failure log file..."
  FAILURE_LOG_COUNT=$(docker exec "$CONTAINER_NAME" bash -c "ls -1 /tmp/dotfiles-install-failures-*.txt 2>/dev/null | wc -l")
  if [[ "$FAILURE_LOG_COUNT" -eq 1 ]]; then
    log_success "✓ Only ONE failure log file created"
  else
    log_error "✗ Expected 1 failure log, found $FAILURE_LOG_COUNT"
    docker exec "$CONTAINER_NAME" bash -c "ls -la /tmp/dotfiles-install-failures-*.txt 2>/dev/null || true"
    echo "F" >> "$FAILURE_TRACKER"
  fi
  echo ""

  # Get failure log path
  FAILURE_LOG=$(docker exec "$CONTAINER_NAME" bash -c "ls /tmp/dotfiles-install-failures-*.txt 2>/dev/null | head -1" || echo "")

  if [[ -n "$FAILURE_LOG" ]]; then
    # Test 2: Count failures in log (expect 8-10 GitHub tools)
    echo "Test 2: Counting failures in log..."
    FAILURE_COUNT=$(docker exec "$CONTAINER_NAME" bash -c "grep -c \"^---\$\" $FAILURE_LOG || echo 0")
    echo "  Found $FAILURE_COUNT tool failures"
    if [[ $FAILURE_COUNT -ge 7 ]]; then
      log_success "✓ Multiple GitHub tool failures logged (>= 7)"
    else
      log_error "✗ Expected at least 7 GitHub tool failures, found $FAILURE_COUNT"
      echo "F" >> "$FAILURE_TRACKER"
    fi
    echo ""

    # Test 3: Verify specific tools are logged
    echo "Test 3: Verifying specific tools failed as expected..."
    EXPECTED_FAILURES=("yazi" "glow" "duf" "lazygit" "neovim")
    for tool in "${EXPECTED_FAILURES[@]}"; do
      if docker exec "$CONTAINER_NAME" bash -c "grep -q \"$tool - Installation Failed\" $FAILURE_LOG"; then
        echo "  ✓ $tool failure logged"
      else
        log_warning "  ✗ $tool failure NOT logged (expected due to GitHub block)"
        # Don't fail test - some tools might be installed via apt fallback
      fi
    done
    echo ""

    # Test 4: Display failure log summary
    echo "Test 4: Failure log contents:"
    docker exec "$CONTAINER_NAME" bash -c "grep \" - Installation Failed\" $FAILURE_LOG | sed 's/^/  - /'"
    echo ""

    # Test 5: Verify installation log shows summary
    echo "Test 5: Checking that summary was displayed..."
    if grep -q "Installation Summary" "$LOG_FILE"; then
      log_success "✓ Summary was displayed during installation"
    else
      log_error "✗ Summary was NOT displayed during installation"
      echo "F" >> "$FAILURE_TRACKER"
    fi
    echo ""

  else
    log_error "✗ No failure log file found at all!"
    docker exec "$CONTAINER_NAME" bash -c "ls -la /tmp/ | grep dotfiles || true"
    echo "F" >> "$FAILURE_TRACKER"
  fi

  # Test 6: Verify apt packages still worked
  echo "Test 6: Verifying apt packages installed successfully..."
  if docker exec "$CONTAINER_NAME" dpkg -l build-essential >/dev/null 2>&1; then
    log_success "✓ Apt packages installed (build-essential found)"
  else
    log_error "✗ Apt packages failed to install"
    echo "F" >> "$FAILURE_TRACKER"
  fi
  echo ""

} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
{
  log_timing "Step 5: Verify failures" "$((STEP_END - STEP_START))"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 6: Display failure log for debugging
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 6/6: Failure Log Details"

  FAILURE_LOG=$(docker exec "$CONTAINER_NAME" bash -c "ls /tmp/dotfiles-install-failures-*.txt 2>/dev/null | head -1" || echo "")

  if [[ -n "$FAILURE_LOG" ]]; then
    echo "Full failure log contents:"
    echo "════════════════════════════════════════════════════════════════"
    docker exec "$CONTAINER_NAME" bash -c "cat $FAILURE_LOG"
    echo "════════════════════════════════════════════════════════════════"
  else
    log_warning "No failure log found to display"
  fi
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
{
  log_timing "Step 6: Display failure log" "$((STEP_END - STEP_START))"
} 2>&1 | tee -a "$LOG_FILE"

# Calculate overall time
OVERALL_END=$(date +%s)
OVERALL_ELAPSED=$((OVERALL_END - OVERALL_START))

# Summary
{
  echo ""
  if [[ $(wc -l < "$FAILURE_TRACKER" 2>/dev/null || echo 0) -eq 0 ]]; then
    print_header_success "Network-Restricted Test PASSED"
  else
    print_header_error "Network-Restricted Test FAILED"
  fi
  echo ""

  print_section "Test Results" "cyan"
  echo ""
  echo "  Failure Handling Tests:"
  if [[ $(wc -l < "$FAILURE_TRACKER" 2>/dev/null || echo 0) -eq 0 ]]; then
    echo "    ✓ All tests passed"
    echo "    ✓ Only ONE failure log created"
    echo "    ✓ Multiple GitHub failures logged"
    echo "    ✓ Summary displayed correctly"
    echo "    ✓ Installation continued despite failures"
  else
    echo "    ✗ $(wc -l < "$FAILURE_TRACKER" 2>/dev/null || echo 0) test(s) failed"
    echo "    Review the log above for details"
  fi
  echo ""

  print_section "Test Information" "cyan"
  echo ""
  echo "  Ubuntu version: ${UBUNTU_VERSION} (${UBUNTU_CODENAME})"
  echo "  Docker image: ${DOCKER_IMAGE}"
  echo "  Container: ${CONTAINER_NAME}"
  echo "  Log file: ${LOG_FILE}"
  echo "  Total time: $(format_time "$OVERALL_ELAPSED")"
  echo ""

  if [[ "$KEEP_CONTAINER" == false ]]; then
    print_section "Cleanup" "cyan"
    echo "  Container will be removed automatically"
  else
    print_section "Debug Information" "cyan"
    echo "  Container kept for debugging"
    echo "  • Shell into container: docker exec -it $CONTAINER_NAME bash"
    echo "  • View failure log: docker exec $CONTAINER_NAME cat /tmp/dotfiles-install-failures-*.txt"
    echo "  • Remove when done: docker rm -f $CONTAINER_NAME"
  fi
  echo ""
} 2>&1 | tee -a "$LOG_FILE"

# Exit with error if any tests failed
if [[ $(wc -l < "$FAILURE_TRACKER" 2>/dev/null || echo 0) -gt 0 ]]; then
  rm -f "$FAILURE_TRACKER" 2>/dev/null || true
  exit 1
fi

# Clean up test tracker file
rm -f "$FAILURE_TRACKER" 2>/dev/null || true
