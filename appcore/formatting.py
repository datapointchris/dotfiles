"""Terminal rendering for the Python apps: color palette, section header, help grammar.

The bash apps share ``~/.local/shell/formatting.sh``; this is its counterpart, and
the parallel is the point. Colors are raw ANSI so any app can import this without
declaring a dependency, and the codes match what ``formatting.sh`` emits, so a
Python screen and a bash screen sitting next to each other on PATH are
indistinguishable.

The help grammar mirrors ``formatting.sh`` function for function, so a
``show_help`` reads the same in either language::

    help_header('menu labs', 'Small experiments worth revisiting.')
    help_usage('menu labs <verb>')

    help_section('Commands')
    help_row('menu labs list', '', 'List every lab')
    help_row('menu labs show', '<id>', 'Show one lab')

    help_end()

``help_row`` buffers rather than printing, so the flush can size the description
column from the longest row in the section. No call site passes a width or a
color. Close a screen with ``help_end``, and use ``help_text`` rather than
``print`` for prose between rows so pending rows flush ahead of it.

There is deliberately no ``dim`` — see ~/dev/standards/cli-design.md, which rules
it out for being unreadable against half the terminal themes in use.

The palette resolves to empty strings when nothing will render them, so
``theme --help > notes.txt`` writes text rather than escape sequences. Every
constant is consumed by direct f-string interpolation across ``apps/`` —
``print(f'{CYAN}{title}{RESET}')`` — so blanking the constants is the only fix
that reaches those call sites without rewriting all of them. It also means the
padding arithmetic is unaffected either way: widths are measured on the
uncolored text already.
"""

import os
import shutil
import sys


def color_enabled(stream=None) -> bool:
    """Whether escape sequences will be seen by anything that can render them.

    ``NO_COLOR`` is the user saying they do not want colour (no-color.org) and
    wins outright. ``FORCE_COLOR`` answers a different question — "is this a
    terminal" — for a caller that knows the detection is wrong: a CI log that
    renders escapes, a pager invoked with ``-R``, a test that needs the codes in
    order to assert on them. Preference beats detection, so NO_COLOR is checked
    first.
    """
    if os.environ.get('NO_COLOR'):
        return False
    if os.environ.get('FORCE_COLOR'):
        return True
    if os.environ.get('TERM') == 'dumb':
        return False
    stream = sys.stdout if stream is None else stream
    try:
        return stream.isatty()
    except (AttributeError, ValueError):  # not a stream, or already closed
        return False


COLOR = color_enabled()


def _code(sequence: str) -> str:
    return sequence if COLOR else ''


CYAN = _code('\033[0;96m')
YELLOW = _code('\033[0;93m')
GREEN = _code('\033[0;92m')
RED = _code('\033[0;91m')
BLUE = _code('\033[0;94m')
MAGENTA = _code('\033[0;95m')
WHITE = _code('\033[0;97m')
COMMAND = _code('\033[0;36m')
BOLD = _code('\033[1m')
RESET = _code('\033[0m')
# Matches the default width of formatting.sh's _separator, so a Python screen and
# a bash screen draw the same rule.
BAR = '━' * 50

# The three roles that appear in nearly every CLI get a fixed color, so they
# become learnable across tools. App-specific headings rotate through the rest of
# the palette by position, keeping adjacent sections distinct without any screen
# choosing — a single fallback made an all-app-specific screen render monochrome.
SECTION_COLORS = {
    'commands': CYAN,
    'verbs': CYAN,
    'suites': CYAN,
    'groups': CYAN,
    'phases': CYAN,
    'options': MAGENTA,
    'flags': MAGENTA,
    'arguments': MAGENTA,
    'environment variables': MAGENTA,
    'examples': YELLOW,
}
SECTION_ROTATION = (GREEN, BLUE, WHITE)

pending_rows: list[tuple[str, str, str]] = []
section_title = ''
section_index = 0


def paint(color: str, text: str) -> str:
    return f'{color}{text}{RESET}'


def cyan(text: str) -> str:
    return paint(CYAN, text)


def green(text: str) -> str:
    return paint(GREEN, text)


def yellow(text: str) -> str:
    return paint(YELLOW, text)


def red(text: str) -> str:
    return paint(RED, text)


def blue(text: str) -> str:
    return paint(BLUE, text)


def magenta(text: str) -> str:
    return paint(MAGENTA, text)


def bold(text: str) -> str:
    return paint(BOLD, text)


def header(title: str) -> None:
    """Print a boxed section header (bar, title, bar, trailing blank line)."""
    print(f'{CYAN}{BAR}{RESET}')
    print(f'{CYAN} {title}{RESET}')
    print(f'{CYAN}{BAR}{RESET}\n')


def clip(text: str, used: int) -> str:
    """``text`` shortened to fit the terminal alongside ``used`` other columns.

    Callers pass the uncolored surrounding text's length and color the result
    afterwards, so a clip can never land inside an escape sequence and leak a
    raw code onto the screen. Every character this family clips around (``↳``,
    ``·``, ``…``) is one column wide, so ``len`` is the display width.
    """
    room = shutil.get_terminal_size().columns - used
    if len(text) <= room or room < 2:
        return text
    return text[: room - 1] + '…'


def section_color(title: str, index: int = 0) -> str:
    return SECTION_COLORS.get(title.lower(), SECTION_ROTATION[index % len(SECTION_ROTATION)])


def help_header(name: str, tagline: str = '') -> None:
    """Open a help screen. Blank line leads, matching formatting.sh's print_header."""
    global section_index
    section_index = 0
    print()
    print(f'{CYAN}{BAR}{RESET}')
    print(f'{CYAN} {name}{RESET}')
    print(f'{CYAN}{BAR}{RESET}')
    if tagline:
        print(tagline)


def help_usage(*lines: str) -> None:
    """Print usage lines. The ``Usage:`` label is ours, so every screen matches."""
    print()
    prefix = 'Usage: '
    for line in lines:
        print(f'{COMMAND}{prefix}{line}{RESET}')
        prefix = '       '


def help_section(title: str) -> None:
    global section_title, section_index
    flush_rows()
    section_title = title
    color = section_color(title, section_index)
    section_index += 1
    print()
    print(title)
    print(f'{color}{"─" * (len(title) + 15)}{RESET}')


def help_row(name: str, args: str = '', description: str = '') -> None:
    pending_rows.append((name, args, description))


def help_text(*lines: str) -> None:
    flush_rows()
    for line in lines:
        print(line)


def help_end() -> None:
    global section_title, section_index
    flush_rows()
    section_title = ''
    section_index = 0
    print()


def flush_rows() -> None:
    """Print the buffered rows, sizing the column from the longest left side.

    The width is measured on the uncolored text and the color is applied after,
    because an f-string field width counts the escape bytes and would push every
    description right by the length of the escape.
    """
    if not pending_rows:
        return

    # An example is a command you would type, so it reads in the command color
    # rather than the name color used for a listing.
    color = COMMAND if section_title.lower() == 'examples' else CYAN
    width = max(len(f'{name} {args}'.rstrip()) for name, args, _ in pending_rows) + 2

    for name, args, description in pending_rows:
        left = f'{name} {args}'.rstrip()
        pad = ' ' * max(width - len(left), 0)
        trailing = f' {args}' if args else ''
        # A continuation row carries no name, so it gets no color escape either.
        row_color = color if name else ''
        print(f'{row_color}  {name}{RESET}{trailing}{pad}{description}'.rstrip())

    pending_rows.clear()
