"""The masthead the reconcile verbs and the help screen open with.

Decoration, and treated as decoration everywhere it matters: it goes to stderr
because stdout is the channel `--json` owns, it is silent off a terminal because
the scheduled `check` writes into the journal and six rows of block capitals
there are noise, and `-q` removes it with the rest of the evidence.

The art is baked in rather than shelled out to figlet. Nothing declares figlet as
a dependency, a machine mid-bootstrap has not installed it yet, and a banner that
costs a subprocess on every invocation is one that gets turned off.

**Rendered through `rich.text.Text`, never markup.** Figlet art is full of
backslashes and square brackets, and both mean something to Rich's parser: art
ending in `\\` escapes the closing tag that follows it, so `\\__ \\` printed as
`\\__ [/]`. Measured while choosing these fonts, and it is silent — the row is
still a row, just the wrong one.
"""

from __future__ import annotations

import random
from typing import Any

from rich.text import Text

from dotfiles.output import err_console
from dotfiles.output import showing_evidence
from dotfiles.refusal import Boundary

FONTS: tuple[tuple[str, ...], ...] = (
    # ansi_regular — 5 rows x 60 cols
    (
        '██████   ██████  ████████ ███████ ██ ██      ███████ ███████',
        '██   ██ ██    ██    ██    ██      ██ ██      ██      ██',
        '██   ██ ██    ██    ██    █████   ██ ██      █████   ███████',
        '██   ██ ██    ██    ██    ██      ██ ██      ██           ██',
        '██████   ██████     ██    ██      ██ ███████ ███████ ███████',
    ),
    # basic — 6 rows x 66 cols
    (
        'd8888b.  .d88b.  d888888b d88888b d888888b db      d88888b .d8888.',
        "88  `8D .8P  Y8. `~~88~~' 88'       `88'   88      88'     88'  YP",
        '88   88 88    88    88    88ooo      88    88      88ooooo `8bo.',
        '88   88 88    88    88    88~~~      88    88      88~~~~~   `Y8b.',
        "88  .8D `8b  d8'    88    88        .88.   88booo. 88.     db   8D",
        "Y8888D'  `Y88P'     YP    YP      Y888888P Y88888P Y88888P `8888Y'",
    ),
    # cosmic — 6 rows x 70 cols
    (
        ":::::::-.      ...   ::::::::::::.-:::::'::: :::    .,:::::: .::::::.",
        " ;;,   `';, .;;;;;;;.;;;;;;;;'''';;;'''' ;;; ;;;    ;;;;'''';;;`    `",
        " `[[     [[,[[     \\[[,   [[     [[[,,== [[[ [[[     [[cccc '[==/[[[[,",
        '  $$,    $$$$$,     $$$   $$     `$$$"`` $$$ $$\'     $$""""   \'\'\'    $',
        '  888_,o8P\'"888,_ _,88P   88,     888    888o88oo,.__888oo,__88b    dP',
        '  MMMMP"`    "YMMMMMP"    MMM     "MM,   MMM""""YUMMM""""YUMMM"YMmMY"',
    ),
    # cyberlarge — 3 rows x 61 cols
    (
        ' ______   _____  _______ _______ _____        _______ _______',
        ' |     \\ |     |    |    |______   |   |      |______ |______',
        ' |_____/ |_____|    |    |       __|__ |_____ |______ ______|',
    ),
    # js_stick_letters — 3 rows x 35 cols
    (
        ' __   __  ___  ___         ___  __',
        '|  \\ /  \\  |  |__  | |    |__  /__`',
        '|__/ \\__/  |  |    | |___ |___ .__/',
    ),
    # nancyj — 6 rows x 55 cols
    (
        '      dP            dP   .8888b oo dP',
        '      88            88   88   "    88',
        '.d888b88 .d8888b. d8888P 88aaa  dP 88 .d8888b. .d8888b.',
        "88'  `88 88'  `88   88   88     88 88 88ooood8 Y8ooooo.",
        '88.  .88 88.  .88   88   88     88 88 88.  ...       88',
        "`88888P8 `88888P'   dP   dP     dP dP `88888P' `88888P'",
    ),
    # varsity — 6 rows x 51 cols
    (
        '       __         _      ___  _   __',
        "      |  ]       / |_  .' ..](_) [  |",
        "  .--.| |  .--. `| |-'_| |_  __   | | .---.  .--.",
        "/ /'`\\' |/ .'`\\ \\| | '-| |-'[  |  | |/ /__\\\\( (`\\]",
        "| \\__/  || \\__. || |,  | |   | |  | || \\__., `'.'.",
        " '.__.;__]'.__.' \\__/ [___] [___][___]'.__.'[\\__) )",
    ),
)

RAMPS: tuple[tuple[str, ...], ...] = (
    ('blue', 'green', 'yellow'),
    ('yellow', 'green', 'blue'),
    ('blue', 'cyan', 'green'),
)
"""The colour a row takes, top to bottom.

Spread across however many rows the font has rather than one colour per row, so a
three-row font shows all three and a six-row font shows two rows of each. A ramp
indexed by row number would leave the short fonts permanently missing their last
colour.
"""


def widest(art: tuple[str, ...]) -> int:
    return max(len(line) for line in art)


def fitting(width: int) -> tuple[tuple[str, ...], ...]:
    """The fonts this terminal is wide enough for, or the narrowest if none are.

    Rich wraps at the console width, and a wrapped banner is not a narrow banner
    but a broken one — the overflow lands under the first column and reads as two
    more rows of glyphs. Choosing a font that fits is the fix; `no_wrap` on the
    print is the backstop for the terminal narrower than all seven.
    """
    return tuple(art for art in FONTS if widest(art) <= width) or (min(FONTS, key=widest),)


def show() -> None:
    """Print one banner, in a font and a ramp neither of which is yesterday's.

    Random on purpose. It is the whole point of the feature — the machine says
    the same thing every time it is asked, and this is the one line of it that
    does not.
    """
    if not err_console.is_terminal or not showing_evidence():
        return
    art = random.choice(fitting(err_console.width))
    ramp = random.choice(RAMPS)
    # Two above and two below, so the banner sits clear of the shell prompt that
    # precedes it rather than reading as the last line of it.
    err_console.print()
    err_console.print()
    for position, line in enumerate(art):
        style = ramp[min(position * len(ramp) // len(art), len(ramp) - 1)]
        err_console.print(Text(line, style=style), no_wrap=True, overflow='crop')
    err_console.print()
    err_console.print()


class Masthead(Boundary):
    """The root group, with the banner on the screen `--help` prints.

    The reconcile verbs call `show` themselves and this covers the other door.
    Neither `dotfiles --help` nor a bare `dotfiles` reaches the root callback:
    click's eager help option exits during parsing, and `no_args_is_help` prints
    and exits before any callback runs. A banner installed on the callback was
    therefore absent from the two screens most likely to be looked at.

    `ctx` and `formatter` are untyped for the reason `Boundary.invoke`'s are —
    their types are whichever click the installed typer carries, and naming
    either is the dependency this package was changed to stop having.
    """

    def format_help(self, ctx: Any, formatter: Any) -> None:
        show()
        super().format_help(ctx, formatter)
