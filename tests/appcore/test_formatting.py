"""Tests for appcore.formatting — the house palette and help-screen grammar.

What these hold is column alignment in the presence of color. Every name in a
help row is wrapped in an escape sequence, and an f-string field width counts
those bytes, so the bug this guards against is invisible in source and obvious
on screen: one colored row shoves its description eight columns right of the
others. The same hazard governs `clip`, which must never cut inside an escape.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from appcore import formatting

ANSI = re.compile(r'\033\[[0-9;]*m')


def plain(captured: str) -> str:
    return ANSI.sub('', captured).rstrip('\n')


def reset_help_state() -> None:
    """The grammar keeps module-level section state, so a screen left half-open by
    one test would color the next one's first section wrong."""
    formatting.pending_rows.clear()
    formatting.section_title = ''
    formatting.section_index = 0


def test_clip_leaves_text_that_fits(monkeypatch):
    monkeypatch.setenv('COLUMNS', '80')
    assert formatting.clip('short', 10) == 'short'


def test_clip_shortens_to_the_room_that_is_left(monkeypatch):
    monkeypatch.setenv('COLUMNS', '40')
    clipped = formatting.clip('x' * 100, 10)
    assert len(clipped) == 30
    assert clipped.endswith('…')


def test_clip_gives_up_rather_than_emit_a_bare_ellipsis(monkeypatch):
    """With no room to say anything, truncating to '…' loses more than it saves."""
    monkeypatch.setenv('COLUMNS', '10')
    assert formatting.clip('hello', 9) == 'hello'


def test_help_rows_align_their_descriptions(capsys):
    reset_help_state()
    formatting.help_section('Commands')
    formatting.help_row('short', '', 'first')
    formatting.help_row('a-much-longer-name', '<arg>', 'second')
    formatting.help_end()

    rows = [plain(line) for line in capsys.readouterr().out.splitlines() if 'first' in line or 'second' in line]
    assert rows[0].index('first') == rows[1].index('second'), 'color escapes must not count toward the width'


def test_help_row_args_share_the_name_column(capsys):
    """The args are uncolored but sit inside the padded column, so a row with args
    must not push its description past a row without them."""
    reset_help_state()
    formatting.help_section('Commands')
    formatting.help_row('name', '<arg>', 'described')
    formatting.help_end()

    row = plain([line for line in capsys.readouterr().out.splitlines() if 'described' in line][0])
    assert row.startswith('  name <arg>')
    assert row.endswith('described')


def test_help_row_without_a_description_has_no_trailing_padding(capsys):
    reset_help_state()
    formatting.help_section('Commands')
    formatting.help_row('bare')
    formatting.help_end()

    row = [line for line in capsys.readouterr().out.splitlines() if 'bare' in line][0]
    assert plain(row) == '  bare'


def test_help_text_flushes_pending_rows_first(capsys):
    """Rows buffer until flush, so prose printed between them would otherwise
    appear above rows that were declared before it."""
    reset_help_state()
    formatting.help_section('Commands')
    formatting.help_row('a-row', '', 'described')
    formatting.help_text('  some prose')
    formatting.help_end()

    lines = [plain(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert lines.index('  a-row  described') < lines.index('  some prose')


def test_section_colors_are_fixed_for_the_universal_roles():
    """These three recur in every tool, so they are learnable only if they never
    shift with position."""
    assert formatting.section_color('Commands', 0) == formatting.CYAN
    assert formatting.section_color('Commands', 7) == formatting.CYAN
    assert formatting.section_color('Options', 3) == formatting.MAGENTA
    assert formatting.section_color('Examples', 5) == formatting.YELLOW


def test_section_colors_are_case_insensitive():
    assert formatting.section_color('OPTIONS') == formatting.MAGENTA
    assert formatting.section_color('examples') == formatting.YELLOW


def test_app_specific_sections_rotate_so_neighbours_differ():
    """A single fallback color rendered an all-app-specific screen monochrome."""
    rotated = [formatting.section_color('Whatever', index) for index in range(4)]
    assert rotated[0] != rotated[1] != rotated[2]
    assert rotated[3] == rotated[0], 'the rotation is three long and wraps'


def test_examples_rows_use_the_command_color(capsys):
    """An example is something you would type, so it reads as a command rather
    than as a listing name."""
    reset_help_state()
    formatting.help_section('Examples')
    formatting.help_row('some command', '', 'does a thing')
    formatting.help_end()

    row = [line for line in capsys.readouterr().out.splitlines() if 'does a thing' in line][0]
    assert row.startswith(formatting.COMMAND)


def test_help_end_resets_state_for_the_next_screen(capsys):
    reset_help_state()
    formatting.help_section('Examples')
    formatting.help_row('x', '', 'y')
    formatting.help_end()
    capsys.readouterr()

    formatting.help_section('Commands')
    formatting.help_row('a', '', 'b')
    formatting.help_end()

    row = [line for line in capsys.readouterr().out.splitlines() if 'b' in line][0]
    assert row.startswith(formatting.CYAN), 'the previous screen must not leak its section color'
