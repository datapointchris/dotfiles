# shellcheck shell=bash
# ================================================================
# bats-support + bats-assert, loaded without the forks
# ================================================================
# Every test process sources this, so its cost is paid once per @test, not once
# per file. The upstream load.bash files run `$(dirname "${BASH_SOURCE[0]}")`
# once per source -- fifteen subprocesses per test, ~120ms on macOS, which was
# more than half the suite's wall time. The paths are the same, resolved with
# parameter expansion instead.
#
# Sourced by every .bats file as, from any depth:
#   load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"
#
# which also exports DOTFILES_DIR, since the same expansion yields the repo root.
# ================================================================

BATS_LIB_DIR="${BATS_LIB_DIR:-$HOME/.local/lib}"

# bats-support's own loader sets this, and its assertions read it to run
# commands from the real PATH rather than a test's stubs.
BATS_SAVED_PATH="${BATS_SAVED_PATH-$PATH}"

for _bats_lib in output error lang; do
  source "$BATS_LIB_DIR/bats-support/src/$_bats_lib.bash"
done

for _bats_lib in assert refute assert_equal assert_not_equal assert_success \
  assert_failure assert_output refute_output assert_line refute_line \
  assert_regex refute_regex; do
  source "$BATS_LIB_DIR/bats-assert/src/$_bats_lib.bash"
done

unset _bats_lib

export DOTFILES_DIR="${DOTFILES_DIR:-${BATS_TEST_FILENAME%/tests/*}}"
