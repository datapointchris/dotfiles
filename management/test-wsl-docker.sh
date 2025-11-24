#!/usr/bin/env bash
# ================================================================
# WSL Installation Testing Script (Docker-based)
# ================================================================
# Tests WSL installation using Docker with official WSL rootfs
# This provides 100% accurate WSL environment on macOS/Linux
# ================================================================

set -euo pipefail

# Source formatting library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$DOTFILES_DIR/platforms/common/shell/formatting.sh"

# Show usage
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Test WSL installation script using Docker with official WSL Ubuntu rootfs"
  echo ""
  echo "Options:"
  echo "  -v, --version VERSION  Ubuntu version to test (22.04 or 24.04, default: 24.04)"
  echo "  -k, --keep            Keep container after test (for debugging)"
  echo "  -h, --help            Show this help message"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")              # Test with Ubuntu 24.04 (default)"
  echo "  $(basename "$0") -v 22.04     # Test with Ubuntu 22.04"
  echo "  $(basename "$0") -k           # Keep container for debugging"
  exit 0
fi

# Parse arguments
UBUNTU_VERSION="24.04"  # Default to 24.04 (current WSL version)
KEEP_CONTAINER=false
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
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
  esac
done

# Configuration
WSL_CACHE_DIR="${DOTFILES_DIR}/.wsl-rootfs-cache"
LOG_FILE="${DOTFILES_DIR}/test-wsl-docker.log"
CONTAINER_NAME="dotfiles-wsl-test-$(date '+%Y%m%d-%H%M%S')"

# Determine Ubuntu codename and file format
case "$UBUNTU_VERSION" in
  22.04)
    UBUNTU_CODENAME="jammy"
    ROOTFS_URL="https://cloud-images.ubuntu.com/wsl/${UBUNTU_CODENAME}/current/ubuntu-${UBUNTU_CODENAME}-wsl-amd64-ubuntu${UBUNTU_VERSION}lts.rootfs.tar.gz"
    ROOTFS_FILE="${WSL_CACHE_DIR}/ubuntu-${UBUNTU_CODENAME}-wsl-amd64-ubuntu${UBUNTU_VERSION}lts.rootfs.tar.gz"
    ;;
  24.04)
    UBUNTU_CODENAME="noble"
    # Ubuntu 24.04 uses .wsl format (which is actually a tar file)
    ROOTFS_URL="https://releases.ubuntu.com/${UBUNTU_CODENAME}/ubuntu-${UBUNTU_VERSION}.3-wsl-amd64.wsl"
    ROOTFS_FILE="${WSL_CACHE_DIR}/ubuntu-${UBUNTU_VERSION}.3-wsl-amd64.wsl"
    ;;
  *)
    die "Unsupported Ubuntu version: $UBUNTU_VERSION (use 22.04 or 24.04)"
    ;;
esac

DOCKER_IMAGE="wsl-ubuntu:${UBUNTU_VERSION}"

# Timing arrays
declare -a STEP_NAMES
declare -a STEP_TIMES

# Function to format seconds as MM:SS
format_time() {
  local total_seconds=$1
  local minutes=$((total_seconds / 60))
  local seconds=$((total_seconds % 60))
  printf "%02d:%02d" $minutes $seconds
}

# Function to log with timestamps
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Function to log section headers with timestamp
log_section() {
  echo ""
  print_header "[$(date '+%Y-%m-%d %H:%M:%S')] $*" "blue"
}

# Function to log timing after each step
log_timing() {
  local step_name=$1
  local elapsed=$2
  local formatted_time
  formatted_time=$(format_time "$elapsed")
  echo ""
  print_info "⏱  $step_name completed in $formatted_time"
  echo ""
}

# Cleanup function
cleanup() {
  if [[ "$KEEP_CONTAINER" == false ]]; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
      echo ""
      print_info "Cleaning up container: $CONTAINER_NAME"
      docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
  else
    echo ""
    print_info "Container kept for debugging: $CONTAINER_NAME"
    echo "  • Shell into container: docker exec -it $CONTAINER_NAME bash"
    echo "  • View logs: docker logs $CONTAINER_NAME"
    echo "  • Remove container: docker rm -f $CONTAINER_NAME"
  fi
}

# Register cleanup on exit
trap cleanup EXIT

# Overwrite log file (not append)
: > "$LOG_FILE"

print_info "Testing WSL installation with Docker"
print_info "Ubuntu version: ${UBUNTU_VERSION} (${UBUNTU_CODENAME})"
print_info "Docker image: ${DOCKER_IMAGE}"
print_info "Container: ${CONTAINER_NAME}"
print_info "Log file: ${LOG_FILE}"
echo ""

# Track overall start time
OVERALL_START=$(date +%s)

# ================================================================
# STEP 1: Ensure WSL rootfs is available and Docker image exists
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
    print_success "Docker image already exists: $DOCKER_IMAGE"
  else
    echo "Docker image not found, will create from WSL rootfs..."
    echo ""

    # Create cache directory
    mkdir -p "$WSL_CACHE_DIR"

    # Download rootfs if not cached
    if [[ -f "$ROOTFS_FILE" ]]; then
      print_success "Using cached WSL rootfs: $ROOTFS_FILE"
    else
      echo "Downloading WSL Ubuntu ${UBUNTU_VERSION} rootfs..."
      echo "URL: $ROOTFS_URL"
      echo "This is a one-time download (~340MB)..."
      echo ""
      curl -L --progress-bar "$ROOTFS_URL" -o "$ROOTFS_FILE"
      print_success "Downloaded WSL rootfs to cache"
    fi

    # Import rootfs into Docker
    echo ""
    echo "Importing WSL rootfs into Docker..."
    if [[ "$ROOTFS_FILE" == *.wsl ]]; then
      # .wsl files are already tar format, no need to gunzip
      docker import - "$DOCKER_IMAGE" < "$ROOTFS_FILE"
    else
      # .tar.gz files need gunzip
      gunzip -c "$ROOTFS_FILE" | docker import - "$DOCKER_IMAGE"
    fi
    print_success "Created Docker image: $DOCKER_IMAGE"

    # Create non-root user for realistic WSL testing
    echo ""
    echo "Creating non-root user in Docker image..."
    docker run --rm "$DOCKER_IMAGE" /bin/bash -c "useradd -m -s /bin/bash -G sudo ubuntu && echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers" 2>/dev/null || {
      echo "Note: Image already has ubuntu user or user creation not needed"
    }
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
  log_section "STEP 2/6: Starting Docker Container"
  echo "Starting container with dotfiles mounted..."

  # Start container in background with dotfiles mounted
  # The imported WSL rootfs needs full paths and proper environment
  # Try to run as ubuntu user (realistic WSL), fall back to root if needed
  if docker run --rm "$DOCKER_IMAGE" id ubuntu &>/dev/null; then
    USER_FLAG="--user ubuntu"
    HOME_DIR="/home/ubuntu"
  else
    echo "Warning: Running as root (ubuntu user not found in image)"
    USER_FLAG=""
    HOME_DIR="/root"
  fi

  # shellcheck disable=SC2086  # USER_FLAG intentionally unquoted (empty or --user ubuntu)
  docker run -d \
    --name "$CONTAINER_NAME" \
    $USER_FLAG \
    --env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    --env HOME="$HOME_DIR" \
    --env DOTFILES_DOCKER_TEST=true \
    --mount type=bind,source="$DOTFILES_DIR",target=/dotfiles,readonly \
    "$DOCKER_IMAGE" \
    /usr/bin/sleep infinity

  print_success "Container started: $CONTAINER_NAME"
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
  log_section "STEP 3/6: Preparing Container Environment"

  # Detect home directory
  CONTAINER_HOME=$(docker exec "$CONTAINER_NAME" bash -c 'echo $HOME')

  # Create ~/.env for testing
  echo "Creating ~/.env..."
  docker exec "$CONTAINER_NAME" bash -c 'cat > ~/.env <<EOF
PLATFORM=wsl
NVIM_AI_ENABLED=false
EOF'

  # Copy dotfiles to writable location (install script modifies files)
  echo "Copying dotfiles to writable location..."
  docker exec "$CONTAINER_NAME" bash -c "cp -r /dotfiles ${CONTAINER_HOME}/dotfiles"

  print_success "Container environment ready"
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
  log_section "STEP 4/6: Running install.sh Script"
  echo "Executing WSL installation in container..."
  echo ""

  CONTAINER_HOME=$(docker exec "$CONTAINER_NAME" bash -c 'echo $HOME')
  docker exec "$CONTAINER_NAME" bash "${CONTAINER_HOME}/dotfiles/install.sh"
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
  log_section "STEP 5/6: Verifying Installation"
  echo "Running comprehensive verification in fresh shell..."
  echo "(This tests that all tools are properly configured and in PATH)"
  echo ""

  # Run verification script
  CONTAINER_HOME=$(docker exec "$CONTAINER_NAME" bash -c 'echo $HOME')
  docker exec "$CONTAINER_NAME" bash -c "
    ZSHDOTDIR=${CONTAINER_HOME}/.config/zsh
    export ZSHDOTDIR
    zsh -c \"source \\\$ZSHDOTDIR/.zshrc 2>/dev/null; bash --norc ${CONTAINER_HOME}/dotfiles/management/verify-installation.sh\"
  "
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Verification")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 5: Verification" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 6: Test update-all
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 6/6: Testing update-all Task"
  echo "Running task wsl:update-all to verify update functionality..."
  echo ""

  CONTAINER_HOME=$(docker exec "$CONTAINER_NAME" bash -c 'echo $HOME')
  docker exec "$CONTAINER_NAME" bash -c "
    cd ${CONTAINER_HOME}/dotfiles
    ZSHDOTDIR=${CONTAINER_HOME}/.config/zsh
    export ZSHDOTDIR
    zsh -c \"source \\\$ZSHDOTDIR/.zshrc 2>/dev/null; task wsl:update-all\"
  "
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Update-all test")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 6: Update-all test" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# Calculate overall time
OVERALL_END=$(date +%s)
OVERALL_ELAPSED=$((OVERALL_END - OVERALL_START))

# Summary
{
  echo ""
  print_header_success "WSL Installation Test Complete"
  echo ""
  print_section "Timing Summary" "cyan"
  echo ""
  for i in "${!STEP_NAMES[@]}"; do
    formatted_time=$(format_time "${STEP_TIMES[$i]}")
    printf "  %s Step %d: %-20s %s\n" "$(print_green "✓")" $((i + 1)) "${STEP_NAMES[$i]}" "$formatted_time"
  done
  echo "  ─────────────────────────────────────────────"
  formatted_total=$(format_time "$OVERALL_ELAPSED")
  printf "  %-27s %s\n" "Total time:" "$(print_cyan "$formatted_total")"
  echo ""
  print_section "Test Information" "cyan"
  echo ""
  echo "  Ubuntu version: ${UBUNTU_VERSION} (${UBUNTU_CODENAME})"
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
    echo "  • Shell into container: docker exec -it $CONTAINER_NAME bash"
    echo "  • View logs: docker logs $CONTAINER_NAME"
    echo "  • Remove when done: docker rm -f $CONTAINER_NAME"
  fi
  echo ""
} 2>&1 | tee -a "$LOG_FILE"
