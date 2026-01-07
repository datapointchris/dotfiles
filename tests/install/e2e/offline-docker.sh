#!/usr/bin/env bash
# ================================================================
# Offline Bundle Installation Test (Docker-based)
# ================================================================
# End-to-end test for offline installation:
# 1. Creates offline bundle (on host with full network)
# 2. Starts Docker container with blocked GitHub downloads
# 3. Extracts bundle and runs install.sh --offline
# 4. Verifies tools are installed from cache
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$DOTFILES_DIR/tests/install/helpers.sh"

# Configuration
DOCKER_IMAGE="dotfiles-test-base:ubuntu-24.04"
CONTAINER_NAME="dotfiles-offline-test-$(date '+%Y%m%d-%H%M%S')"
BUNDLE_DIR="$DOTFILES_DIR/management/offline"
LOG_FILE="$DOTFILES_DIR/test-offline-docker.log"

# Options
KEEP_CONTAINER=false
SKIP_BUNDLE=false
REUSE_BUNDLE=false

usage() {
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Test offline bundle installation using Docker with blocked network"
  echo ""
  echo "Options:"
  echo "  -k, --keep          Keep container after test (for debugging)"
  echo "  -s, --skip-bundle   Skip bundle creation, use existing bundle"
  echo "  -r, --reuse-bundle  Reuse existing bundle if available, create if not"
  echo "  -h, --help          Show this help message"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")              # Full test: create bundle + test install"
  echo "  $(basename "$0") -s           # Test with existing bundle (faster)"
  echo "  $(basename "$0") -k           # Keep container for debugging"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -k|--keep)         KEEP_CONTAINER=true; shift ;;
    -s|--skip-bundle)  SKIP_BUNDLE=true; shift ;;
    -r|--reuse-bundle) REUSE_BUNDLE=true; shift ;;
    -h|--help)         usage; exit 0 ;;
    *)                 echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# Cleanup on exit
cleanup() {
  local exit_code=$?
  if [[ "$KEEP_CONTAINER" == false ]]; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
      log_info "Cleaning up container: $CONTAINER_NAME"
      docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi
  else
    if [[ $exit_code -ne 0 ]]; then
      echo ""
      log_info "Container kept for debugging: $CONTAINER_NAME"
      echo "  Shell: docker exec -it $CONTAINER_NAME bash"
      echo "  Logs:  docker logs $CONTAINER_NAME"
      echo "  Remove: docker rm -f $CONTAINER_NAME"
    fi
  fi
}
trap cleanup EXIT

# Timing
declare -a STEP_NAMES
declare -a STEP_TIMES
OVERALL_START=$(date +%s)

# Initialize log
: > "$LOG_FILE"

log_info "Offline Bundle Installation Test"
log_info "Docker image: $DOCKER_IMAGE"
log_info "Container: $CONTAINER_NAME"
log_info "Log file: $LOG_FILE"
echo ""

# ================================================================
# Step 1: Check prerequisites
# ================================================================
STEP_START=$(date +%s)
{
  log_section "Step 1: Checking Prerequisites"

  check_docker

  if ! docker_image_exists "$DOCKER_IMAGE"; then
    die "Docker base image not found: $DOCKER_IMAGE
Build it with: cd tests/install/docker && ./build-base.sh"
  fi
  log_success "Docker image exists: $DOCKER_IMAGE"

} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_NAMES+=("Prerequisites")
STEP_TIMES+=($((STEP_END - STEP_START)))

# ================================================================
# Step 2: Create or find offline bundle
# ================================================================
STEP_START=$(date +%s)
log_section "Step 2: Preparing Offline Bundle" 2>&1 | tee -a "$LOG_FILE"

BUNDLE_FILE=""

if [[ "$SKIP_BUNDLE" == true ]]; then
  log_info "Skipping bundle creation (--skip-bundle)" 2>&1 | tee -a "$LOG_FILE"
  BUNDLE_FILE=$(find "$BUNDLE_DIR" -maxdepth 1 -name "dotfiles-offline-*-linux-x86_64.tar.gz" -type f -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1 || true)
  if [[ -z "$BUNDLE_FILE" || ! -f "$BUNDLE_FILE" ]]; then
    die "No existing bundle found. Run without --skip-bundle first."
  fi

elif [[ "$REUSE_BUNDLE" == true ]]; then
  BUNDLE_FILE=$(find "$BUNDLE_DIR" -maxdepth 1 -name "dotfiles-offline-*-linux-x86_64.tar.gz" -type f -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1 || true)
  if [[ -n "$BUNDLE_FILE" && -f "$BUNDLE_FILE" ]]; then
    log_info "Reusing existing bundle: $(basename "$BUNDLE_FILE")" 2>&1 | tee -a "$LOG_FILE"
  else
    log_info "No existing bundle, creating new one..." 2>&1 | tee -a "$LOG_FILE"
    bash "$BUNDLE_DIR/create-bundle.sh" --platform linux-x86_64 2>&1 | tee -a "$LOG_FILE"
    BUNDLE_FILE=$(find "$BUNDLE_DIR" -maxdepth 1 -name "dotfiles-offline-*-linux-x86_64.tar.gz" -type f -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1)
  fi

else
  log_info "Creating fresh offline bundle..." 2>&1 | tee -a "$LOG_FILE"
  bash "$BUNDLE_DIR/create-bundle.sh" --platform linux-x86_64 2>&1 | tee -a "$LOG_FILE"
  BUNDLE_FILE=$(find "$BUNDLE_DIR" -maxdepth 1 -name "dotfiles-offline-*-linux-x86_64.tar.gz" -type f -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1)
fi

if [[ -z "$BUNDLE_FILE" || ! -f "$BUNDLE_FILE" ]]; then
  die "Bundle file not found after creation"
fi

BUNDLE_SIZE=$(du -h "$BUNDLE_FILE" | cut -f1)
log_success "Using bundle: $(basename "$BUNDLE_FILE") ($BUNDLE_SIZE)" 2>&1 | tee -a "$LOG_FILE"

STEP_END=$(date +%s)
STEP_NAMES+=("Bundle preparation")
STEP_TIMES+=($((STEP_END - STEP_START)))

# ================================================================
# Step 3: Start container with blocked network
# ================================================================
STEP_START=$(date +%s)
{
  log_section "Step 3: Starting Container (GitHub Downloads Blocked)"

  # Block GitHub download domains via /etc/hosts
  # This simulates a corporate firewall that blocks GitHub file downloads
  # but allows other network access (npm, PyPI, Go proxy)
  docker run -d \
    --name "$CONTAINER_NAME" \
    --user testuser \
    --add-host "objects.githubusercontent.com:127.0.0.1" \
    --add-host "github-releases.githubusercontent.com:127.0.0.1" \
    --add-host "raw.githubusercontent.com:127.0.0.1" \
    --env DOTFILES_DOCKER_TEST=true \
    --env SKIP_FONTS=1 \
    --env PATH="/home/testuser/.local/bin:/home/testuser/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    "$DOCKER_IMAGE" \
    sleep infinity >/dev/null

  log_success "Container started with blocked GitHub downloads"
  log_info "Blocked hosts: objects.githubusercontent.com, github-releases.githubusercontent.com, raw.githubusercontent.com"

} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_NAMES+=("Start container")
STEP_TIMES+=($((STEP_END - STEP_START)))

# ================================================================
# Step 4: Copy bundle and dotfiles into container
# ================================================================
STEP_START=$(date +%s)
{
  log_section "Step 4: Copying Bundle and Dotfiles"

  log_info "Copying offline bundle..."
  docker cp "$BUNDLE_FILE" "$CONTAINER_NAME:/home/testuser/"

  log_info "Copying dotfiles repository..."
  docker cp "$DOTFILES_DIR/." "$CONTAINER_NAME:/home/testuser/dotfiles/"

  log_info "Fixing ownership..."
  docker exec --user root "$CONTAINER_NAME" \
    chown -R testuser:testuser /home/testuser

  log_info "Creating .env file..."
  docker exec "$CONTAINER_NAME" bash -c 'cat > ~/.env <<EOF
PLATFORM=wsl
NVIM_AI_ENABLED=false
EOF'

  log_success "Files copied to container"

} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_NAMES+=("Copy files")
STEP_TIMES+=($((STEP_END - STEP_START)))

# ================================================================
# Step 5: Extract bundle
# ================================================================
STEP_START=$(date +%s)
{
  log_section "Step 5: Extracting Offline Bundle"

  BUNDLE_BASENAME=$(basename "$BUNDLE_FILE")
  docker exec "$CONTAINER_NAME" bash -c "cd /home/testuser && tar -xzf '$BUNDLE_BASENAME'"

  log_info "Bundle contents:"
  docker exec "$CONTAINER_NAME" ls -la /home/testuser/installers/
  docker exec "$CONTAINER_NAME" bash -c "wc -l /home/testuser/installers/manifest.txt | awk '{print \"  Manifest entries: \" \$1}'"

  log_success "Bundle extracted to ~/installers/"

} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_NAMES+=("Extract bundle")
STEP_TIMES+=($((STEP_END - STEP_START)))

# ================================================================
# Step 6: Verify network is blocked
# ================================================================
STEP_START=$(date +%s)
{
  log_section "Step 6: Verifying Network Restrictions"

  log_info "Testing that GitHub downloads are blocked..."

  # This should fail (blocked)
  if docker exec "$CONTAINER_NAME" curl -fsSL --connect-timeout 5 \
    "https://objects.githubusercontent.com/test" 2>/dev/null; then
    log_warning "GitHub downloads NOT blocked - test may not be valid"
  else
    log_success "GitHub downloads are blocked (as expected)"
  fi

  # This should work (not blocked)
  if docker exec "$CONTAINER_NAME" curl -fsSL --connect-timeout 5 \
    "https://registry.npmjs.org/" >/dev/null 2>&1; then
    log_success "npm registry accessible (as expected)"
  else
    log_warning "npm registry not accessible"
  fi

} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_NAMES+=("Verify network")
STEP_TIMES+=($((STEP_END - STEP_START)))

# ================================================================
# Step 7: Run install.sh --offline
# ================================================================
STEP_START=$(date +%s)
{
  log_section "Step 7: Running install.sh --offline"
  log_info "This should use cached files from ~/installers/"
  echo ""

  docker exec "$CONTAINER_NAME" bash -c "cd ~/dotfiles && ./install.sh --offline"

} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_NAMES+=("Installation")
STEP_TIMES+=($((STEP_END - STEP_START)))

# ================================================================
# Step 8: Verify installation
# ================================================================
STEP_START=$(date +%s)
{
  log_section "Step 8: Verifying Installation"
  log_info "Checking that tools were installed from offline cache..."
  echo ""

  # Check key tools that come from the bundle
  # Include cargo bin in PATH for verification
  TOOLS_TO_CHECK=(
    "nvim:neovim"
    "lazygit:lazygit"
    "fzf:fzf"
    "bat:bat"
    "fd:fd"
    "eza:eza"
    "zoxide:zoxide"
    "delta:git-delta"
    "glow:glow"
    "duf:duf"
  )

  PASSED=0
  FAILED=0

  for tool_spec in "${TOOLS_TO_CHECK[@]}"; do
    cmd="${tool_spec%%:*}"
    name="${tool_spec##*:}"

    # Check in PATH including cargo bin directory
    if docker exec "$CONTAINER_NAME" bash -c "export PATH=\"/home/testuser/.cargo/bin:/home/testuser/.local/bin:\$PATH\"; command -v $cmd >/dev/null 2>&1"; then
      version=$(docker exec "$CONTAINER_NAME" bash -c "export PATH=\"/home/testuser/.cargo/bin:/home/testuser/.local/bin:\$PATH\"; $cmd --version 2>&1 | head -1" || echo "installed")
      log_success "$name: $version"
      PASSED=$((PASSED + 1))
    else
      log_error "$name: NOT FOUND"
      FAILED=$((FAILED + 1))
    fi
  done

  echo ""
  log_info "Results: $PASSED passed, $FAILED failed"

  if [[ $FAILED -gt 0 ]]; then
    log_error "Some tools failed to install from offline cache"
  else
    log_success "All tools installed successfully from offline cache!"
  fi

  # Save FAILED count to temp file to avoid subshell issue with tee
  echo "$FAILED" > "$TMP_DIR/failed_count"

} 2>&1 | tee -a "$LOG_FILE"

# Read FAILED count from temp file
FAILED=$(cat "$TMP_DIR/failed_count")
STEP_END=$(date +%s)
STEP_NAMES+=("Verification")
STEP_TIMES+=($((STEP_END - STEP_START)))

# ================================================================
# Summary
# ================================================================
OVERALL_END=$(date +%s)
OVERALL_ELAPSED=$((OVERALL_END - OVERALL_START))

{
  echo ""
  print_header_success "Offline Installation Test Complete"
  echo ""

  print_timing_summary "$OVERALL_ELAPSED"

  print_section "Test Information" "cyan"
  echo ""
  echo "  Docker image: $DOCKER_IMAGE"
  echo "  Container: $CONTAINER_NAME"
  echo "  Bundle: $(basename "$BUNDLE_FILE")"
  echo "  Log file: $LOG_FILE"
  echo ""

  if [[ "$KEEP_CONTAINER" == true ]]; then
    print_section "Debug Information" "cyan"
    echo "  Container kept for debugging"
    echo "  Shell: docker exec -it $CONTAINER_NAME bash"
    echo "  Remove: docker rm -f $CONTAINER_NAME"
    echo ""
  fi

} 2>&1 | tee -a "$LOG_FILE"

# Exit with failure if verification failed
if [[ ${FAILED:-0} -gt 0 ]]; then
  exit 1
fi
