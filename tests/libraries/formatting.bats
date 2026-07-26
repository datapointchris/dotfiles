#!/usr/bin/env bats
#
# Tests for the help-screen functions in formatting.sh
#
# These carry the alignment contract every CLI help screen depends on: the
# colour escapes must sit outside the padded field, and the two-space indent
# must stay flush against the name so the CLI help tests can grep for it.

setup() {
  load "$HOME/.local/lib/bats-support/load.bash"
  load "$HOME/.local/lib/bats-assert/load.bash"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
}

strip_ansi() {
  sed 's/\x1b\[[0-9;]*m//g'
}

@test "print_help_row indents the name by exactly two spaces" {
  run bash -c 'source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"; print_help_row 15 "--dry-run" "Show what would run" | sed "s/\x1b\[[0-9;]*m//g"'
  assert_success
  assert_output "  --dry-run      Show what would run"
}

@test "print_help_row keeps the indent flush against the name once coloured" {
  run print_help_row 15 "--dry-run" "Show what would run"
  assert_success
  assert_output --partial "  --dry-run"
}

@test "print_help_row starts the description at the same column for any name length" {
  local short long
  short=$(print_help_row 15 "--list" "one" | strip_ansi)
  long=$(print_help_row 15 "--no-system" "two" | strip_ansi)
  [[ ${#short} -eq ${#long} ]]
}

@test "print_help_row truncates nothing when the name exceeds the field width" {
  run bash -c 'source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"; print_help_row 4 "--create-offline-bundle" "desc" | sed "s/\x1b\[[0-9;]*m//g"'
  assert_success
  assert_output "  --create-offline-bundledesc"
}

@test "print_help_row omits the description when not given" {
  run bash -c 'source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"; print_help_row 0 "go-tools" | sed "s/\x1b\[[0-9;]*m//g"'
  assert_success
  assert_output "  go-tools"
}

@test "print_example_row pads the command and appends the comment" {
  run bash -c 'source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"; print_example_row 20 "./update.sh tools" "# only binaries" | sed "s/\x1b\[[0-9;]*m//g"'
  assert_success
  assert_output "  ./update.sh tools   # only binaries"
}

@test "print_example_row and print_help_row use different colours" {
  local help_row example_row
  help_row=$(print_help_row 10 "name" "desc")
  example_row=$(print_example_row 10 "name" "desc")
  [[ "$help_row" != "$example_row" ]]
}
