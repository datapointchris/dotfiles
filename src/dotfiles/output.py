"""The console pair every command renders through.

Two consoles, not one, and the split is the machine contract rather than taste:
stdout carries data a caller parses — `--json`, a printed path, an id — and
nothing else; stderr carries logs, progress, warnings and errors. One stray
diagnostic on stdout turns a `--json` parse into a syntax error rather than the
warning it actually was.

Importing this module is deliberately free of side effects beyond constructing
the two consoles, because `main.py` imports it before deciding whether the run
is a `--json` one.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from rich.console import Console

if TYPE_CHECKING:
    from dotfiles.reconcile import ResourceResult

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

VERDICT_COLOURS = {'converged': 'green', 'drift': 'yellow', 'issue': 'red', 'pending': 'blue'}


def emit_json(data: Any) -> None:
    """Write machine-readable output to stdout, bypassing Rich entirely.

    `print`, not `console.print`: Rich wraps at the terminal width and would
    insert newlines into a long JSON string, and it interprets square brackets
    as markup — both of which corrupt the document for the caller parsing it.
    """
    print(json.dumps(data, indent=2, default=str))


def render_result(result: ResourceResult) -> None:
    """One resource's verdict, as a row.

    Keyed on the verdict's string value rather than the enum, so this module
    stays below `reconcile` and does not import it at runtime — presentation
    should not be a reason for the logic to be loaded.
    """
    colour = VERDICT_COLOURS[str(result.verdict)]
    console.print(f'[{colour}]{result.verdict:<9}[/] [bold]{result.address:<11}[/] {result.detail}')


def error(message: str) -> None:
    err_console.print(f'[red]✗[/] {message}')


def success(message: str) -> None:
    err_console.print(f'[green]✓[/] {message}')


def warn(message: str) -> None:
    err_console.print(f'[yellow]![/] {message}')


def hint(message: str) -> None:
    err_console.print(f'[blue]→[/] {message}')
