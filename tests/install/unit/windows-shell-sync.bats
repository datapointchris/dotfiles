#!/usr/bin/env bats
# ================================================================
# Unit tests for sync-windows-shell.sh
# ================================================================
# The Windows shell tree is assembled on WSL and only ever executed by Git Bash
# on Windows, so a fault in it surfaces days later, on the one machine with no
# working shell left to debug from. These tests run the real staging and .bashrc
# generation and load the result, on any platform.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../../.."
}

setup() {
  TEST_DIR=$(mktemp -d)
  STAGED="$TEST_DIR/.local/shell"

  # Sourcing runs neither main nor the WSL detection, so this works on any
  # platform; the script's own guard is what makes that possible.
  source "$DOTFILES_DIR/install/wsl/sync-windows-shell.sh"

  stage_shell_files "$STAGED" >/dev/null
  write_bashrc "$TEST_DIR"
}

teardown() {
  rm -rf "$TEST_DIR"
}

# Builds a script that loads the generated .bashrc and then runs whatever the
# test pipes in. A file rather than `bash -c` so the probe can name $HOME and
# the palette variables literally, as Git Bash would.
write_probe() {
  cat >"$TEST_DIR/probe.sh" <<'PROBE'
source "$HOME/.bashrc"
PROBE
  cat >>"$TEST_DIR/probe.sh"
}

# Runs the probe with HOME pointed at the staged tree, merging stderr so the
# per-file load warnings are visible to assertions.
load_bashrc() {
  env HOME="$TEST_DIR" bash --norc --noprofile "$TEST_DIR/probe.sh" 2>&1
}

@test "every file in the load order is staged and parses as bash" {
  for f in "${SHELL_FILES[@]}"; do
    assert [ -f "$STAGED/$f" ]
    run bash -n "$STAGED/$f"
    assert_success
  done
}

@test "the .bashrc parses and loads without error" {
  run bash -n "$TEST_DIR/.bashrc"
  assert_success

  write_probe <<'PROBE'
echo loaded
PROBE
  run load_bashrc
  assert_success
  assert_output --partial "loaded"
  refute_output --partial "failed to load"
  refute_output --partial "No such file"
}

@test "the loaded shell has the palette, the helpers, and the aliases" {
  # bats captures stdout, so without this the gate in colors.sh blanks the
  # palette and the assertion would pass on an empty string. See colors.bats.
  export FORCE_COLOR=1

  write_probe <<'PROBE'
declare -F print_success >/dev/null || exit 1
[[ -n "$COLOR_RED" ]] || exit 1
alias open
PROBE
  run load_bashrc
  assert_success
  assert_output --partial "start"
}

@test "the windows override is loaded after the shared files" {
  local windows_pos shared_pos i=0
  for f in "${SHELL_FILES[@]}"; do
    i=$((i + 1))
    [[ "$f" == "windows.sh" ]] && windows_pos=$i
    [[ "$f" == "aliases.sh" ]] && shared_pos=$i
  done
  assert [ "$windows_pos" -gt "$shared_pos" ]
}

@test "a broken file costs only itself" {
  # The regression this whole layout exists for: a syntax error used to be fatal
  # to everything after it, because every file was concatenated into one.
  printf 'if true; then\n' >>"$STAGED/functions.sh"

  write_probe <<'PROBE'
declare -F print_success >/dev/null || exit 1
alias open
PROBE
  run load_bashrc
  assert_success
  assert_output --partial "functions.sh failed to load"
  assert_output --partial "start"
}

@test "a missing file is skipped rather than fatal" {
  rm "$STAGED/wsl.sh"

  write_probe <<'PROBE'
echo survived
PROBE
  run load_bashrc
  assert_success
  assert_output --partial "survived"
  refute_output --partial "No such file"
}

@test "staging clears a combined.sh left by the old generator" {
  : >"$STAGED/combined.sh"
  stage_shell_files "$STAGED" >/dev/null
  assert [ ! -f "$STAGED/combined.sh" ]
}
