#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Integration test for language manager installers pattern
# ================================================================
# Tests that language manager installers:
# 1. Output structured failure data using output_failure_data()
# 2. Return proper exit codes (0 for success, 1 for failure)
# 3. Work with run_installer wrapper
# 4. Generate properly formatted failure logs
# ================================================================

# Load BATS helpers (from ~/.local installation)
load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

# Setup runs once before all tests
setup_file() {
  export SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  export DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

  # Source libraries
  source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  source "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
  source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

  # Setup test environment
  export FAILURES_LOG="/tmp/test-language-managers-bats-$$.log"
  rm -f "$FAILURES_LOG"

  # Create mock language manager installer
  export MOCK_INSTALLER="/tmp/mock-language-manager.sh"
  cat > "$MOCK_INSTALLER" << 'EOF'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

# Simulate language manager installer that fails
TOOL_NAME="mock-lang-manager"
DOWNLOAD_URL="https://example.com/install.sh"
VERSION="v1.0"
MANUAL_STEPS="1. Download from: $DOWNLOAD_URL
2. Run: bash install.sh
3. Verify: mock-lang-manager --version"

# Simulate download failure
log_error "Failed to download installer from $DOWNLOAD_URL"

# Output structured failure data
output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "$MANUAL_STEPS" "Download failed - network timeout"

exit 1
EOF
  chmod +x "$MOCK_INSTALLER"

  # Define run_installer wrapper
  run_installer() {
    local script="$1"
    local tool_name="$2"

    local output
    local exit_code

    output=$(bash "$script" 2>&1)
    exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
      return 0
    else
      local failure_tool failure_url failure_version failure_reason failure_manual
      failure_tool=$(echo "$output" | grep "^FAILURE_TOOL=" | cut -d"'" -f2 || echo "$tool_name")
      failure_url=$(echo "$output" | grep "^FAILURE_URL=" | cut -d"'" -f2 || echo "")
      failure_version=$(echo "$output" | grep "^FAILURE_VERSION=" | cut -d"'" -f2 || echo "")
      failure_reason=$(echo "$output" | grep "^FAILURE_REASON=" | cut -d"'" -f2 || echo "")

      if echo "$output" | grep -q "^FAILURE_MANUAL_START"; then
        failure_manual=$(echo "$output" | sed -n '/^FAILURE_MANUAL_START$/,/^FAILURE_MANUAL_END$/p' | sed '1d;$d')
      fi

      cat >> "$FAILURES_LOG" << EOF_LOG
========================================
$failure_tool - Installation Failed
========================================
Script: $script
Exit Code: $exit_code
Timestamp: $(date -Iseconds)
${failure_url:+Download URL: $failure_url}
${failure_version:+Version: $failure_version}
${failure_reason:+Reason: $failure_reason}

${failure_manual:+Manual Installation Steps:
$failure_manual
}
---

EOF_LOG
      return 1
    fi
  }
  export -f run_installer
}

# Teardown runs once after all tests
teardown_file() {
  rm -f "$MOCK_INSTALLER" "$FAILURES_LOG"
}

# ================================================================
# Test Suite 1: Installer outputs structured failure data
# ================================================================

@test "installer returns exit code 1 on failure" {
  run bash "$MOCK_INSTALLER"
  assert_failure
}

@test "installer outputs FAILURE_TOOL field with correct value" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_TOOL='mock-lang-manager'"
}

@test "installer outputs FAILURE_URL field with correct value" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_URL='https://example.com/install.sh'"
}

@test "installer outputs FAILURE_VERSION field with correct value" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_VERSION='v1.0'"
}

@test "installer outputs FAILURE_REASON field" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_REASON='Download failed"
}

@test "installer outputs FAILURE_MANUAL_START marker" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_MANUAL_START"
}

@test "installer outputs FAILURE_MANUAL_END marker" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_MANUAL_END"
}

# ================================================================
# Test Suite 2: run_installer wrapper captures structured data
# ================================================================

@test "wrapper returns failure status when installer fails" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure
}

@test "wrapper creates failures log file" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure
  assert [ -f "$FAILURES_LOG" ]
}

@test "failure log contains tool name header" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "mock-lang-manager - Installation Failed"
}

@test "failure log contains download URL" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Download URL: https://example.com/install.sh"
}

@test "failure log contains version" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Version: v1.0"
}

@test "failure log contains reason" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Reason: Download failed"
}

@test "failure log contains manual installation steps" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Manual Installation Steps:"
}

@test "failure log includes script path" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Script: $MOCK_INSTALLER"
}

@test "failure log includes exit code" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Exit Code: 1"
}

@test "failure log includes timestamp" {
  rm -f "$FAILURES_LOG"
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Timestamp:"
}
