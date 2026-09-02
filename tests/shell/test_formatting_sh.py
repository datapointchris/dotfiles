"""formatting.sh — the status rows and the help-screen grammar.

Both halves survive the Python conversion because the surviving consumers are
`apps/`: `notes`, `packup` and `_aws-profiles` build their whole help screen out
of this grammar, and the status rows are what every app prints. The
CLI's own help is Typer's and is pinned separately by the conformance suite.

The alignment is asserted on the text with the escapes stripped, because the
contract is that the escapes sit *outside* the padded field — printf counts them
toward a field width, so a color inside the pad shifts the column.
"""

from __future__ import annotations

import pytest
from shells import source

LIBRARY = 'formatting.sh'


def screen(snippet: str) -> str:
    """A help screen with color forced on and then stripped back off.

    Forced on because the padding is only interesting when there are escapes to
    misplace: with color off the two spellings of the bug produce identical
    text.
    """
    return source(LIBRARY, snippet, FORCE_COLOR='1').plain


@pytest.mark.parametrize(
    ('function', 'icon'),
    [('print_success', '✓'), ('print_error', '✗'), ('print_warning', '▲'), ('print_info', '●')],
)
def test_a_status_row_carries_its_icon_and_degrades_to_plain_text(function: str, icon: str) -> None:
    """These had no test at all under bats — `windows-shell-sync.bats` only ever
    asserted `print_success` was *defined*."""
    colored = source(LIBRARY, f'{function} "a message"', FORCE_COLOR='1')
    plain = source(LIBRARY, f'{function} "a message"')

    assert plain.stdout == f'  {icon} a message\n'
    assert '\x1b[' in colored.stdout
    assert colored.plain == plain.stdout


def test_a_status_row_goes_to_stdout_where_its_caller_asked_for_it() -> None:
    """The split against logging.sh, which is always stderr: a heading or a status
    row is output the call site asked for, not narration."""
    result = source(LIBRARY, 'print_success "done"')

    assert result.stderr == ''
    assert result.stdout != ''


def test_print_help_row_indents_by_two_and_holds_the_description_column() -> None:
    assert screen('print_help_row 15 "--dry-run" "Show what would run"') == '  --dry-run      Show what would run\n'

    short = screen('print_help_row 15 "--list" "one"')
    long = screen('print_help_row 15 "--no-system" "two"')
    assert len(short) == len(long)


def test_a_name_past_the_field_width_pushes_the_description_rather_than_being_cut() -> None:
    assert screen('print_help_row 4 "--create-offline-bundle" "desc"') == '  --create-offline-bundledesc\n'
    assert screen('print_help_row 0 "go-tools"') == '  go-tools\n'


def test_an_example_row_is_colored_differently_from_a_help_row() -> None:
    """An example is a command you would type, so it reads in the command color
    rather than the name color a listing uses."""
    assert screen('print_example_row 20 "./update.sh tools" "# only binaries"') == '  ./update.sh tools   # only binaries\n'

    help_row = source(LIBRARY, 'print_help_row 10 "name" "desc"', FORCE_COLOR='1').stdout
    example_row = source(LIBRARY, 'print_example_row 10 "name" "desc"', FORCE_COLOR='1').stdout
    assert help_row != example_row


def test_a_section_sizes_its_column_from_its_own_longest_row() -> None:
    """No call site types a width. `help_row` buffers so the flush can measure."""
    rendered = screen('help_section "Commands"; help_row "short" "" "one"; help_row "a-much-longer-name" "" "two"; help_end')

    assert '  short               one' in rendered
    assert '  a-much-longer-name  two' in rendered


def test_args_are_part_of_the_left_column_not_the_description() -> None:
    rendered = screen('help_section "Commands"; help_row "get" "<id>" "one"; help_row "list" "" "two"; help_end')

    assert '  get <id>  one' in rendered
    assert '  list      two' in rendered


def test_a_second_section_sizes_itself_rather_than_inheriting_the_first() -> None:
    rendered = screen(
        'help_section "Commands"; help_row "a-very-long-command-name" "" "one"; help_section "Options"; help_row "-f" "" "two"; help_end'
    )

    assert '  -f  two' in rendered


def test_a_longer_row_reflows_the_section_it_lands_in() -> None:
    narrow = screen('help_section "Commands"; help_row "a" "" "x"; help_end')
    wide = screen('help_section "Commands"; help_row "a" "" "x"; help_row "aaaaaaaaaa" "" "y"; help_end')

    assert narrow != wide


@pytest.mark.parametrize('other', ['Options', 'Examples', 'Collections'])
def test_a_section_is_colored_by_its_name_not_its_position(other: str) -> None:
    """So a screen cannot get the wrong color by being the second Options block."""
    assert screen('help_section Commands') != screen(f'help_section {other}')


def test_the_section_color_is_case_insensitive() -> None:
    lower = screen('help_section commands').replace('commands', 'X')
    upper = screen('help_section COMMANDS').replace('COMMANDS', 'X')

    assert lower == upper


def test_a_section_opens_on_a_blank_line() -> None:
    assert screen('help_section "Commands"; help_end').startswith('\nCommands')


def test_pending_rows_flush_ahead_of_prose() -> None:
    """`help_text` rather than a bare echo, so a buffered row cannot land after
    the paragraph that was meant to follow it."""
    rendered = screen('help_section "Commands"; help_row "first" "" "row"; help_text "prose after the row"; help_end')
    lines = rendered.splitlines()

    assert lines.index('  first  row') < lines.index('prose after the row')


def test_help_end_flushes_and_does_not_reprint_what_it_already_flushed() -> None:
    rendered = screen('help_section "Commands"; help_row "once" "" "row"; help_end; help_end')

    assert rendered.count('once') == 1


def test_help_usage_owns_the_label_and_aligns_continuation_lines() -> None:
    """The library prints "Usage: " so every screen labels it identically."""
    rendered = screen('help_usage "install.sh --machine NAME" "install.sh --machine NAME --offline"')

    assert 'Usage: install.sh --machine NAME\n' in rendered
    assert '       install.sh --machine NAME --offline\n' in rendered
