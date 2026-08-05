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
  # colors.sh resolves the palette when it is sourced, and bats captures stdout,
  # so without this every constant would be empty and the colour assertions here
  # would compare two identical plain strings. Exported so the `run bash -c`
  # subshells inherit it. The gate itself is tested in colors.bats.
  export FORCE_COLOR=1
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

# ================================================================
# Help screen grammar
# ================================================================
# The grammar buffers rows so the flush can size the column from the longest one
# in the section. These tests pin that no call site ever needs to know a width.

screen() {
  bash -c "source \"$DOTFILES_DIR/configs/common/.local/shell/formatting.sh\"; $1" \
    | sed 's/\x1b\[[0-9;]*m//g'
}

@test "help_row sizes the column from the longest row in its section" {
  run screen '
    help_section "Commands"
    help_row "short" "" "one"
    help_row "a-much-longer-name" "" "two"
    help_end'
  assert_success
  assert_line "  short               one"
  assert_line "  a-much-longer-name  two"
}

@test "help_row counts the args as part of the left column" {
  run screen '
    help_section "Commands"
    help_row "get" "<id>" "one"
    help_row "list" "" "two"
    help_end'
  assert_success
  assert_line "  get <id>  one"
  assert_line "  list      two"
}

@test "help_row re-flows a section when a longer row is added" {
  local narrow wide
  narrow=$(screen 'help_section "Commands"; help_row "a" "" "x"; help_end')
  wide=$(screen 'help_section "Commands"; help_row "a" "" "x"; help_row "aaaaaaaaaa" "" "y"; help_end')
  [[ "$narrow" != "$wide" ]]
}

@test "help_row sizes each section independently" {
  run screen '
    help_section "Commands"
    help_row "a-very-long-command-name" "" "one"
    help_section "Options"
    help_row "-f" "" "two"
    help_end'
  assert_success
  assert_line "  -f  two"
}

@test "help_row keeps the two-space indent flush against the name" {
  run bash -c "source \"$DOTFILES_DIR/configs/common/.local/shell/formatting.sh\"; help_section Commands; help_row update '' 'x'; help_end"
  assert_success
  assert_output --partial "  update"
}

@test "help_section colours by name, not by call site" {
  local commands options examples other
  commands=$(bash -c "source \"$DOTFILES_DIR/configs/common/.local/shell/formatting.sh\"; help_section Commands")
  options=$(bash -c "source \"$DOTFILES_DIR/configs/common/.local/shell/formatting.sh\"; help_section Options")
  examples=$(bash -c "source \"$DOTFILES_DIR/configs/common/.local/shell/formatting.sh\"; help_section Examples")
  other=$(bash -c "source \"$DOTFILES_DIR/configs/common/.local/shell/formatting.sh\"; help_section Collections")
  [[ "$commands" != "$options" ]]
  [[ "$options" != "$examples" ]]
  [[ "$examples" != "$other" ]]
}

@test "help_section colour lookup is case-insensitive" {
  local lower upper
  lower=$(bash -c "source \"$DOTFILES_DIR/configs/common/.local/shell/formatting.sh\"; help_section commands" | sed 's/commands/X/')
  upper=$(bash -c "source \"$DOTFILES_DIR/configs/common/.local/shell/formatting.sh\"; help_section COMMANDS" | sed 's/COMMANDS/X/')
  [[ "$lower" == "$upper" ]]
}

# bats collapses blank lines out of ${lines[@]}, so ordering is asserted against
# the raw output rather than by line index.
@test "help_text flushes pending rows before printing" {
  local out row_line prose_line
  out=$(screen '
    help_section "Commands"
    help_row "first" "" "row"
    help_text "prose after the row"
    help_end')
  row_line=$(grep -n "first  row" <<<"$out" | cut -d: -f1)
  prose_line=$(grep -n "prose after the row" <<<"$out" | cut -d: -f1)
  [[ "$row_line" -lt "$prose_line" ]]
}

@test "help_end flushes the final section" {
  run screen 'help_section "Commands"; help_row "last" "" "row"; help_end'
  assert_success
  assert_output --partial "  last  row"
}

@test "help_end leaves no buffered rows behind" {
  run screen '
    help_section "Commands"
    help_row "once" "" "row"
    help_end
    help_end'
  assert_success
  [[ $(grep -c "once" <<<"$output") -eq 1 ]]
}

@test "help_usage owns the Usage label and aligns continuation lines" {
  run screen 'help_usage "install.sh --machine NAME" "install.sh --create-offline-bundle"'
  assert_success
  assert_line "Usage: install.sh --machine NAME"
  assert_line "       install.sh --create-offline-bundle"
}

@test "help_section emits its own leading blank line" {
  local out
  out=$(screen 'help_section "Commands"; help_end')
  [[ "$out" == $'\n'"Commands"* ]]
}
