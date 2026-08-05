#!/usr/bin/env bats
#
# Tests for the help-screen functions in formatting.sh
#
# These carry the alignment contract every CLI help screen depends on: the
# colour escapes must sit outside the padded field, and the two-space indent
# must stay flush against the name so the CLI help tests can grep for it.

setup() {
  load "${BATS_TEST_FILENAME%/tests/*}/tests/helpers/bats-libs"

  export DOTFILES_DIR="${BATS_TEST_DIRNAME}/../.."
  # colors.sh resolves the palette when it is sourced, and bats captures stdout,
  # so without this every constant would be empty and the colour assertions here
  # would compare two identical plain strings. Exported so the `run bash -c`
  # subshells inherit it. The gate itself is tested in colors.bats.
  export FORCE_COLOR=1
  export FORMATTING="$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
  source "$DOTFILES_DIR/configs/common/.local/shell/formatting.sh"
}

strip_ansi() {
  sed 's/\x1b\[[0-9;]*m//g'
}

# Runs help-screen code in a fresh shell and strips the escapes, which is how
# the alignment is asserted on the text alone.
screen() {
  bash -c "source \"$FORMATTING\"; $1" | strip_ansi
}

@test "print_help_row: two-space indent, fixed description column, no truncation" {
  # The indent and the column are what every CLI help test greps for; the
  # escapes have to sit outside the padded field or the padding shifts.
  run screen 'print_help_row 15 "--dry-run" "Show what would run"'
  assert_success
  assert_output "  --dry-run      Show what would run"

  run print_help_row 15 "--dry-run" "Show what would run"
  assert_output --partial "  --dry-run"

  # Same description column for any name shorter than the field.
  local short long
  short=$(print_help_row 15 "--list" "one" | strip_ansi)
  long=$(print_help_row 15 "--no-system" "two" | strip_ansi)
  assert_equal "${#short}" "${#long}"

  # A name past the field width pushes the description rather than being cut.
  run screen 'print_help_row 4 "--create-offline-bundle" "desc"'
  assert_output "  --create-offline-bundledesc"

  run screen 'print_help_row 0 "go-tools"'
  assert_output "  go-tools"
}

@test "print_example_row pads the command, and is coloured unlike a help row" {
  run screen 'print_example_row 20 "./update.sh tools" "# only binaries"'
  assert_success
  assert_output "  ./update.sh tools   # only binaries"

  local help_row example_row
  help_row=$(print_help_row 10 "name" "desc")
  example_row=$(print_example_row 10 "name" "desc")
  refute [ "$help_row" = "$example_row" ]
}

# ================================================================
# Help screen grammar
# ================================================================
# The grammar buffers rows so the flush can size the column from the longest one
# in the section. These pin that no call site ever needs to know a width.

@test "help_row sizes each section's column from its own longest row" {
  run screen '
    help_section "Commands"
    help_row "short" "" "one"
    help_row "a-much-longer-name" "" "two"
    help_end'
  assert_success
  assert_line "  short               one"
  assert_line "  a-much-longer-name  two"

  # Args are part of the left column, not the description.
  run screen '
    help_section "Commands"
    help_row "get" "<id>" "one"
    help_row "list" "" "two"
    help_end'
  assert_line "  get <id>  one"
  assert_line "  list      two"

  # A second section sizes itself, rather than inheriting the first's width.
  run screen '
    help_section "Commands"
    help_row "a-very-long-command-name" "" "one"
    help_section "Options"
    help_row "-f" "" "two"
    help_end'
  assert_line "  -f  two"

  # Adding a longer row re-flows the section it lands in.
  local narrow wide
  narrow=$(screen 'help_section "Commands"; help_row "a" "" "x"; help_end')
  wide=$(screen 'help_section "Commands"; help_row "a" "" "x"; help_row "aaaaaaaaaa" "" "y"; help_end')
  refute [ "$narrow" = "$wide" ]

  run screen 'help_section Commands; help_row update "" "x"; help_end'
  assert_output --partial "  update"
}

@test "help_section colours by name, case-insensitively, after a blank line" {
  local commands options examples other
  commands=$(screen 'help_section Commands')
  options=$(screen 'help_section Options')
  examples=$(screen 'help_section Examples')
  other=$(screen 'help_section Collections')

  # Colour is a property of the section name, so a call site cannot get the
  # wrong one by being the second Options block on the screen.
  refute [ "$commands" = "$options" ]
  refute [ "$options" = "$examples" ]
  refute [ "$examples" = "$other" ]

  local lower upper
  lower=$(bash -c "source \"$FORMATTING\"; help_section commands" | sed 's/commands/X/')
  upper=$(bash -c "source \"$FORMATTING\"; help_section COMMANDS" | sed 's/COMMANDS/X/')
  assert_equal "$lower" "$upper"

  local out
  out=$(screen 'help_section "Commands"; help_end')
  [[ "$out" == $'\n'"Commands"* ]]
}

@test "the buffer flushes before prose, at the end, and only once" {
  # bats collapses blank lines out of ${lines[@]}, so ordering is asserted
  # against the raw output rather than by line index.
  local out row_line prose_line
  out=$(screen '
    help_section "Commands"
    help_row "first" "" "row"
    help_text "prose after the row"
    help_end')
  row_line=$(grep -n "first  row" <<<"$out" | cut -d: -f1)
  prose_line=$(grep -n "prose after the row" <<<"$out" | cut -d: -f1)
  assert [ "$row_line" -lt "$prose_line" ]

  run screen 'help_section "Commands"; help_row "last" "" "row"; help_end'
  assert_success
  assert_output --partial "  last  row"

  # A second help_end must not reprint what the first one flushed.
  run screen '
    help_section "Commands"
    help_row "once" "" "row"
    help_end
    help_end'
  assert_equal "$(grep -c "once" <<<"$output")" 1
}

@test "help_usage owns the Usage label and aligns continuation lines" {
  run screen 'help_usage "install.sh --machine NAME" "install.sh --create-offline-bundle"'
  assert_success
  assert_line "Usage: install.sh --machine NAME"
  assert_line "       install.sh --create-offline-bundle"
}
