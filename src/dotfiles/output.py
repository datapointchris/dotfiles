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

EVIDENCE_INDENT = '  '
VERDICT_COLUMN = 11
SUBJECT_COLUMN = 28
"""The two columns every evidence row shares — a change's, a finding's, and the
advice line that hangs under both.

Named because they are the property, not a detail of one f-string. A finding
reading as part of the same list as the changes above it is what makes the output
one list rather than two, and that only holds while all three agree. Repeated as
literals they had already been copied four times, and nothing would have failed if
one of the copies drifted."""


def showing_evidence() -> bool:
    """Whether the per-item rows below a verdict are worth printing.

    Read from the console threshold rather than held as a second switch, so `-q`
    and `LOG_LEVEL=warning` cannot disagree about how much this run says. The
    rows are not log records — they go through Rich — so without this `-q` moved
    the log threshold and changed nothing a reader could see.

    The verdict itself is never suppressed. It goes to stdout because it is the
    answer to the question asked, and a `check` that printed nothing at all would
    be reporting by exit code alone.
    """
    import logging as stdlib

    from dotfiles import logging

    level, _ = logging.resolved_console()
    return stdlib.getLevelNamesMapping().get(level, stdlib.INFO) <= stdlib.INFO


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


def tallies(result: ResourceResult) -> str:
    """The counts behind a verdict, where there are any.

    `ResourceResult` has carried these four since it was written and no row has
    ever shown them, so "converged" meant whatever the reader assumed it meant.
    Each answers a question the verdict alone leaves open: how much `apply` would
    change, how much it cannot, how much nothing could measure either way, and
    how much of the work will ask for a password.

    Only non-zero counts appear. A converged resource with four zeroes would
    otherwise print a row of noughts on every line of a healthy machine, which is
    the "pages of output" this is trying not to become.

    `attention` is dropped on an `issue` row for the same reason: that verdict is
    *made of* the items needing attention and its detail already names them, so
    the count restates the sentence beside it.

    The pairing worth keeping is a converged row with a non-zero `pending`, which
    looks contradictory and is not. `check` answers what is *wrong*, and a
    declared package that is merely absent is drift the `apply` will fix. Before
    this the two senses of "converged" were indistinguishable.
    """
    counts = (
        (result.pending, 'pending'),
        (0 if str(result.verdict) == 'issue' else result.attention, 'need attention'),
        (result.unmeasured, 'unmeasured'),
        (result.privileged, 'need a password'),
    )
    shown = [f'{count} {label}' for count, label in counts if count]
    return f'  ·  {", ".join(shown)}' if shown else ''


def render_result(result: ResourceResult) -> None:
    """One resource's verdict, as a row.

    Keyed on the verdict's string value rather than the enum, so this module
    stays below `reconcile` and does not import it at runtime — presentation
    should not be a reason for the logic to be loaded.
    """
    colour = VERDICT_COLOURS[str(result.verdict)]
    console.print(f'[{colour}]{result.verdict:<9}[/] [bold]{result.address:<11}[/] {result.detail}{tallies(result)}')


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
    if not showing_evidence():
        return
    colour = CHANGE_COLOURS[str(change.verdict)]
    observed = f' (is {change.observed!r})' if change.observed else ''
    err_console.print(
        f'{EVIDENCE_INDENT}[{colour}]{change.verdict:<{VERDICT_COLUMN}}[/] {change.item:<{SUBJECT_COLUMN}} {change.detail}{observed}'
    )
    # One row per line, because advice is now assembled from what a diagnosis
    # measured — the owning package, then the command that removes it — and a
    # reader scanning for the command wants it on a line of its own rather than
    # inside a sentence.
    for line in change.advice.splitlines():
        err_console.print(f'{EVIDENCE_INDENT}{"":<{VERDICT_COLUMN}} {"":<{SUBJECT_COLUMN}} [blue]→[/] {line}')


def render_finding(section: str, message: str) -> None:
    """One declaration finding, on stderr, in the same column as a change.

    A finding is evidence for the `machines` row the way a Change is evidence for
    a resource's, so it reads as one list rather than two — and it goes to stderr
    for the reason every diagnostic here does: `--json` is what a caller parses.
    """
    if not showing_evidence():
        return
    err_console.print(f'{EVIDENCE_INDENT}[red]{"invalid":<{VERDICT_COLUMN}}[/] {section:<{SUBJECT_COLUMN}} {message}')


def heading(text: str) -> None:
    """Announce an address. On stderr, because a banner is progress, not data."""
    if not showing_evidence():
        return
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
