#!/usr/bin/env bash
# ================================================================
# Arch Linux Installation Testing Script (Docker-based)
# ================================================================
# Tests Arch Linux installation using Docker with official Arch image
# This provides realistic Arch environment for testing
# ================================================================

set -euo pipefail

# Source shared test helpers (includes formatting library)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/helpers.sh"

# Show usage
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Test Arch Linux installation script using Docker with official Arch image"
  echo ""
  echo "Options:"
  echo "  -k, --keep            Keep container after test (for debugging)"
  echo "  -h, --help            Show this help message"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")              # Test with latest Arch"
  echo "  $(basename "$0") -k           # Keep container for debugging"
  exit 0
fi

# Parse arguments
KEEP_CONTAINER=false
while [[ $# -gt 0 ]]; do
  case $1 in
    -k|--keep)
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

# Configuration
DOCKER_IMAGE="archlinux:latest"
LOG_FILE="${DOTFILES_DIR}/test-arch-docker.log"
CONTAINER_NAME="dotfiles-arch-test-$(date '+%Y%m%d-%H%M%S')"

# Timing arrays
declare -a STEP_NAMES
declare -a STEP_TIMES

# Cleanup function
cleanup() {
  cleanup_container "$CONTAINER_NAME" "$KEEP_CONTAINER"
}

# Register cleanup on exit
trap cleanup EXIT

# Overwrite log file (not append)
: > "$LOG_FILE"

log_info "Testing Arch Linux installation with Docker"
log_info "Docker image: ${DOCKER_IMAGE}"
log_info "Container: ${CONTAINER_NAME}"
log_info "Log file: ${LOG_FILE}"
echo ""

# Track overall start time
OVERALL_START=$(date +%s)

# ================================================================
# STEP 1: Ensure Docker image is available
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 1/7: Preparing Arch Linux Docker Image"

  check_docker

  # Pull latest official Arch image
  if docker_image_exists "$DOCKER_IMAGE"; then
    log_success "Docker image exists: $DOCKER_IMAGE"
    echo "Pulling latest updates..."
    docker pull "$DOCKER_IMAGE" >/dev/null 2>&1
    log_success "Updated to latest image"
  else
    echo "Pulling official Arch Linux image..."
    docker pull "$DOCKER_IMAGE"
    log_success "Pulled Docker image: $DOCKER_IMAGE"
  fi
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Prepare Docker image")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 1: Prepare Docker image" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 2: Start container with dotfiles mounted
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 2/7: Starting Docker Container"
  echo "Starting container with dotfiles mounted..."

  # Start container in background with dotfiles mounted
  # Run as root (standard for Arch) but will create non-root user for realistic testing
  docker run -d \
    --name "$CONTAINER_NAME" \
    --env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    --env HOME=/root \
    --env DOTFILES_DOCKER_TEST=true \
    --mount type=bind,source="$DOTFILES_DIR",target=/dotfiles,readonly \
    "$DOCKER_IMAGE" \
    /usr/bin/sleep infinity

  log_success "Container started: $CONTAINER_NAME"
  echo "Dotfiles mounted at: /dotfiles (read-only)"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Start container")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 2: Start container" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 3: Prepare container environment
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 3/7: Preparing Container Environment"

  # Update package database and install sudo (required for fresh Arch containers)
  echo "Updating package database and installing sudo..."
  docker exec "$CONTAINER_NAME" pacman -Sy --noconfirm sudo

  # Create non-root user for realistic Arch testing
  echo "Creating test user 'archuser' for realistic testing..."
  docker exec "$CONTAINER_NAME" bash -c "
    useradd -m -G wheel -s /bin/bash archuser
    echo 'archuser ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers
  "

  # Set container home directory for archuser
  CONTAINER_HOME="/home/archuser"

  # Create ~/.env for testing
  echo "Creating ~/.env..."
  docker exec --user archuser --env HOME=${CONTAINER_HOME} "$CONTAINER_NAME" bash -c "cat > ${CONTAINER_HOME}/.env <<EOF
PLATFORM=arch
NVIM_AI_ENABLED=false
DOTFILES_DOCKER_TEST=true
EOF"

  # Copy dotfiles to writable location (install script modifies files)
  echo "Copying dotfiles to writable location..."
  docker exec --user archuser --env HOME=${CONTAINER_HOME} "$CONTAINER_NAME" bash -c "
    shopt -s dotglob
    for item in /dotfiles/*; do
      [[ \$(basename \"\$item\") == '.git' ]] && continue
      cp -rp \"\$item\" ${CONTAINER_HOME}/dotfiles/
    done
    chmod +x ${CONTAINER_HOME}/dotfiles/install.sh
  "

  log_success "Container environment ready"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Prepare environment")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 3: Prepare environment" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 4: Run installation script
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 4/7: Running install.sh Script"
  echo "Executing Arch Linux installation in container..."
  echo ""

  docker exec --user archuser --env HOME=/home/archuser "$CONTAINER_NAME" bash "/home/archuser/dotfiles/install.sh"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Installation")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 4: Installation" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 5: Verify installation
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 5/7: Verifying Installation"
  echo "Running comprehensive verification in fresh shell..."
  echo "(This tests that all tools are properly configured and in PATH)"
  echo ""

  # Run verification script (continue even if verification fails)
  docker exec --user archuser --env HOME=/home/archuser "$CONTAINER_NAME" bash -c "
    ZSHDOTDIR=/home/archuser/.config/zsh
    export ZSHDOTDIR
    zsh -c \"source \\\$ZSHDOTDIR/.zshrc 2>/dev/null; bash --norc /home/archuser/dotfiles/management/lib/verify-installed-packages.sh\"
  " || echo "  Note: Verification had failures, continuing with remaining tests..."
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Verification")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 5: Verification" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 6: Detect alternate installations
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 6/7: Detecting Alternate Installations"
  echo "Running detect-installed-duplicates.sh to check for duplicates..."
  echo ""

  docker exec --user archuser --env HOME=/home/archuser "$CONTAINER_NAME" bash "/home/archuser/dotfiles/management/lib/detect-installed-duplicates.sh"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Detect alternates")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 6: Detect alternates" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 7: Test update-all
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 7/7: Testing update-all Task"
  echo "Running task arch:update-all to verify update functionality..."
  echo ""

  docker exec --user archuser --env HOME=/home/archuser "$CONTAINER_NAME" bash -c "
    cd /home/archuser/dotfiles
    ZSHDOTDIR=/home/archuser/.config/zsh
    export ZSHDOTDIR
    zsh -c \"source \\\$ZSHDOTDIR/.zshrc 2>/dev/null; task arch:update-all\"
  "
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Update-all test")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 7: Update-all test" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# Calculate overall time
OVERALL_END=$(date +%s)
OVERALL_ELAPSED=$((OVERALL_END - OVERALL_START))

# Summary
{
  echo ""
  print_header_success "Arch Linux Installation Test Complete"
  echo ""
  print_timing_summary "$OVERALL_ELAPSED"
  print_section "Test Information" "cyan"
  echo ""
  echo "  Docker image: ${DOCKER_IMAGE}"
  echo "  Container: ${CONTAINER_NAME}"
  echo "  Log file: ${LOG_FILE}"
  echo ""

  if [[ "$KEEP_CONTAINER" == false ]]; then
    print_section "Cleanup" "cyan"
    echo "  Container will be removed automatically"
  else
    print_section "Debug Information" "cyan"
    echo "  Container kept for debugging"
    echo "  • Shell into container: docker exec -it --user archuser $CONTAINER_NAME bash"
    echo "  • View logs: docker logs $CONTAINER_NAME"
    echo "  • Remove when done: docker rm -f $CONTAINER_NAME"
  fi
  echo ""
} 2>&1 | tee -a "$LOG_FILE"
