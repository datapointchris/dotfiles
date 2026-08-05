#!/usr/bin/env bats
# ================================================================
# Unit tests for the dotfiles CLI
# ================================================================
# The CLI's reason to exist is working from any directory, so every test runs
# from a temp dir, through a symlink, the way the deployed ~/.local/bin entry
# is invoked.
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
