#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Integration test for GitHub release installers pattern
# ================================================================
# Tests that GitHub release installers:
# 1. Output structured failure data using output_failure_data()
# 2. Return proper exit codes (0 for success, 1 for failure)
# 3. Work with run_installer wrapper
# 4. Generate properly formatted failure logs
#
# run_installer is sourced from install/run-installer.sh rather than copied in.
# The copy that used to live here parsed FAILURE_* fields with a flat grep over
# the whole stderr, so it passed while the real wrapper spliced two tools'
# fields into one nonsense entry.
# ================================================================

# Load BATS helpers (from ~/.local installation)
load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export SCRIPT_DIR
  SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  export DOTFILES_DIR
  DOTFILES_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

  # Create mock GitHub release installer
  export MOCK_INSTALLER="/tmp/mock-github-release.sh"
  cat >"$MOCK_INSTALLER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/configs/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

# Simulate GitHub release installer that fails
TOOL_NAME="mock-tool"
DOWNLOAD_URL="https://github.com/mock/tool/releases/download/v1.0/tool.tar.gz"
VERSION="v1.0"

# Simulate download failure
log_error "Failed to download from $DOWNLOAD_URL"

# Output structured failure data
output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "Download failed - network timeout" \
  "curl: (60) SSL certificate problem: unable to get local issuer certificate"

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
# Tests
# ================================================================

@test "github-releases: installer outputs FAILURE_TOOL field" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_TOOL='mock-tool'"
}

@test "github-releases: installer outputs FAILURE_URL field" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_URL='https://github.com/mock/tool"
}

@test "github-releases: installer outputs FAILURE_VERSION field" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_VERSION='v1.0'"
}

@test "github-releases: installer outputs FAILURE_REASON field" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_REASON='Download failed"
}

@test "github-releases: installer outputs FAILURE_DETAIL section" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_DETAIL_START"
  assert_output --partial "FAILURE_DETAIL_END"
}

@test "github-releases: wrapper creates failures log" {
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  [[ -f "$FAILURES_LOG" ]]
}

@test "github-releases: log contains tool name" {
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "Installation Failed"
}

@test "github-releases: log contains parsed URL" {
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "Download URL: https://github.com/mock/tool"
}

@test "github-releases: log contains parsed version" {
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "Version: v1.0"
}

@test "github-releases: log contains parsed reason" {
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "Error: Download failed"
}

@test "github-releases: log contains the failing command's error output" {
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "curl: (60) SSL certificate problem"
}

@test "github-releases: log has no manual-instruction section" {
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  refute_output --partial "How to Install Manually"
}

@test "github-releases: installer returns exit code 1 on failure" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_equal "$status" 1
}
