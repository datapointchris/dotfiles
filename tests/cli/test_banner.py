"""The masthead, asserted on the four things that make it decoration rather than output.

Three of the four are silent failures. Art printed through Rich's markup parser
comes back subtly wrong rather than raising — a row ending in `\\` escapes the
closing tag after it — so the banner still prints and one line of it is corrupt.
A banner on stdout corrupts a `--json` parse. A banner wider than the terminal
wraps, and the overflow reads as two more rows of glyphs rather than as a banner
that did not fit.

The fourth is the gate itself: this must not reach the journal, where the
scheduled `check` writes.
"""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from dotfiles import banner
from dotfiles import output


def captured(monkeypatch: pytest.MonkeyPatch, *, width: int = 200, terminal: bool = True) -> io.StringIO:
    """A stderr console that renders like a terminal into a buffer."""
    written = io.StringIO()
    console = Console(file=written, force_terminal=terminal, no_color=True, highlight=False, width=width)
    monkeypatch.setattr(output, 'err_console', console)
    monkeypatch.setattr(banner, 'err_console', console)
    return written


@pytest.mark.parametrize('art', banner.FONTS, ids=lambda art: art[0][:12])
def test_every_font_survives_rendering_unchanged(art: tuple[str, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    """Figlet art is full of backslashes and square brackets, and both mean
    something to Rich's markup parser. Rendering through `Text` is what keeps the
    art literal, and this is what stops that being tidied back into an f-string."""
    written = captured(monkeypatch)
    monkeypatch.setattr(banner, 'fitting', lambda width: (art,))

    banner.show()

    printed = [line.rstrip() for line in written.getvalue().split('\n')]
    assert [line for line in printed if line] == [line.rstrip() for line in art if line.strip()]


def test_the_banner_writes_nothing_to_stdout(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """stdout is the channel `--json` owns. A banner there is a syntax error in
    the caller's parser rather than the decoration it was meant to be."""
    captured(monkeypatch)

    banner.show()

    assert capsys.readouterr().out == ''


def test_the_banner_is_silent_off_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The scheduled `check` writes into the journal, where six rows of block
    capitals are noise nobody asked for."""
    written = captured(monkeypatch, terminal=False)

    banner.show()

    assert written.getvalue() == ''


def test_the_banner_is_silent_under_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """`-q` is a request for less of exactly this.

    Driven through `LOG_LEVEL` rather than by patching `resolved_console`, so the
    test goes through the same threshold the flag moves. A patched return value
    would have passed with a lowercase level the real code never produces."""
    written = captured(monkeypatch)
    monkeypatch.setenv('LOG_LEVEL', 'warning')

    banner.show()

    assert written.getvalue() == ''


@pytest.mark.parametrize('width', [200, 72, 61, 50, 36, 20])
def test_no_row_is_wider_than_the_terminal(width: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """A wrapped banner is not a narrow banner. The overflow lands under the first
    column and reads as two more rows of glyphs, so a font is chosen to fit and
    the print crops whatever still does not."""
    written = captured(monkeypatch, width=width)

    banner.show()

    assert all(len(line.rstrip()) <= width for line in written.getvalue().split('\n'))


def test_a_narrow_terminal_still_gets_a_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Narrower than every font is a crop, not a blank. Falling through to nothing
    would make the feature vanish on a split pane rather than shrink."""
    written = captured(monkeypatch, width=20)

    banner.show()

    assert written.getvalue().strip()


def test_the_widest_font_fits_a_conventional_terminal() -> None:
    """Eighty columns is the width every terminal opens at, and a banner that
    needs more than that is one most sessions see cropped."""
    assert max(banner.widest(art) for art in banner.FONTS) <= 80


def test_every_ramp_colours_the_shortest_font_end_to_end() -> None:
    """The ramp is spread across the rows rather than indexed by row number, so a
    three-row font shows all three colours instead of losing the last one."""
    shortest = min(banner.FONTS, key=len)

    for ramp in banner.RAMPS:
        used = {ramp[min(position * len(ramp) // len(shortest), len(ramp) - 1)] for position in range(len(shortest))}
        assert used == set(ramp)


def test_the_root_group_carries_the_masthead() -> None:
    """`--help` and a bare `dotfiles` both exit during parsing and never reach the
    root callback, so the banner on those two screens hangs on this class alone."""
    from dotfiles.main import app

    assert app.info.cls is banner.Masthead
