#!/usr/bin/env bash
# ================================================================
# macOS Installation Testing Script (User Account-based)
# ================================================================
# Tests macOS installation using temporary user accounts
# This provides realistic macOS environment for testing
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
  echo "Test macOS installation script using temporary user account"
  echo ""
  echo "Options:"
  echo "  -k, --keep            Keep test user after test (for debugging)"
  echo "  -h, --help            Show this help message"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")              # Test with temporary user"
  echo "  $(basename "$0") -k           # Keep test user for debugging"
  echo ""
  echo "Note: This script requires sudo permissions to create/delete users"
  exit 0
fi

# Parse arguments
KEEP_USER=false
while [[ $# -gt 0 ]]; do
  case $1 in
    -k|--keep)
      KEEP_USER=true
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
TEST_USER="dotfiles-test-$(date '+%Y%m%d-%H%M%S')"
TEST_UID=599  # Use UID 599 (below 500, typically hidden from login screen)
LOG_FILE="${DOTFILES_DIR}/test-macos-user.log"

# Timing arrays
declare -a STEP_NAMES
declare -a STEP_TIMES

# Cleanup function
cleanup() {
  if [[ "$KEEP_USER" == false ]]; then
    if dscl . -list /Users | grep -q "^${TEST_USER}$"; then
      echo ""
      log_info "Cleaning up test user: $TEST_USER"
      sudo dscl . -delete "/Users/${TEST_USER}" 2>/dev/null || true
      sudo rm -rf "/Users/${TEST_USER}" 2>/dev/null || true
      log_success "Test user removed"
    fi
  else
    echo ""
    log_info "Test user kept for debugging: $TEST_USER"
    echo "  • Switch user: Command+Shift+Q, then select $TEST_USER"
    echo "  • Delete user: sudo dscl . -delete /Users/$TEST_USER && sudo rm -rf /Users/$TEST_USER"
  fi
}

# Register cleanup on exit
trap cleanup EXIT

# Overwrite log file (not append)
: > "$LOG_FILE"

log_info "Testing macOS installation with temporary user account"
log_info "Test user: ${TEST_USER}"
log_info "Log file: ${LOG_FILE}"
echo ""

# Check for sudo access early
if ! sudo -v; then
  die "This script requires sudo permissions to create test user"
fi

# Track overall start time
OVERALL_START=$(date +%s)

# ================================================================
# STEP 1: Create test user account
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 1/6: Creating Test User Account"

  echo "Creating test user: $TEST_USER (UID: $TEST_UID)..."

  # Create user
  sudo dscl . -create "/Users/${TEST_USER}"
  sudo dscl . -create "/Users/${TEST_USER}" UserShell /bin/zsh
  sudo dscl . -create "/Users/${TEST_USER}" RealName "Dotfiles Test User"
  sudo dscl . -create "/Users/${TEST_USER}" UniqueID "$TEST_UID"
  sudo dscl . -create "/Users/${TEST_USER}" PrimaryGroupID 20
  sudo dscl . -create "/Users/${TEST_USER}" NFSHomeDirectory "/Users/${TEST_USER}"

  # Create home directory
  sudo createhomedir -c -u "$TEST_USER" 2>/dev/null || {
    sudo mkdir -p "/Users/${TEST_USER}"
    sudo chown "${TEST_UID}:20" "/Users/${TEST_USER}"
  }

  # Set password (for potential debugging, but not needed for su)
  sudo dscl . -passwd "/Users/${TEST_USER}" "test1234"

  # Add to admin group (for sudo access during testing)
  sudo dscl . -append /Groups/admin GroupMembership "$TEST_USER"

  log_success "Created test user: $TEST_USER"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Create test user")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 1: Create test user" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 2: Clone dotfiles to test user's home
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 2/6: Preparing Test Environment"

  echo "Copying dotfiles to test user's home directory..."
  sudo -u "$TEST_USER" cp -r "$DOTFILES_DIR" "/Users/${TEST_USER}/dotfiles"

  echo "Creating ~/.env..."
  sudo -u "$TEST_USER" bash -c "cat > /Users/${TEST_USER}/.env <<EOF
PLATFORM=macos
NVIM_AI_ENABLED=false
EOF"

  log_success "Test environment ready"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Prepare environment")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 2: Prepare environment" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 3: Run installation script as test user
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 3/6: Running install.sh Script"
  echo "Executing macOS installation as test user..."
  echo ""

  sudo -u "$TEST_USER" bash "/Users/${TEST_USER}/dotfiles/install.sh"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Installation")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 3: Installation" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 4: Verify installation
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 4/6: Verifying Installation"
  echo "Running comprehensive verification in fresh shell..."
  echo "(This tests that all tools are properly configured and in PATH)"
  echo ""

  # Run verification script as test user in fresh zsh shell (continue even if verification fails)
  sudo -u "$TEST_USER" bash -c "
    export ZSHDOTDIR=/Users/$TEST_USER/.config/zsh
    zsh -c \"source \$ZSHDOTDIR/.zshrc 2>/dev/null; bash --norc /Users/$TEST_USER/dotfiles/management/lib/verify-installed-packages.sh\"
  " || echo "  Note: Verification had failures, continuing with remaining tests..."
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Verification")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 4: Verification" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 5: Detect alternate installations
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 5/6: Detecting Alternate Installations"
  echo "Running detect-installed-duplicates.sh to check for duplicates..."
  echo ""

  sudo -u "$TEST_USER" bash "/Users/${TEST_USER}/dotfiles/management/lib/detect-installed-duplicates.sh"
} 2>&1 | tee -a "$LOG_FILE"
STEP_END=$(date +%s)
STEP_ELAPSED=$((STEP_END - STEP_START))
STEP_NAMES+=("Detect alternates")
STEP_TIMES+=("$STEP_ELAPSED")
{
  log_timing "Step 5: Detect alternates" "$STEP_ELAPSED"
} 2>&1 | tee -a "$LOG_FILE"

# ================================================================
# STEP 6: Test update-all
# ================================================================
STEP_START=$(date +%s)
{
  log_section "STEP 6/6: Testing update-all Task"
  echo "Running task macos:update-all to verify update functionality..."
  echo ""

  sudo -u "$TEST_USER" bash -c "
    cd /Users/$TEST_USER/dotfiles
    export ZSHDOTDIR=/Users/$TEST_USER/.config/zsh
    zsh -c \"source \$ZSHDOTDIR/.zshrc 2>/dev/null; task macos:update-all\"
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
  print_header_success "macOS Installation Test Complete"
  echo ""
  print_timing_summary "$OVERALL_ELAPSED"
  print_section "Test Information" "cyan"
  echo ""
  echo "  Test user: ${TEST_USER}"
  echo "  Home directory: /Users/${TEST_USER}"
  echo "  Log file: ${LOG_FILE}"
  echo ""

  if [[ "$KEEP_USER" == false ]]; then
    print_section "Cleanup" "cyan"
    echo "  Test user will be removed automatically"
  else
    print_section "Debug Information" "cyan"
    echo "  Test user kept for debugging"
    echo "  • Switch user: Lock screen (Cmd+Ctrl+Q), then select $TEST_USER"
    echo "  • Password: test1234"
    echo "  • Delete user: sudo dscl . -delete /Users/$TEST_USER && sudo rm -rf /Users/$TEST_USER"
  fi
  echo ""
} 2>&1 | tee -a "$LOG_FILE"
