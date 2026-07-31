"""Tests for menucore.render's nudge primitives — the one-line-per-item renderers
shared by menu-review and menu-labs.

The bound these hold is the whole point of a nudge: a row that wraps is two rows,
so a clip that is off by a column silently doubles what shell startup prints. The
callers' own tests cover their assembly; these cover the primitive.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from menucore import render

ANSI = re.compile(r'\033\[[0-9;]*m')


def plain(captured: str) -> str:
    return ANSI.sub('', captured).rstrip('\n')


def test_clip_leaves_text_that_fits(monkeypatch):
    monkeypatch.setenv('COLUMNS', '80')
    assert render.clip('short', 10) == 'short'


def test_clip_shortens_to_the_room_that_is_left(monkeypatch):
    monkeypatch.setenv('COLUMNS', '40')
    clipped = render.clip('x' * 100, 10)
    assert len(clipped) == 30
    assert clipped.endswith('…')


def test_clip_gives_up_rather_than_emit_a_bare_ellipsis(monkeypatch):
    """With no room to say anything, truncating to '…' loses more than it saves."""
    monkeypatch.setenv('COLUMNS', '10')
    assert render.clip('hello', 9) == 'hello'


def test_nudge_width_sizes_from_the_longest_name():
    assert render.nudge_width(['a', 'abc', 'ab']) == 5, 'longest name plus a two-column gutter'
    assert render.nudge_width([]) == 2, 'an empty roster is the gutter alone, not a max() error'


def test_nudge_row_fits_the_terminal(monkeypatch, capsys):
    monkeypatch.setenv('COLUMNS', '50')
    render.nudge_row('an-item', 'never done', 'x' * 200, render.nudge_width(['an-item']))

    out = plain(capsys.readouterr().out)
    assert len(out) <= 50
    assert out.startswith('  an-item'), "the name is the row's identity and is never clipped"
    assert out.endswith('…')


def test_nudge_row_colors_do_not_shift_the_columns(monkeypatch, capsys):
    """The escapes must not count toward the width, or every later column slides."""
    monkeypatch.setenv('COLUMNS', '200')
    width = render.nudge_width(['short', 'a-much-longer-name'])
    render.nudge_row('short', 'never done', 'cmd', width)
    render.nudge_row('a-much-longer-name', 'overdue 3d', 'cmd', width)

    first, second = (plain(line) for line in capsys.readouterr().out.splitlines())
    assert first.index('never done') == second.index('overdue 3d')
    assert first.index('↳') == second.index('↳')


def test_nudge_row_without_a_command(monkeypatch, capsys):
    monkeypatch.setenv('COLUMNS', '80')
    render.nudge_row('an-item', 'never done', '', render.nudge_width(['an-item']))

    out = plain(capsys.readouterr().out)
    assert out == '  an-item  never done'
    assert '↳' not in out


def test_nudge_header_is_one_line(capsys):
    render.nudge_header('Review', 6)

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1, 'the boxed three-line header belongs to the browse views'
    assert plain(lines[0]) == 'Review · 6 due'
