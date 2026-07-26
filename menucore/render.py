"""Shared terminal rendering: the menu color palette, section header, help screen grammar.

Colors are raw ANSI so the scripts stay dependency-free. These exact codes match
what ``menu`` (bash) and ``menu-review`` already emit, so the whole family reads
as one tool.

The help grammar mirrors ``formatting.sh`` function for function, so a
``show_help`` reads the same in either language::

    help_header("menu labs", "Small experiments worth revisiting.")
    help_usage("menu labs <verb>")

    help_section("Commands")
    help_row("menu labs list", "", "List every lab")
    help_row("menu labs show", "<id>", "Show one lab")

    help_end()

``help_row`` buffers rather than printing, so the flush can size the description
column from the longest row in the section. No call site passes a width or a
color. Close a screen with ``help_end``, and use ``help_text`` rather than
``print`` for prose between rows so pending rows flush ahead of it.
"""

CYAN = "\033[0;96m"
YELLOW = "\033[0;93m"
GREEN = "\033[0;92m"
RED = "\033[0;91m"
BLUE = "\033[0;94m"
MAGENTA = "\033[0;95m"
WHITE = "\033[0;97m"
COMMAND = "\033[0;36m"
RESET = "\033[0m"
# Matches the default width of formatting.sh's _separator, so a Python screen and
# a bash screen draw the same rule.
BAR = "━" * 50

# The three roles that appear in nearly every CLI get a fixed color, so they
# become learnable across tools. App-specific headings rotate through the rest of
# the palette by position, keeping adjacent sections distinct without any screen
# choosing — a single fallback made an all-app-specific screen render monochrome.
SECTION_COLORS = {
    "commands": CYAN,
    "verbs": CYAN,
    "suites": CYAN,
    "groups": CYAN,
    "phases": CYAN,
    "options": MAGENTA,
    "flags": MAGENTA,
    "arguments": MAGENTA,
    "environment variables": MAGENTA,
    "examples": YELLOW,
}
SECTION_ROTATION = (GREEN, BLUE, WHITE)

pending_rows: list[tuple[str, str, str]] = []
section_title = ""
section_index = 0


def header(title: str) -> None:
    """Print a boxed section header (bar, title, bar, trailing blank line)."""
    print(f"{CYAN}{BAR}{RESET}")
    print(f"{CYAN} {title}{RESET}")
    print(f"{CYAN}{BAR}{RESET}\n")


def section_color(title: str, index: int = 0) -> str:
    return SECTION_COLORS.get(title.lower(), SECTION_ROTATION[index % len(SECTION_ROTATION)])


def help_header(name: str, tagline: str = "") -> None:
    """Open a help screen. Blank line leads, matching formatting.sh's print_header."""
    global section_index
    section_index = 0
    print()
    print(f"{CYAN}{BAR}{RESET}")
    print(f"{CYAN} {name}{RESET}")
    print(f"{CYAN}{BAR}{RESET}")
    if tagline:
        print(tagline)


def help_usage(*lines: str) -> None:
    """Print usage lines. The ``Usage:`` label is ours, so every screen matches."""
    print()
    prefix = "Usage: "
    for line in lines:
        print(f"{COMMAND}{prefix}{line}{RESET}")
        prefix = "       "


def help_section(title: str) -> None:
    global section_title, section_index
    flush_rows()
    section_title = title
    color = section_color(title, section_index)
    section_index += 1
    print()
    print(title)
    print(f"{color}{'─' * (len(title) + 15)}{RESET}")


def help_row(name: str, args: str = "", description: str = "") -> None:
    pending_rows.append((name, args, description))


def help_text(*lines: str) -> None:
    flush_rows()
    for line in lines:
        print(line)


def help_end() -> None:
    global section_title, section_index
    flush_rows()
    section_title = ""
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
    color = COMMAND if section_title.lower() == "examples" else CYAN
    width = max(len(f"{name} {args}".rstrip()) for name, args, _ in pending_rows) + 2

    for name, args, description in pending_rows:
        left = f"{name} {args}".rstrip()
        pad = " " * max(width - len(left), 0)
        trailing = f" {args}" if args else ""
        # A continuation row carries no name, so it gets no color escape either.
        row_color = color if name else ""
        print(f"{row_color}  {name}{RESET}{trailing}{pad}{description}".rstrip())

    pending_rows.clear()
