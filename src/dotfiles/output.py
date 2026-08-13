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
from rich.control import Control
from rich.segment import ControlType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dotfiles.reconcile import Lens
    from dotfiles.reconcile import ResourceResult
    from dotfiles.resources import Change
    from dotfiles.resources import Examined

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

VERDICT_COLOURS = {'converged': 'green', 'drift': 'yellow', 'issue': 'red'}

CHANGE_COLOURS = {'matched': 'green', 'missing': 'yellow', 'stale': 'yellow', 'undeclared': 'blue', 'unknown': 'magenta'}

MATCHED = 'matched'
"""The label an `Examined` row carries.

A literal rather than `str(Verdict.MATCHED)`, so this module keeps its runtime
distance from `resources`: nothing about presentation should be a reason to import
the logic. `tests/cli/test_output.py` asserts the two agree."""

VERDICT_MARKS = {'converged': '✓', 'drift': '~', 'issue': '✗'}
"""What stands in front of a section's name, since the name itself is the heading.

A mark rather than the verdict word, which now appears once, on the closing line
that is the run's actual answer. Spelled out on every section it was a column of
`converged` nine deep, in the position where the reader is looking for the name of
the thing.

A mark and not colour alone. `NO_COLOR` is a preference this fleet honours, so a
report that carries its verdict only in an escape code answers nothing on a machine
that asked for none — and the marks match `_render`'s, which have meant this for
as long as `apply` has printed them."""

EVIDENCE_INDENT = '    '
VERDICT_COLUMN = 11
SUBJECT_COLUMN = 28
"""The two columns every evidence row shares — a change's, a finding's, and the
advice line that hangs under both.

Named because they are the property, not a detail of one f-string. A finding
reading as part of the same list as the changes above it is what makes the output
one list rather than two, and that only holds while all three agree. Repeated as
literals they had already been copied four times, and nothing would have failed if
one of the copies drifted.

`SUBJECT_COLUMN` is a floor rather than the width. A section sets its own from the
longest item in it, so `shell-plugin/zsh-syntax-highlighting` no longer shoves one
row's detail three columns right of its neighbours' — an alignment that holds for
most rows and breaks for a few reads as a broken table rather than a wide word."""

SUBJECT_CEILING = 44
"""Where a section stops widening for one long item.

Past this the column costs every other row more than the long one gains, and the
detail is pushed off a narrow terminal entirely. The over-long item takes the hit
alone, which is the same trade `announce` makes by cropping."""


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
    """The counts behind a verdict, where there are any, worded for the verb asking.

    `ResourceResult` has carried these since it was written and no row has ever
    shown them, so "converged" meant whatever the reader assumed it meant. Each
    answers a question the verdict alone leaves open: how much the other verb
    would report, how much nothing could measure either way, and how much of the
    work will ask for a password.

    **Each verb shows only the count that is not its own answer**, and words it as
    the other verb's business. A `plan` row saying `converged` beside
    `4 need attention` was a row contradicting itself: apply has nothing to do
    here, and four tools are logged out, and both are true. Saying "4 need a
    person" is the same number read from the side that owns it. The mirror case is
    a `check` row saying `converged` beside a non-zero `pending`, which is a
    declared package merely absent — drift, and not something wrong.

    The count a verb *does* answer with never appears, because its own detail
    sentence already states it. `4 item(s) need a person: learning, meso, ...`
    followed by `4 need a person` is the sentence twice.

    Only non-zero counts appear. A converged resource with zeroes would otherwise
    print a row of noughts on every line of a healthy machine, which is the "pages
    of output" this is trying not to become.
    """
    counts: tuple[tuple[int, str], ...]
    if str(result.lens) == 'check':
        counts = ((result.pending, 'differ'), (result.unmeasured, 'unmeasured'))
    else:
        counts = ((result.attention, 'need a person'), (result.unmeasured, 'unmeasured'), (result.privileged, 'need a password'))
    shown = [f'{count} {label}' for count, label in counts if count]
    return f'  ·  {", ".join(shown)}' if shown else ''


def render_result(result: ResourceResult) -> None:
    """One resource's section: its name, what it found, and the rows behind that.

    **The resource's name is the heading.** The left column spelled the verdict on
    every section, so a healthy run was the word `converged` nine deep in the one
    position a reader scans for the name of the thing. The verdict is a mark now,
    and the word itself appears once, on the closing line where it is the run's
    answer rather than a label on each part of it.

    The heading goes to stdout because it is the answer to the question asked, and
    the rows go to stderr because they are the evidence for it — the same split
    every command here keeps. Interleaved on a terminal they read as one section,
    and redirected they separate into an answer and a transcript.

    **The rows come after the heading, and belong to it.** They were printed while
    the fold was still running, which put the whole walk's evidence above the whole
    walk's verdicts: four logged-out CLIs appeared under the progress line for
    `credentials`, and the `credentials` verdict two lines later said converged.
    Nothing on screen tied a row to the resource that found it.

    Keyed on the verdict's string value rather than the enum, so this module stays
    below `reconcile` and does not import it at runtime — presentation should not
    be a reason for the logic to be loaded.
    """
    colour = VERDICT_COLOURS[str(result.verdict)]
    mark = VERDICT_MARKS[str(result.verdict)]
    # A summary may hold a newline where the resource measures more than one kind
    # of thing, and `system` joined its two with a comma into the longest row in
    # the report. Continuations align under the first, so they read as the same
    # sentence rather than as items — and the counts ride on the *last* of them,
    # since a tally wedged between two halves of a sentence separates them.
    lines = result.detail.split('\n')
    trailer = f'{tallies(result)}{elapsed(result.seconds)}'
    console.print(f'[{colour}]{mark}[/] [bold]{result.address:<11}[/] {lines[0]}{trailer if len(lines) == 1 else ""}')
    for position, line in enumerate(lines[1:], start=2):
        console.print(f'  {"":<11} {line}{trailer if position == len(lines) else ""}')

    deferred, listed = _listed(result)
    width = _width([change.item for change in result.findings] + [change.item for change in deferred] + [row.item for row in listed])
    for section, message in result.invalid:
        render_finding(section, message)
    for change in [*result.findings, *deferred]:
        render_change(change, width)
    for row in listed:
        render_examined(row, width)
    # After the section rather than before it, so the closing line sits below a gap
    # too and nothing has to remember whether it is first.
    console.print()


def render_verdict(results: Sequence[ResourceResult], lens: Lens) -> None:
    """The run's answer, and the one place the verdict word is spelled out.

    It was the left column of every section, which put `converged` nine deep on a
    healthy machine and said nothing about the run as a whole. It is the run as a
    whole that a person came for, and it belongs at the bottom, where the terminal
    stops scrolling.

    Imported from `reconcile` at call time rather than at module scope. This module
    sits below it on purpose — `reconcile` renders through this one — and the
    sentence is the fold's to compose, since only it knows what the two verbs keep.
    """
    from dotfiles import reconcile

    verdict = str(reconcile.worst(results))
    colour = VERDICT_COLOURS[verdict]
    console.print(f'[{colour}]{verdict:<9}[/] {reconcile.verdict_line(results, lens)}')


def _listed(result: ResourceResult) -> tuple[tuple[Change, ...], tuple[Examined, ...]]:
    """What this section lists beyond its own findings, after the size threshold.

    Two lists rather than one merged sequence, so nothing here has to construct a
    `resources` type: presentation should not be a reason to import the logic, which
    is the same rule `MATCHED` is a literal for.

    The threshold is per group rather than per resource, because `system` measures a
    hundred declared packages and nine `system.yml` rows and they are different
    questions — which its own summary already says in two sentences. One threshold
    over the whole resource could only answer by suppressing both.
    """
    if not showing_evidence():
        return (), ()

    grouped: dict[str, list[Examined]] = {}
    for row in result.examined:
        grouped.setdefault(row.group, []).append(row)

    kept = [row for rows in grouped.values() if _fits(len(rows)) for row in rows]
    # The other verb's findings are changes, so they carry no group and are weighed
    # as one — which is right, since a resource never splits *what differs* into
    # kinds the way it splits what it merely holds.
    return (result.others if _fits(len(result.others)) else ()), tuple(kept)


def _fits(count: int) -> bool:
    return listing_everything() or count <= LISTED_MAX


def _width(items: list[str]) -> int:
    """How wide this section's subject column is, from the longest thing in it."""
    return min(max([SUBJECT_COLUMN, *(len(item) for item in items)]), SUBJECT_CEILING)


LISTED_MAX = 24
"""How many items a group may have before its default row is a count.

A reading threshold rather than a performance one. Below it the summary sentence
*is* the list, only worse — "go, node, rust, uv" names four runtimes and drops
the version of each, and "~/.env matches the manifest" withholds the whole of
what the file says this machine is. Above it the sentence is a genuine collapse
of something nobody wants unasked, and `-v` expands it.

The number is where a section stops reading as one block and starts being a page.
It leaves the three declared inventories — packages, symlinks and the system half
— as counts, which is right for a different reason too: each is long enough that
its own `list` verb is the better door.
"""


def listing_everything() -> bool:
    """Whether `-v` (or `LOG_LEVEL=debug`) asked for every item on screen.

    Read off the console threshold for the reason `showing_evidence` is, and it is
    the same threshold from the other end: one flag decides how much of a run
    reaches the terminal, so a second switch could disagree with it.
    """
    import logging as stdlib

    from dotfiles import logging

    level, _ = logging.resolved_console()
    return stdlib.getLevelNamesMapping().get(level, stdlib.INFO) <= stdlib.DEBUG


SLOW_RESOURCE_SECONDS = 2.0
"""Above this, a resource's own measurement is worth colouring rather than stating.

The number is a reading threshold, not a performance one: a row that takes long
enough to be *waited on* is the row a reader is looking for when they come back
to a screen that sat still, and everything under it is noise in a list of rows.
"""


def elapsed(seconds: float) -> str:
    """What one measurement cost, in the units a person compares.

    Minutes once past sixty, because "294.1s" is a number that has to be divided
    before it means anything, and the whole reason this is printed is that
    somebody sat watching it.

    Nothing at all under a tenth of a second. A column of `0.0s` down every
    resource that answered instantly makes the one row worth reading harder to
    find, which is the opposite of what a timing is for.

    A slow one is coloured and an ordinary one is plain, rather than the pair
    being coloured against faint. Faint is unreadable on half the terminal themes
    this fleet uses, so the row it was hiding is the row somebody came back to
    the screen to find.
    """
    if seconds < 0.1:
        return ''
    rendered = f'{seconds:.1f}s' if seconds < 60 else f'{int(seconds // 60)}m{seconds % 60:04.1f}s'
    return f'  [yellow]{rendered}[/]' if seconds >= SLOW_RESOURCE_SECONDS else f'  {rendered}'


def announce(address: str, detail: str) -> None:
    """Say what is being measured, before it is.

    Two gates, answering different questions. `showing_evidence` is `-q`, and
    cli-design.md § "Quieten the evidence, never the answer" names the progress
    headings as exactly what it removes. `heading` beside it is gated the same
    way, and a progress line outranking the heading it announces would be the odd
    one out.

    The terminal test is the second, and it is not about volume: this exists to
    be read *during* the wait, and a wait nobody is sitting through does not need
    narrating. The scheduled check writes into the journal and a `--json` run is
    parsed, so in both this is a second row per resource carrying nothing the
    verdict row does not.
    """
    if not showing_evidence() or not err_console.is_terminal:
        return
    # Cropped rather than wrapped, which is also what makes `retract` correct: it
    # moves the cursor up exactly one row, and a line that wrapped would leave the
    # half above it on screen.
    err_console.print(f'[blue]⋯[/] {address:<11} {detail}', no_wrap=True, overflow='ellipsis')


def retract() -> None:
    """Take back the progress line, now that the answer is ready to replace it.

    A progress line is a statement about the present tense, and leaving it on
    screen turns it into a second, worse report. Measured on this machine: a
    healthy `check` printed nine `⋯` lines carrying each resource's help text, then
    nine verdict rows carrying each resource's answer, and the reader's question
    was which of the two lists was the report — the resource descriptions read as
    a summary of their own.

    Gated as `announce` is, because it erases what `announce` wrote and a run
    where nothing was written must not eat the line above it.

    And gated once more, on `-v` not being set. This erases *the line above*, not
    the announcement by identity, so it is only correct while nothing else can have
    printed in between — which at DEBUG is false: `engine._measure` logs
    `measured` and every `effects.run` logs `ran`, all to this console. There the
    progress line stays, which is the right answer anyway, since a reader who asked
    for the log wants the line the log belongs under.
    """
    if not showing_evidence() or listing_everything() or not err_console.is_terminal:
        return
    err_console.control(Control((ControlType.CURSOR_UP, 1), (ControlType.CARRIAGE_RETURN,), (ControlType.ERASE_IN_LINE, 2)))


def measured(address: str, detail: str, seconds: float) -> None:
    """What one resource turned out to hold, and what asking cost.

    `apply`'s counterpart to the verdict row `check` and `plan` print. It renders
    no verdict, because an apply is about to act on what was found and a row
    saying "drift" immediately above the repair for it is a fact that expires as
    the reader looks at it. What does not expire is which part of the machine the
    wait belonged to.

    Gated with the rest of the narration: this is the working an apply shows, not
    the answer it was asked for, and `-q` is a request for less of exactly this.
    """
    if not showing_evidence():
        return
    err_console.print(f'[green]✓[/] [bold]{address:<11}[/] {detail}{elapsed(seconds)}')


def render_change(change: Change, width: int = SUBJECT_COLUMN) -> None:
    """One item's verdict, on stderr — and, where there is one, the next step.

    Below a composite `check`, these are the evidence for the row that follows,
    not the answer a caller parses — which is `--json`. Keyed on the verdict's
    string value for the same reason `render_result` is: presentation should not
    be a reason to import the logic.

    `advice` prints as its own line rather than appended to `detail`, aligned
    under it: the two answer different questions — what is wrong, and what to do
    about it — and a reader scanning a screen of rows for the instruction wants
    it in one column, not folded into a sentence of varying length.

    `source` rides inside the same parenthesis as `observed` rather than taking a
    column, because it is meaningless without it and is set on a handful of rows:
    a column would be blank on nearly every line of a real run.
    """
    if not showing_evidence():
        return
    colour = CHANGE_COLOURS[str(change.verdict)]
    attribution = f' from {change.source}' if change.source else ''
    observed = f' (is {change.observed!r}{attribution})' if change.observed else ''
    err_console.print(f'{EVIDENCE_INDENT}[{colour}]{change.verdict:<{VERDICT_COLUMN}}[/] {change.item:<{width}} {change.detail}{observed}')
    # One row per line, because advice is now assembled from what a diagnosis
    # measured — the owning package, then the command that removes it — and a
    # reader scanning for the command wants it on a line of its own rather than
    # inside a sentence.
    for line in change.advice.splitlines():
        err_console.print(f'{EVIDENCE_INDENT}{"":<{VERDICT_COLUMN}} {"":<{width}} [blue]→[/] {line}')


def render_examined(row: Examined, width: int = SUBJECT_COLUMN) -> None:
    """One item a resource looked at and was happy with, in the changes' columns.

    `matched` is the label, which is the verdict a `Change` would have carried had
    the resource had anything to say about it — so a section reads as one list of
    every item, with the interesting ones coloured rather than segregated.
    """
    if not showing_evidence():
        return
    colour = CHANGE_COLOURS[MATCHED]
    err_console.print(f'{EVIDENCE_INDENT}[{colour}]{MATCHED:<{VERDICT_COLUMN}}[/] {row.item:<{width}} {row.detail}')


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
