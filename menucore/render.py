"""Shared terminal rendering: the menu color palette and section header.

Colors are raw ANSI so the scripts stay dependency-free. These exact codes match
what ``menu`` (bash) and ``menu-review`` already emit, so the whole family reads
as one tool.
"""

CYAN = "\033[0;96m"
YELLOW = "\033[0;93m"
GREEN = "\033[0;92m"
RED = "\033[0;91m"
DIM = "\033[2m"
RESET = "\033[0m"
BAR = "━" * 48


def header(title: str) -> None:
    """Print a boxed section header (bar, title, bar, trailing blank line)."""
    print(f"{CYAN}{BAR}{RESET}")
    print(f"{CYAN} {title}{RESET}")
    print(f"{CYAN}{BAR}{RESET}\n")
