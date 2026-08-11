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
    from dotfiles.resources import Change

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

VERDICT_COLOURS = {'converged': 'green', 'drift': 'yellow', 'issue': 'red'}

CHANGE_COLOURS = {'matched': 'green', 'missing': 'yellow', 'stale': 'yellow', 'undeclared': 'blue', 'unknown': 'magenta'}


def emit_json(data: Any) -> None:
    """Write machine-readable output to stdout, bypassing Rich entirely.

    `print`, not `console.print`: Rich wraps at the terminal width and would
    insert newlines into a long JSON string, and it interprets square brackets
    as markup — both of which corrupt the document for the caller parsing it.
    """
    print(json.dumps(data, indent=2, default=str))


def emit_text(text: str) -> None:
    """Write a file's contents to stdout, byte for byte.

    `print`, not `console.print`, for the same reason `emit_json` uses it: Rich
    wraps at the terminal width, and a wrapped `~/.env` line or manifest key is a
    different file from the one that was asked for.
    """
    print(text, end='')


def render_result(result: ResourceResult) -> None:
    """One resource's verdict, as a row.

    Keyed on the verdict's string value rather than the enum, so this module
    stays below `reconcile` and does not import it at runtime — presentation
    should not be a reason for the logic to be loaded.
    """
    colour = VERDICT_COLOURS[str(result.verdict)]
    console.print(f'[{colour}]{result.verdict:<9}[/] [bold]{result.address:<11}[/] {result.detail}')


def render_change(change: Change) -> None:
    """One item's verdict, on stderr — and, where there is one, the next step.

    Below a composite `check`, these are the evidence for the row that follows,
    not the answer a caller parses — which is `--json`. Keyed on the verdict's
    string value for the same reason `render_result` is: presentation should not
    be a reason to import the logic.

    `advice` prints as its own line rather than appended to `detail`, aligned
    under it: the two answer different questions — what is wrong, and what to do
    about it — and a reader scanning a screen of rows for the instruction wants
    it in one column, not folded into a sentence of varying length.
    """
    colour = CHANGE_COLOURS[str(change.verdict)]
    observed = f' (is {change.observed!r})' if change.observed else ''
    err_console.print(f'  [{colour}]{change.verdict:<11}[/] {change.item:<28} {change.detail}{observed}')
    if change.advice:
        err_console.print(f'  {"":<11} {"":<28} [blue]→[/] {change.advice}')


def render_finding(section: str, message: str) -> None:
    """One declaration finding, on stderr, in the same column as a change.

    A finding is evidence for the `machines` row the way a Change is evidence for
    a resource's, so it reads as one list rather than two — and it goes to stderr
    for the reason every diagnostic here does: `--json` is what a caller parses.
    """
    err_console.print(f'  [red]{"invalid":<11}[/] {section:<28} {message}')


def heading(text: str) -> None:
    """Announce an address. On stderr, because a banner is progress, not data."""
    err_console.print()
    err_console.print(f'[bold blue]{text}[/]')


def error(message: str) -> None:
    err_console.print(f'[red]✗[/] {message}')


def success(message: str) -> None:
    err_console.print(f'[green]✓[/] {message}')


def warn(message: str) -> None:
    err_console.print(f'[yellow]![/] {message}')


def hint(message: str) -> None:
    err_console.print(f'[blue]→[/] {message}')
