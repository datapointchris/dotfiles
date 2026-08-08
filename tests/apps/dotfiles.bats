#!/usr/bin/env bats
# ================================================================
# Unit tests for the bash dotfiles CLI, and its handover to the Python one
# ================================================================
# The CLI's reason to exist is working from any directory, so every test runs
# from a temp dir, through a symlink, the way the deployed ~/.local/bin entry
# is invoked.
#
# This file outlives the bash CLI by exactly one step. `dotfiles` is now a
# console script in pyproject.toml, so the symlink manager refuses to deploy
# apps/common/dotfiles over it and the Python tree is what a machine gets. The
# handover section below asserts the two agree on the verbs that carry over,
# which is the only thing that makes deleting the bash one safe rather than
# hopeful. Both go when the Python CLI installs itself, in step 3.
# ================================================================

load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

setup_file() {
  DOTFILES_DIR="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
  export DOTFILES_DIR
  export CLI_SOURCE="$DOTFILES_DIR/apps/common/dotfiles"
}

setup() {
  TEST_DIR=$(mktemp -d)
  CLI="$TEST_DIR/dotfiles"
  ln -s "$CLI_SOURCE" "$CLI"
  cd "$TEST_DIR" || exit 1
}

teardown() {
  cd / || exit 1
  rm -rf "$TEST_DIR"
}

# ================================================================
# Repository resolution
# ================================================================

@test "dotfiles: resolves the repo however it was invoked" {
  # Through the deployed symlink, through a symlink to that symlink, and
  # directly -- the resolution has to survive all three.
  run "$CLI" path
  assert_success
  assert_output "$DOTFILES_DIR"

  ln -s "$CLI" "$TEST_DIR/dotfiles-indirect"
  run "$TEST_DIR/dotfiles-indirect" path
  assert_success
  assert_output "$DOTFILES_DIR"

  run "$CLI_SOURCE" path
  assert_success
  assert_output "$DOTFILES_DIR"
}

# ================================================================
# Dispatch
# ================================================================

@test "dotfiles: help is the no-argument behaviour and every documented spelling" {
  run "$CLI"
  assert_success
  assert_output --partial "Usage: dotfiles <command>"

  for flag in help -h --help; do
    run "$CLI" "$flag"
    assert_success
    assert_output --partial "Usage: dotfiles <command>"
  done

  run "$CLI" nonsense
  assert_failure
  assert_output --partial "Unknown command"
}

@test "dotfiles: every advertised command is dispatched and documented" {
  # __commands is the list the CLI advertises; both the case statement and the
  # help screen have to agree with it, or a command exists in name only.
  local help_output name
  help_output=$("$CLI")
  while read -r name; do
    [[ -z "$name" ]] && continue
    run grep -qE "^[[:space:]]*($name|.*\| ?$name)[ )|]" "$CLI_SOURCE"
    assert_success
    echo "$help_output" | grep -q "  $name"
  done < <("$CLI" __commands)
}

# ================================================================
# Delegation
# ================================================================
# The CLI is a front door: each verb must reach the script behind it, and that
# script's own failures must come back out rather than being turned into a
# usage error by the dispatcher.

@test "dotfiles: update and install forward their arguments" {
  run "$CLI" update --list
  assert_success
  assert_output --partial "update groups and phases"

  run "$CLI" install --list
  assert_success
  assert_output --partial "install groups and phases"

  run "$CLI" update notagroup
  assert_failure
  assert_output --partial "Unknown group"
}

@test "dotfiles: subcommand verbs show usage bare and reject a bad verb" {
  run "$CLI" symlinks
  assert_success
  assert_output --partial "Usage: symlinks.sh"

  run "$CLI" symlinks bogus
  assert_failure
  assert_output --partial "Unknown verb"

  run "$CLI" docs
  assert_success
  assert_output --partial "Usage: docs.sh"

  run "$CLI" docs bogus
  assert_failure
  assert_output --partial "Unknown verb"

  run "$CLI" windows bogus
  assert_failure
  assert_output --partial "Unknown windows verb"

  run "$CLI" test bogus
  assert_failure
  assert_output --partial "Unknown suite"
}

# ================================================================
# Handover to the Python CLI
# ================================================================
# The Python tree is the replacement, so what matters is that the verbs
# carrying over answer the same. Run through `uv run` from the repo: the
# console script is not on PATH until a machine installs the tool, and this
# has to pass on a machine that has not.

new_cli() {
  (cd "$DOTFILES_DIR" && uv run dotfiles "$@")
}

@test "handover: both front doors resolve the same repository" {
  run "$CLI" path
  assert_success
  local from_bash="$output"

  run new_cli repo path
  assert_success
  assert_output "$from_bash"
}

@test "handover: the python tree covers every bash command" {
  # Not a rename check -- `link`/`relink` deliberately collapse into
  # `symlinks apply`, and `doctor` into `check`. What must not happen is a verb
  # disappearing with nothing named as its replacement.
  local -A replacement=(
    [update]="apply"
    [install]="apply"
    [doctor]="check"
    [env]="env"
    [link]="symlinks"
    [relink]="symlinks"
    [symlinks]="symlinks"
    [windows]="windows"
    [pull]="update"
    [status]="repo"
    [path]="repo"
    [edit]="repo"
    # test and docs move to `task`, which is the tool that already owns them.
    [test]="-"
    [docs]="-"
  )

  run new_cli --help
  assert_success
  local help_output="$output"

  local name
  while read -r name; do
    [[ -z "$name" ]] && continue
    local target="${replacement[$name]:-}"
    [[ -n "$target" ]] || fail "bash command '$name' has no recorded replacement"
    [[ "$target" == "-" ]] && continue
    echo "$help_output" | grep -q "$target" || fail "'$name' maps to '$target', absent from the python help"
  done < <("$CLI" __commands)
}

@test "handover: check agrees with doctor on this machine" {
  # Both read the same five checkers, so they must agree on whether this machine
  # is converged. Compared as converged-or-not rather than by exit code: doctor
  # collapses everything into 1, while check reserves 3 for an Issue, so on a
  # machine with no ~/.env -- a CI runner, a fresh box -- the numbers differ by
  # design and only the verdict is comparable.
  local doctor_converged check_converged

  run bash "$DOTFILES_DIR/install/ops/doctor.sh"
  doctor_converged=$([[ "$status" -eq 0 ]] && echo yes || echo no)

  run new_cli check
  check_converged=$([[ "$status" -eq 0 ]] && echo yes || echo no)

  assert_equal "$check_converged" "$doctor_converged"
}
