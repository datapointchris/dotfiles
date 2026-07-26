#!/usr/bin/env bats
# ================================================================
# Unit tests for the dotfiles CLI
# ================================================================
# The CLI's reason to exist is working from any directory, so every test runs
# from a temp dir, through a symlink, the way the deployed ~/.local/bin entry
# is invoked.
# ================================================================

load "$HOME/.local/lib/bats-support/load.bash"
load "$HOME/.local/lib/bats-assert/load.bash"

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

@test "dotfiles: resolves the repo through a symlink from an unrelated cwd" {
  run "$CLI" path
  assert_success
  assert_output "$DOTFILES_DIR"
}

@test "dotfiles: resolves the repo through a chain of symlinks" {
  ln -s "$CLI" "$TEST_DIR/dotfiles-indirect"
  run "$TEST_DIR/dotfiles-indirect" path
  assert_success
  assert_output "$DOTFILES_DIR"
}

@test "dotfiles: works when invoked directly rather than through a symlink" {
  run "$CLI_SOURCE" path
  assert_success
  assert_output "$DOTFILES_DIR"
}

# ================================================================
# Dispatch
# ================================================================

@test "dotfiles: no arguments shows help" {
  run "$CLI"
  assert_success
  assert_output --partial "Usage: dotfiles <command>"
}

@test "dotfiles: help is reachable by every documented spelling" {
  for flag in help -h --help; do
    run "$CLI" "$flag"
    assert_success
    assert_output --partial "Usage: dotfiles <command>"
  done
}

@test "dotfiles: unknown command fails" {
  run "$CLI" nonsense
  assert_failure
  assert_output --partial "Unknown command"
}

@test "dotfiles: every advertised command has a dispatch arm" {
  local name
  while read -r name; do
    [[ -z "$name" ]] && continue
    run grep -qE "^  ($name|.*\| ?$name)[ )|]" "$CLI_SOURCE"
    assert_success
  done < <("$CLI" __commands)
}

@test "dotfiles: help lists every advertised command" {
  local help_output name
  help_output=$("$CLI")
  while read -r name; do
    [[ -z "$name" ]] && continue
    echo "$help_output" | grep -q "  $name"
  done < <("$CLI" __commands)
}

# ================================================================
# Delegation
# ================================================================

@test "dotfiles: update forwards its arguments to update.sh" {
  run "$CLI" update --list
  assert_success
  assert_output --partial "Update Groups"
}

@test "dotfiles: update rejects a bad group via update.sh" {
  run "$CLI" update notagroup
  assert_failure
  assert_output --partial "Unknown group"
}

@test "dotfiles: symlinks requires a verb" {
  run "$CLI" symlinks
  assert_success
  assert_output --partial "Usage: symlinks.sh"
}

@test "dotfiles: symlinks rejects an unknown verb" {
  run "$CLI" symlinks bogus
  assert_failure
  assert_output --partial "Unknown verb"
}

@test "dotfiles: docs without a verb shows its usage" {
  run "$CLI" docs
  assert_success
  assert_output --partial "Usage: docs.sh"
}

@test "dotfiles: docs rejects an unknown verb" {
  run "$CLI" docs bogus
  assert_failure
  assert_output --partial "Unknown verb"
}

@test "dotfiles: windows rejects an unknown verb" {
  run "$CLI" windows bogus
  assert_failure
  assert_output --partial "Unknown windows verb"
}

@test "dotfiles: test rejects an unknown suite" {
  run "$CLI" test bogus
  assert_failure
  assert_output --partial "Unknown suite"
}
