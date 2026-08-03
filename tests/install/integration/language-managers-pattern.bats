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
#
# run_installer is sourced from install/run-installer.sh rather than copied in.
# The copy that used to live here wrote a "Script:/Exit Code:/Timestamp:" report
# the real wrapper has never produced, so every assertion below the wrapper
# boundary was checking a format that did not exist.
# ================================================================

# Load BATS helpers (from ~/.local installation)
load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  export SCRIPT_DIR
  SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  export DOTFILES_DIR
  DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

  # Create mock language manager installer
  export MOCK_INSTALLER="/tmp/mock-language-manager.sh"
  cat >"$MOCK_INSTALLER" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

# Simulate language manager installer that fails
TOOL_NAME="mock-lang-manager"
DOWNLOAD_URL="https://example.com/install.sh"
VERSION="v1.0"

# Simulate download failure
log_error "Failed to download installer from $DOWNLOAD_URL"

# Output structured failure data
output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "Download failed - network timeout" \
  "curl: (35) OpenSSL SSL_connect: Connection reset by peer"

exit 1
EOF
  chmod +x "$MOCK_INSTALLER"
}

setup() {
  export FAILURES_LOG="$BATS_TEST_TMPDIR/failures.log"
  rm -f "$FAILURES_LOG"
  source "$DOTFILES_DIR/install/run-installer.sh"
}

teardown_file() {
  rm -f "$MOCK_INSTALLER"
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

@test "installer outputs FAILURE_DETAIL markers around the error output" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_DETAIL_START"
  assert_output --partial "curl: (35) OpenSSL SSL_connect"
  assert_output --partial "FAILURE_DETAIL_END"
}

# ================================================================
# Test Suite 2: run_installer wrapper captures structured data
# ================================================================

@test "wrapper returns failure status when installer fails" {
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure
}

@test "wrapper creates failures log file" {
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure
  assert [ -f "$FAILURES_LOG" ]
}

@test "failure log contains tool name header" {
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "mock-lang-manager - Installation Failed"
}

@test "failure log contains download URL" {
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Download URL: https://example.com/install.sh"
}

@test "failure log contains version" {
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Version: v1.0"
}

@test "failure log contains reason" {
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Error: Download failed"
}

@test "failure log contains the failing command's error output" {
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "curl: (35) OpenSSL SSL_connect"
}

@test "failure log names the installer script" {
  run run_installer "$MOCK_INSTALLER" "mock-lang-manager"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "Installer: $(basename "$MOCK_INSTALLER")"
}
