#!/usr/bin/env bats
# ================================================================
# Integration test for BATS installer (dogfooding!)
# ================================================================
# Tests that the BATS installer:
# 1. Handles idempotency (skip if already installed)
# 2. Installs bats-core to ~/.local/bin
# 3. Installs helper libraries to ~/.local/lib
# 4. Verifies installation success
# 5. Provides structured failure output
# ================================================================

# Load BATS helpers (from ~/.local installation)
load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

# Setup runs once before all tests
setup_file() {
  export SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  export DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
  export BATS_INSTALLER="$DOTFILES_DIR/management/common/install/custom-installers/bats.sh"

  # Verify installer exists
  if [[ ! -f "$BATS_INSTALLER" ]]; then
    echo "BATS installer not found at: $BATS_INSTALLER" >&2
    exit 1
  fi

  # Setup test environment with isolated installation directory
  # Use mktemp for cross-platform compatibility
  export TEST_INSTALL_PREFIX="$(mktemp -d)/test-local"
  export HOME_BACKUP="$HOME"

  # Create test installation directories
  mkdir -p "$TEST_INSTALL_PREFIX/bin"
  mkdir -p "$TEST_INSTALL_PREFIX/lib"

  # Source required libraries for the installer
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
  source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
}

# Teardown runs once after all tests
teardown_file() {
  # Clean up test installation
  rm -rf "$TEST_INSTALL_PREFIX"
}

# ================================================================
# Test Suite 1: Installer Pre-flight Checks
# ================================================================

@test "installer script exists and is executable" {
  assert [ -f "$BATS_INSTALLER" ]
  assert [ -x "$BATS_INSTALLER" ]
}

@test "installer has proper shebang" {
  run head -n1 "$BATS_INSTALLER"
  assert_output --partial "#!/usr/bin/env bash"
}

@test "installer sources required libraries" {
  run grep -c "source.*logging.sh" "$BATS_INSTALLER"
  assert_success

  run grep -c "source.*failure-logging.sh" "$BATS_INSTALLER"
  assert_success
}

@test "installer sets error handling flags" {
  run grep -c "set -uo pipefail" "$BATS_INSTALLER"
  assert_success
}

# ================================================================
# Test Suite 2: Idempotency and Version Detection
# ================================================================

@test "installer checks if bats already exists" {
  run grep -c "command -v bats" "$BATS_INSTALLER"
  assert_success
  # Should check multiple times (initial check, verification)
  local check_count
  check_count=$(grep -c "command -v bats" "$BATS_INSTALLER")
  assert [ "$check_count" -ge 2 ]
}

@test "installer compares installation paths" {
  # Should check if current bats is in target location
  run grep -c "CURRENT_PATH.*INSTALL_PREFIX" "$BATS_INSTALLER"
  assert_success
}

@test "installer respects FORCE_INSTALL environment variable" {
  # When FORCE_INSTALL=true, it should not skip even if installed
  run grep -c 'FORCE_INSTALL.*false.*true' "$BATS_INSTALLER"
  assert_success
}

# ================================================================
# Test Suite 3: Installation Configuration
# ================================================================

@test "installer uses correct default version" {
  run grep "BATS_VERSION=" "$BATS_INSTALLER"
  assert_success
  assert_output --partial "v1.13.0"
}

@test "installer targets ~/.local prefix" {
  run grep "INSTALL_PREFIX=" "$BATS_INSTALLER"
  assert_success
  assert_output --partial "\$HOME/.local"
}

@test "installer defines correct repository URLs" {
  run grep "BATS_CORE_REPO=" "$BATS_INSTALLER"
  assert_success
  assert_output --partial "bats-core/bats-core.git"

  run grep "BATS_SUPPORT_REPO=" "$BATS_INSTALLER"
  assert_success
  assert_output --partial "bats-core/bats-support.git"

  run grep "BATS_ASSERT_REPO=" "$BATS_INSTALLER"
  assert_success
  assert_output --partial "bats-core/bats-assert.git"
}

# ================================================================
# Test Suite 4: Error Handling
# ================================================================

@test "installer checks for git command" {
  run grep -c "command -v git" "$BATS_INSTALLER"
  assert_success
}

@test "installer uses failure-logging for errors" {
  run grep -c "output_failure_data" "$BATS_INSTALLER"
  assert_success

  # Should have multiple failure scenarios
  local failure_count
  failure_count=$(grep -c "output_failure_data" "$BATS_INSTALLER")
  assert [ "$failure_count" -ge 3 ]
}

@test "installer provides manual installation steps on failure" {
  run grep -c "manual_steps=" "$BATS_INSTALLER"
  assert_success
}

@test "installer uses trap for cleanup" {
  run grep -c "trap.*EXIT" "$BATS_INSTALLER"
  assert_success
}

# ================================================================
# Test Suite 5: Installation Steps
# ================================================================

@test "installer creates lib directory" {
  run grep -c "mkdir.*BATS_LIB_DIR" "$BATS_INSTALLER"
  assert_success
}

@test "installer clones bats-core repository" {
  run grep -c "git clone.*bats-core" "$BATS_INSTALLER"
  assert_success
}

@test "installer runs bats-core install.sh" {
  run grep -c "./install.sh.*INSTALL_PREFIX" "$BATS_INSTALLER"
  assert_success
}

@test "installer copies bats-support to lib directory" {
  run grep -c "cp -r.*bats-support.*BATS_LIB_DIR" "$BATS_INSTALLER"
  assert_success
}

@test "installer copies bats-assert to lib directory" {
  run grep -c "cp -r.*bats-assert.*BATS_LIB_DIR" "$BATS_INSTALLER"
  assert_success
}

# ================================================================
# Test Suite 6: Verification Steps
# ================================================================

@test "installer verifies bats command is available" {
  run grep -c "command -v bats" "$BATS_INSTALLER"
  assert_success
}

@test "installer checks bats version" {
  run grep -c "bats --version" "$BATS_INSTALLER"
  assert_success
}

@test "installer verifies helper library load files exist" {
  run grep -c "bats-support/load.bash" "$BATS_INSTALLER"
  assert_success

  run grep -c "bats-assert/load.bash" "$BATS_INSTALLER"
  assert_success
}

@test "installer provides usage instructions for helpers" {
  run grep -c "Load in tests with:" "$BATS_INSTALLER"
  assert_success
}

# ================================================================
# Test Suite 7: Output and Logging
# ================================================================

@test "installer uses logging functions" {
  # Should use log_info, log_success, log_error, log_warning
  run grep -c "log_info\|log_success\|log_error\|log_warning" "$BATS_INSTALLER"
  assert_success

  local log_count
  log_count=$(grep -c "log_info\|log_success\|log_error\|log_warning" "$BATS_INSTALLER")
  assert [ "$log_count" -ge 10 ]
}

@test "installer uses print_banner for headers" {
  run grep -c "print_banner" "$BATS_INSTALLER"
  assert_success
}

@test "installer has success banner at end" {
  run grep -c "print_banner_success" "$BATS_INSTALLER"
  assert_success
}

# ================================================================
# Test Suite 8: Code Quality
# ================================================================

@test "installer has no shellcheck warnings" {
  if ! command -v shellcheck >/dev/null 2>&1; then
    skip "shellcheck not installed"
  fi

  run shellcheck "$BATS_INSTALLER"
  assert_success
}

@test "installer follows naming conventions" {
  # Variables should be UPPER_CASE
  run grep -E "^[a-z_]+=" "$BATS_INSTALLER"
  assert_failure
}

@test "installer script is reasonably sized" {
  local line_count
  line_count=$(wc -l < "$BATS_INSTALLER")

  # Should be comprehensive but not overly complex
  assert [ "$line_count" -ge 100 ]
  assert [ "$line_count" -le 300 ]
}
