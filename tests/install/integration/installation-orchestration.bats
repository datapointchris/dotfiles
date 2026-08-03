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

  # Setup test environment
  export FAILURES_LOG="/tmp/test-orchestration-$$.log"
  export TEMP_DIR="/tmp/test-installers-$$"
  mkdir -p "$TEMP_DIR"

  # Create mock successful installer
  cat >"$TEMP_DIR/success.sh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$TEMP_DIR/success.sh"

  # Create mock failing installer with structured output
  # Accepts tool name via MOCK_TOOL_NAME environment variable
  cat >"$TEMP_DIR/failure.sh" <<'EOF'
#!/usr/bin/env bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"

TOOL_NAME="${MOCK_TOOL_NAME:-mock-tool}"
DOWNLOAD_URL="https://example.com/${TOOL_NAME}.tar.gz"
VERSION="v1.0.0"

output_failure_data "$TOOL_NAME" "$DOWNLOAD_URL" "$VERSION" "Download failed - test error" \
  "curl: (60) SSL certificate problem: unable to get local issuer certificate"
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

  # Sourced per test rather than exported from setup_file: run_installer calls
  # helpers that `export -f run_installer` alone does not carry across, so an
  # exported copy silently wrote nothing.
  source "$DOTFILES_DIR/install/run-installer.sh"
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
  assert_output --partial "Installer: failure.sh"
  assert_output --partial "Download URL: https://example.com/mock-tool.tar.gz"
  assert_output --partial "Version: v1.0.0"
  assert_output --partial "Error: Download failed - test error"
  assert_output --partial "curl: (60) SSL certificate problem"
}

# ================================================================
# Test: Multiple failures accumulate in single log
# ================================================================

@test "orchestration: each failure has separate entry in log" {
  MOCK_TOOL_NAME="tool-1" run_installer "$TEMP_DIR/failure.sh" "tool-1" >/dev/null 2>&1 || true
  MOCK_TOOL_NAME="tool-2" run_installer "$TEMP_DIR/failure.sh" "tool-2" >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "tool-1.tar.gz"
  assert_output --partial "tool-2.tar.gz"
}

# ================================================================
# Test: Installers that die before they can report
# ================================================================
# An installer aborting early — `set -o pipefail` tripping on a failing
# pipeline, an unbound variable — never reaches output_failure_data. These
# reached the report as a heading with nothing beneath it, which reads as the
# report having dropped the failure rather than the installer having been mute.

@test "orchestration: installer that reports nothing still names its exit code" {
  printf '#!/usr/bin/env bash\nexit 7\n' >"$TEMP_DIR/silent.sh"
  chmod +x "$TEMP_DIR/silent.sh"

  run_installer "$TEMP_DIR/silent.sh" "silent-tool" >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "silent-tool"
  assert_output --partial "Installer exited 7 without reporting a failure"
  assert_output --partial "no error output captured"
}

@test "orchestration: unreported failure still carries the installer's stderr" {
  printf '#!/usr/bin/env bash\necho "ssl: unable to get local issuer certificate" >&2\nexit 1\n' \
    >"$TEMP_DIR/noisy.sh"
  chmod +x "$TEMP_DIR/noisy.sh"

  run_installer "$TEMP_DIR/noisy.sh" "noisy-tool" >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "ssl: unable to get local issuer certificate"
  refute_output --partial "no error output captured"
}

@test "orchestration: the unknown URL sentinel is not printed back" {
  cat >"$TEMP_DIR/nourl.sh" <<'EOF'
#!/usr/bin/env bash
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
output_failure_data "nourl-tool" "unknown" "latest" "Sync failed" "boom"
exit 1
EOF
  chmod +x "$TEMP_DIR/nourl.sh"

  run_installer "$TEMP_DIR/nourl.sh" "nourl-tool" >/dev/null 2>&1 || true

  run cat "$FAILURES_LOG"
  assert_output --partial "Error: Sync failed"
  refute_output --partial "Download URL"
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
  assert_output --partial "fail-tool.tar.gz"
}

@test "orchestration: success does not add entry to log" {
  # Fail first to create log
  run_installer "$TEMP_DIR/failure.sh" "fail-tool" >/dev/null 2>&1 || true

  # Get initial log size
  initial_size=$(wc -l <"$FAILURES_LOG")

  # Succeed
  run_installer "$TEMP_DIR/success.sh" "success-tool" >/dev/null 2>&1 || true

  # Log size should not have changed
  final_size=$(wc -l <"$FAILURES_LOG")
  [[ "$initial_size" == "$final_size" ]]
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
  assert_output --partial "Installation Failures"
}

@test "orchestration: show_failures_summary displays log contents" {
  run_installer "$TEMP_DIR/failure.sh" "mock-tool" >/dev/null 2>&1 || true

  run show_failures_summary
  assert_success
  assert_output --partial "Installer: failure.sh"
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

@test "orchestration: empty log file returns without output" {
  touch "$FAILURES_LOG"

  run show_failures_summary
  assert_success
  assert_output ""
}

# ================================================================
# Test: Minimal and unstructured failures (regression tests)
# ================================================================

@test "orchestration: failure with only the required fields does not cause unbound variable" {
  cat >"$TEMP_DIR/simple-failure.sh" <<'EOF'
#!/usr/bin/env bash
echo "FAILURE_TOOL='simple-tool'" >&2
echo "FAILURE_REASON='Simple failure with no detail block'" >&2
exit 1
EOF
  chmod +x "$TEMP_DIR/simple-failure.sh"

  # This should not fail with "unbound variable" error
  run run_installer "$TEMP_DIR/simple-failure.sh" "simple-tool"
  assert_failure

  # Log should exist and contain the error
  [[ -f "$FAILURES_LOG" ]]
  run cat "$FAILURES_LOG"
  assert_output --partial "Simple failure with no detail block"
}

@test "orchestration: installer emitting no markers still reports its stderr" {
  # The common case for a third-party installer that just dies: no structured
  # output at all. Its stderr is the only diagnosis available, so it becomes the
  # error detail rather than being dropped for a bare "Installation failed".
  cat >"$TEMP_DIR/unstructured-failure.sh" <<'EOF'
#!/usr/bin/env bash
echo "tar: Unexpected EOF in archive" >&2
exit 2
EOF
  chmod +x "$TEMP_DIR/unstructured-failure.sh"

  run run_installer "$TEMP_DIR/unstructured-failure.sh" "mystery-tool"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "mystery-tool - Installation Failed"
  assert_output --partial "tar: Unexpected EOF in archive"
}

@test "orchestration: each failed tool in one run gets its own entry" {
  # go-tools.sh loops over every Go package, so one script can report several
  # failures. Parsing the fields with a flat grep spliced them into a single
  # entry naming the first tool with the last tool's URL.
  cat >"$TEMP_DIR/multi-failure.sh" <<'EOF'
#!/usr/bin/env bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
source "$DOTFILES_DIR/install/common/lib/failure-logging.sh"
output_failure_data "first-tool" "https://example.com/first" "v1" "Failed" "first tool error"
output_failure_data "second-tool" "https://example.com/second" "v2" "Failed" "second tool error"
exit 1
EOF
  chmod +x "$TEMP_DIR/multi-failure.sh"

  run run_installer "$TEMP_DIR/multi-failure.sh" "go-tools"
  assert_failure

  run cat "$FAILURES_LOG"
  assert_output --partial "first-tool - Installation Failed"
  assert_output --partial "second-tool - Installation Failed"
  assert_output --partial "first tool error"
  assert_output --partial "second tool error"

  # Each entry keeps its own URL rather than borrowing the other's
  entry_count=$(grep -c "Installation Failed" "$FAILURES_LOG")
  assert_equal "$entry_count" 2
}
