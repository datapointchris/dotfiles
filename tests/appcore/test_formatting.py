"""Tests for appcore.formatting — the house palette and help-screen grammar.

What these hold is column alignment in the presence of color. Every name in a
help row is wrapped in an escape sequence, and an f-string field width counts
those bytes, so the bug this guards against is invisible in source and obvious
on screen: one colored row shoves its description eight columns right of the
others. The same hazard governs `clip`, which must never cut inside an escape.
"""

import importlib
import io
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


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def no_color_env(monkeypatch) -> None:
    for name in ('NO_COLOR', 'FORCE_COLOR', 'TERM'):
        monkeypatch.delenv(name, raising=False)


def test_color_is_on_for_a_terminal(monkeypatch):
    no_color_env(monkeypatch)
    assert formatting.color_enabled(Terminal())


def test_color_is_off_for_a_pipe(monkeypatch):
    """`theme --help > notes.txt` should write text, not escape sequences."""
    no_color_env(monkeypatch)
    assert not formatting.color_enabled(io.StringIO())


def test_no_color_outranks_force_color(monkeypatch):
    """NO_COLOR says the user does not want color; FORCE_COLOR only says the
    terminal detection is wrong. A preference beats a detection override."""
    no_color_env(monkeypatch)
    monkeypatch.setenv('FORCE_COLOR', '1')
    monkeypatch.setenv('NO_COLOR', '1')
    assert not formatting.color_enabled(Terminal())


def test_force_color_beats_a_non_terminal(monkeypatch):
    no_color_env(monkeypatch)
    monkeypatch.setenv('FORCE_COLOR', '1')
    assert formatting.color_enabled(io.StringIO())


def test_dumb_terminal_gets_no_color(monkeypatch):
    no_color_env(monkeypatch)
    monkeypatch.setenv('TERM', 'dumb')
    assert not formatting.color_enabled(Terminal())


def test_a_closed_stream_is_not_a_terminal(monkeypatch):
    """isatty raises on a closed stream, and a crash in the palette would take
    down a tool that was only trying to print."""
    no_color_env(monkeypatch)
    stream = io.StringIO()
    stream.close()
    assert not formatting.color_enabled(stream)


def reloaded_without_color(monkeypatch):
    """appcore resolves the palette at import, so the disabled palette only
    exists after a reload. Callers must reload again on the way out."""
    no_color_env(monkeypatch)
    monkeypatch.setenv('NO_COLOR', '1')
    return importlib.reload(formatting)


def restore_color(monkeypatch):
    monkeypatch.undo()
    importlib.reload(formatting)


def test_the_palette_itself_blanks_out(monkeypatch):
    """Every app in apps/ interpolates these constants directly —
    print(f'{CYAN}{title}{RESET}') — so the gate only reaches those call sites
    if it reaches the constants."""
    plain_module = reloaded_without_color(monkeypatch)
    try:
        assert plain_module.CYAN == ''
        assert plain_module.RESET == ''
        assert plain_module.BAR, 'the rule is content, not color, and must survive'
    finally:
        restore_color(monkeypatch)


def test_rows_still_align_when_color_is_off(monkeypatch, capsys):
    """The padding is measured on uncolored text, so removing color must not
    move a single column."""
    plain_module = reloaded_without_color(monkeypatch)
    try:
        plain_module.help_section('Commands')
        plain_module.help_row('short', '', 'first')
        plain_module.help_row('much-longer-name', '', 'second')
        plain_module.help_end()

        out = capsys.readouterr().out
        rows = [line for line in out.splitlines() if 'first' in line or 'second' in line]
        assert '\033' not in out
        assert rows[0].index('first') == rows[1].index('second')
    finally:
        restore_color(monkeypatch)
