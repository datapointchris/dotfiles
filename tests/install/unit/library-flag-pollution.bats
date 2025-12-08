#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit test for library flag pollution
# ================================================================
# Verifies that sourcing libraries does NOT add unwanted shell flags,
# specifically the -e flag which causes premature exits. Libraries should
# be composable without side effects on the calling script's environment.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

# Helper function to test a library for flag pollution
test_library_flags() {
  local library="$1"

  # Create a test script that checks flags before and after sourcing
  local test_script=$(mktemp)
  cat > "$test_script" << 'TESTEOF'
#!/usr/bin/env bash
set -u
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"

FLAGS_BEFORE="$-"
source "$LIBRARY_PATH"
FLAGS_AFTER="$-"

# Check if -e was added
if [[ "$FLAGS_BEFORE" != *e* ]] && [[ "$FLAGS_AFTER" == *e* ]]; then
  echo "FAIL: Library added -e flag"
  echo "Before: $FLAGS_BEFORE"
  echo "After:  $FLAGS_AFTER"
  exit 1
fi

exit 0
TESTEOF

  chmod +x "$test_script"
  LIBRARY_PATH="$library" bash "$test_script"
  local result=$?
  rm -f "$test_script"
  return $result
}

# ================================================================
# Test: Common shell libraries
# ================================================================

@test "library_flags: logging.sh does not add -e flag" {
  run test_library_flags "$DOTFILES_DIR/platforms/common/.local/shell/logging.sh"
  assert_success
}

@test "library_flags: formatting.sh does not add -e flag" {
  run test_library_flags "$DOTFILES_DIR/platforms/common/.local/shell/formatting.sh"
  assert_success
}

@test "library_flags: error-handling.sh does not add -e flag" {
  run test_library_flags "$DOTFILES_DIR/platforms/common/.local/shell/error-handling.sh"
  assert_success
}

# ================================================================
# Test: Management libraries
# ================================================================

@test "library_flags: failure-logging.sh does not add -e flag" {
  run test_library_flags "$DOTFILES_DIR/management/common/lib/failure-logging.sh"
  assert_success
}

@test "library_flags: github-release-installer.sh does not add -e flag" {
  run test_library_flags "$DOTFILES_DIR/management/common/lib/github-release-installer.sh"
  assert_success
}

@test "library_flags: font-installer.sh does not add -e flag" {
  run test_library_flags "$DOTFILES_DIR/management/common/lib/font-installer.sh"
  assert_success
}

@test "library_flags: version-helpers.sh does not add -e flag" {
  run test_library_flags "$DOTFILES_DIR/management/common/lib/version-helpers.sh"
  assert_success
}

@test "library_flags: platform-detection.sh does not add -e flag" {
  run test_library_flags "$DOTFILES_DIR/management/orchestration/platform-detection.sh"
  assert_success
}
