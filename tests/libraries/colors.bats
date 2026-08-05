#!/usr/bin/env bats
#
# Tests for the colour gate in colors.sh.
#
# The contract is that escape sequences are emitted only where something will
# render them. Every test sources colors.sh in a fresh subshell, because the
# palette is resolved once at source time and that is the behaviour under test.

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  export COLORS_SH="$DOTFILES_DIR/configs/common/.local/shell/colors.sh"
}

# Sources colors.sh in a clean subshell and prints one variable's raw bytes.
# The environment is scrubbed first so an outer FORCE_COLOR cannot mask a
# regression.
probe() {
  local var="$1"
  shift
  env -u NO_COLOR -u FORCE_COLOR -u TERM "$@" \
    bash -c "source \"\$1\"; printf '%s' \"\${$var}\"" _ "$COLORS_SH"
}

@test "a pipe gets no colour" {
  run probe COLOR_RED
  assert_success
  assert_output ""
}

@test "a pipe gets no reset either, so nothing emits a bare escape" {
  run probe COLOR_RESET
  assert_output ""
}

@test "FORCE_COLOR overrides the non-terminal detection" {
  run probe COLOR_RED FORCE_COLOR=1
  assert_output '\033[0;31m'
}

@test "NO_COLOR outranks FORCE_COLOR" {
  run probe COLOR_RED FORCE_COLOR=1 NO_COLOR=1
  assert_output ""
}

@test "TERM=dumb gets no colour" {
  run probe COLOR_RED TERM=dumb
  assert_output ""
}

@test "the short aliases follow the gate" {
  run probe RED
  assert_output ""
  run probe RED FORCE_COLOR=1
  assert_output '\033[0;31m'
}

@test "COLOR_ENABLED reports the decision" {
  run probe COLOR_ENABLED
  assert_output "0"
  run probe COLOR_ENABLED FORCE_COLOR=1
  assert_output "1"
}

@test "the stored value is the literal escape, not a resolved ESC byte" {
  # echo -e is what renders these, so storing a real ESC would change what every
  # caller emits. zsh sources this file too and its printf must agree with bash.
  run probe COLOR_RED FORCE_COLOR=1
  assert_output '\033[0;31m'

  # The workstations all have zsh; the CI runner does not, and the bash half
  # above already covers the property that actually regresses.
  command -v zsh >/dev/null || skip "zsh not installed"
  run env -u NO_COLOR -u TERM FORCE_COLOR=1 \
    zsh -c "source \"\$1\"; printf '%s' \"\$COLOR_RED\"" _ "$COLORS_SH"
  assert_output '\033[0;31m'
}

@test "a colour function still renders when colour is on" {
  run env -u NO_COLOR -u TERM FORCE_COLOR=1 \
    bash -c "source \"\$1\"; color_red hello" _ "$COLORS_SH"
  assert_output "$(printf '\033[0;31mhello\033[0m')"
}

@test "a colour function degrades to plain text when colour is off" {
  run env -u NO_COLOR -u FORCE_COLOR -u TERM \
    bash -c "source \"\$1\"; color_red hello" _ "$COLORS_SH"
  assert_output "hello"
}
