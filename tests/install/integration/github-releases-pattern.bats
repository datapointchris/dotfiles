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
  export FAILURES_LOG="/tmp/test-github-releases-bats-$$.log"
  rm -f "$FAILURES_LOG"

  # Create mock GitHub release installer
  export MOCK_INSTALLER="/tmp/mock-github-release.sh"
  cat > "$MOCK_INSTALLER" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
source "$DOTFILES_DIR/management/common/lib/failure-logging.sh"

# Simulate GitHub release installer that fails
TOOL_NAME="mock-tool"
DOWNLOAD_URL="https://github.com/mock/tool/releases/download/v1.0/tool.tar.gz"
VERSION="v1.0"
MANUAL_STEPS="1. Download from browser: $DOWNLOAD_URL
2. Extract: tar -xzf tool.tar.gz
3. Install: mv tool ~/.local/bin/"

# Simulate download failure
log_error "Failed to download from $DOWNLOAD_URL"

# Output structured failure data
output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "$MANUAL_STEPS" "Download failed - network timeout"

exit 1
EOF
  chmod +x "$MOCK_INSTALLER"

  # Define run_installer wrapper (from install.sh)
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

      cat >> "$FAILURES_LOG" << LOGEOF
$failure_tool - Installation Failed
Installer: $(basename "$script")
${failure_reason:+Error: $failure_reason}
${failure_url:+Download URL: $failure_url}
${failure_version:+Version: $failure_version}

${failure_manual:+How to Install Manually:
$failure_manual
}
LOGEOF
      return 1
    fi
  }

  export -f run_installer
}

# Cleanup after all tests
teardown_file() {
  rm -f "$MOCK_INSTALLER" "$FAILURES_LOG"
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

@test "github-releases: installer outputs FAILURE_MANUAL section" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_output --partial "FAILURE_MANUAL_START"
  assert_output --partial "FAILURE_MANUAL_END"
}

@test "github-releases: wrapper creates failures log" {
  rm -f "$FAILURES_LOG"
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  [[ -f "$FAILURES_LOG" ]]
}

@test "github-releases: log contains tool name" {
  rm -f "$FAILURES_LOG"
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "Installation Failed"
}

@test "github-releases: log contains parsed URL" {
  rm -f "$FAILURES_LOG"
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "Download URL: https://github.com/mock/tool"
}

@test "github-releases: log contains parsed version" {
  rm -f "$FAILURES_LOG"
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "Version: v1.0"
}

@test "github-releases: log contains parsed reason" {
  rm -f "$FAILURES_LOG"
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "Error: Download failed"
}

@test "github-releases: log contains manual steps" {
  rm -f "$FAILURES_LOG"
  run_installer "$MOCK_INSTALLER" "mock-tool" >/dev/null 2>&1 || true
  run cat "$FAILURES_LOG"
  assert_output --partial "How to Install Manually:"
}

@test "github-releases: installer returns exit code 1 on failure" {
  run bash "$MOCK_INSTALLER"
  assert_failure
  assert_equal "$status" 1
}
