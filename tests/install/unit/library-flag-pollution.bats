#!/usr/bin/env bats
# shellcheck disable=SC2317
# ================================================================
# Unit test for library flag pollution
# ================================================================
# Verifies that sourcing libraries does NOT add unwanted shell flags,
# specifically the -e flag which causes premature exits. Libraries should
# be composable without side effects on the calling script's environment.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

# Helper function to test a library for flag pollution
test_library_flags() {
  local library="$1"

  # A missing library sources to an error and carries on, because the probe
  # below deliberately runs without -e. It then adds no -e flag, so it passes.
  # install/common/lib/platform-detection.sh was in the list for months and had
  # never existed; the suite reported seven libraries covered and checked six.
  if [[ ! -f $library ]]; then
    echo "FAIL: No library at $library — the list names a file that is not there"
    return 1
  fi

  # Create a test script that checks flags before and after sourcing
  local test_script
  test_script=$(mktemp)
  cat >"$test_script" <<'TESTEOF'
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
# Every library, one test
# ================================================================
# The list is the point: a new library is one line here, not a copy of the whole
# @test. This was one identical test per library, differing only in the path.

@test "library_flags: no library adds -e to its caller" {
  local library
  for library in \
    configs/common/.local/shell/logging.sh \
    configs/common/.local/shell/formatting.sh \
    configs/common/.local/shell/error-handling.sh \
    install/common/lib/failure-logging.sh \
    install/common/lib/version-helpers.sh \
    install/platform-detection.sh; do

    run test_library_flags "$DOTFILES_DIR/$library"
    # The path is in the failure message because the loop hides which one broke.
    assert_success "$library added -e"
  done
}
