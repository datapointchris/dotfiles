#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Integration test for installation orchestration
# ================================================================
# Tests end-to-end installation workflow:
# 1. Multiple installers (success + failure)
# 2. Failures accumulate in single log
# 3. show_failures_summary() displays correctly
# 4. Successful installers don't pollute failure log
#
# This complements pattern tests which focus on individual
# installer behavior. This tests the ORCHESTRATION layer.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."

  # Source libraries
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
  source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

  # Source REAL run_installer wrapper and export it
  source "$DOTFILES_DIR/management/orchestration/run-installer.sh"
  export -f run_installer

  # Define REAL show_failures_summary (from install.sh) and export it
  show_failures_summary() {
    if [[ ! -f "$FAILURES_LOG" ]] || [[ ! -s "$FAILURES_LOG" ]]; then
      return 0
    fi

    local failure_count
    # grep -c outputs "0" when no matches (doesn't fail), so no need for || echo "0"
    failure_count=$(grep -c "^---$" "$FAILURES_LOG" 2>/dev/null)

    if [[ "$failure_count" -eq 0 ]]; then
      return 0
    fi

    echo "Installation Summary"
    echo "$failure_count installation(s) failed"
    cat "$FAILURES_LOG"
    echo "Full report saved to: $FAILURES_LOG"
  }
  export -f show_failures_summary

  # Setup test environment
  export FAILURES_LOG="/tmp/test-orchestration-$$.log"
  export TEMP_DIR="/tmp/test-installers-$$"
  mkdir -p "$TEMP_DIR"

  # Create mock successful installer
  cat > "$TEMP_DIR/success.sh" << 'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$TEMP_DIR/success.sh"

  # Create mock failing installer with structured output
  # Accepts tool name via MOCK_TOOL_NAME environment variable
  cat > "$TEMP_DIR/failure.sh" << 'EOF'
#!/usr/bin/env bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

TOOL_NAME="${MOCK_TOOL_NAME:-mock-tool}"
DOWNLOAD_URL="https://example.com/${TOOL_NAME}.tar.gz"
VERSION="v1.0.0"
MANUAL_STEPS="1. Download from: https://example.com/${TOOL_NAME}.tar.gz
2. Extract: tar -xzf ${TOOL_NAME}.tar.gz
3. Install: mv ${TOOL_NAME} ~/.local/bin/"

output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "$MANUAL_STEPS" "Download failed - test error"
exit 1
EOF
  chmod +x "$TEMP_DIR/failure.sh"
}

teardown_file() {
  rm -rf "$TEMP_DIR" "$FAILURES_LOG"
}

setup() {
  # Clean log before each test
  rm -f "$FAILURES_LOG"
}

# ================================================================
# Test: Successful installers don't create failure log
# ================================================================

@test "orchestration: successful installer does not create failure log" {
  run run_installer "$TEMP_DIR/success.sh" "success-tool"
  assert_success

  # No log file should exist
  [[ ! -f "$FAILURES_LOG" ]]
}

# ================================================================
# Test: Failed installer creates failure log
# ================================================================

@test "orchestration: failed installer creates failure log" {
  run run_installer "$TEMP_DIR/failure.sh" "mock-tool"
  assert_failure

  # Log file should exist and have content
  [[ -f "$FAILURES_LOG" ]]
  [[ -s "$FAILURES_LOG" ]]
}

@test "orchestration: failure log contains structured data" {
  run_installer "$TEMP_DIR/failure.sh" "mock-tool" >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "mock-tool - Installation Failed"
  assert_output --partial "Download URL: https://example.com/mock-tool.tar.gz"
  assert_output --partial "Version: v1.0.0"
  assert_output --partial "Reason: Download failed - test error"
  assert_output --partial "Manual Installation Steps:"
}

# ================================================================
# Test: Multiple failures accumulate in single log
# ================================================================

@test "orchestration: multiple failures accumulate in log" {
  # Run three failures
  run_installer "$TEMP_DIR/failure.sh" "tool-1" >/dev/null 2>&1 || true
  run_installer "$TEMP_DIR/failure.sh" "tool-2" >/dev/null 2>&1 || true
  run_installer "$TEMP_DIR/failure.sh" "tool-3" >/dev/null 2>&1 || true

  # Count separator lines (each failure ends with ---)
  failure_count=$(grep -c "^---$" "$FAILURES_LOG")
  [[ "$failure_count" == "3" ]]
}

@test "orchestration: each failure has separate entry in log" {
  MOCK_TOOL_NAME="tool-1" run_installer "$TEMP_DIR/failure.sh" "tool-1" >/dev/null 2>&1 || true
  MOCK_TOOL_NAME="tool-2" run_installer "$TEMP_DIR/failure.sh" "tool-2" >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "tool-1 - Installation Failed"
  assert_output --partial "tool-2 - Installation Failed"
}

# ================================================================
# Test: Mixed success and failure
# ================================================================

@test "orchestration: success after failure does not clear log" {
  # Fail, then succeed
  MOCK_TOOL_NAME="fail-tool" run_installer "$TEMP_DIR/failure.sh" "fail-tool" >/dev/null 2>&1 || true
  run_installer "$TEMP_DIR/success.sh" "success-tool" >/dev/null 2>&1 || true

  # Log should still exist with failure entry
  [[ -f "$FAILURES_LOG" ]]
  run cat "$FAILURES_LOG"
  assert_output --partial "fail-tool - Installation Failed"
}

@test "orchestration: success does not add entry to log" {
  # Fail first to create log
  run_installer "$TEMP_DIR/failure.sh" "fail-tool" >/dev/null 2>&1 || true

  # Succeed
  run_installer "$TEMP_DIR/success.sh" "success-tool" >/dev/null 2>&1 || true

  # Log should have exactly 1 failure (not 2)
  failure_count=$(grep -c "^---$" "$FAILURES_LOG")
  [[ "$failure_count" == "1" ]]
}

# ================================================================
# Test: show_failures_summary() function
# ================================================================

@test "orchestration: show_failures_summary with no failures returns 0" {
  # No failures, no log
  run show_failures_summary
  assert_success
  assert_output ""
}

@test "orchestration: show_failures_summary displays header" {
  run_installer "$TEMP_DIR/failure.sh" "mock-tool" >/dev/null 2>&1 || true

  run show_failures_summary
  assert_success
  assert_output --partial "Installation Summary"
}

@test "orchestration: show_failures_summary shows failure count" {
  run_installer "$TEMP_DIR/failure.sh" "tool-1" >/dev/null 2>&1 || true
  run_installer "$TEMP_DIR/failure.sh" "tool-2" >/dev/null 2>&1 || true

  run show_failures_summary
  assert_success
  assert_output --partial "2 installation(s) failed"
}

@test "orchestration: show_failures_summary displays log contents" {
  run_installer "$TEMP_DIR/failure.sh" "mock-tool" >/dev/null 2>&1 || true

  run show_failures_summary
  assert_success
  assert_output --partial "mock-tool - Installation Failed"
  assert_output --partial "Download URL: https://example.com/mock-tool.tar.gz"
}

@test "orchestration: show_failures_summary shows log file path" {
  run_installer "$TEMP_DIR/failure.sh" "mock-tool" >/dev/null 2>&1 || true

  run show_failures_summary
  assert_success
  assert_output --partial "Full report saved to:"
  assert_output --partial "$FAILURES_LOG"
}

# ================================================================
# Test: Failure counting edge cases
# ================================================================

@test "orchestration: empty log file shows 0 failures" {
  touch "$FAILURES_LOG"

  run show_failures_summary
  assert_success
  assert_output ""
}

@test "orchestration: log with content but no separators shows 0 failures" {
  echo "Random content" > "$FAILURES_LOG"

  run show_failures_summary
  assert_success
  assert_output ""
}
