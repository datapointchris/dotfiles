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

from dotfiles import vocabulary
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode

if TYPE_CHECKING:
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

NEED_ATTENTION = 'need attention'
"""How drift that `apply` declines to act on is worded, everywhere it is counted.

Named because six sites across two modules render it, and the tests build their
expected strings from it rather than repeating it — so rewording is this line and
its neighbour, not a sweep. `attention` rather than a repairer is what the bucket
can honestly claim: `Change.declined` is the complement of "apply will act", so it
carries `Repair.NONE` items with no by-hand route to point at."""

NEEDS_ATTENTION = 'needs attention'
"""The same phrase as a section heading, where the subject is singular."""

VERDICT_MARKS = {'converged': '✓', 'drift': '~', 'issue': '✗'}
"""What stands in front of a section's name, since the name itself is the heading.

A mark and not colour alone: `NO_COLOR` is a preference this fleet honours, and a
verdict carried only in an escape code answers nothing on a machine that asked for
none."""

PROGRESS_MARK = '⋯'
"""What stands in front of a line stated in the present tense.

Deliberately not one of `VERDICT_MARKS` — a section printed before its work has
happened would otherwise put a tick in front of an install that has not run."""

NOTICE_MARK = '!'
"""What stands in front of a set the run walked past rather than judged.

Neither what `apply` declined to act on nor what it could not measure is a verdict
about the machine, so neither takes a verdict mark."""

EVIDENCE_INDENT = '    '
VERDICT_COLUMN = 11
SUBJECT_COLUMN = 28
"""The two columns every evidence row shares — a change's, a finding's, and the
advice line that hangs under both.

`SUBJECT_COLUMN` is a floor rather than the width: a section sets its own from the
longest item in it, so one long address cannot shove that row's detail past its
neighbours'."""

SUBJECT_CEILING = 44
"""Where a section stops widening for one long item.

Past this the column costs every other row more than the long one gains, so the
over-long item takes the hit alone."""

ADDRESS_COLUMN = max(len(resource) for resource in vocabulary.RESOURCES)
"""How wide the name column is on a section heading, in every report that has one.

Derived rather than typed, because the number *is* the widest resource name and a
literal is a second copy nothing would notice going stale. A longer name —
`packages/ghrelease`, a stage called `system_upgrade` — pushes its own detail right
rather than being cut."""

VERDICT_WIDTH = max(len(word) for word in VERDICT_COLOURS)
"""How wide the closing line's verdict word is: the longest of them, so the
sentence after it starts in one place whatever the run answered."""


def quoted(value: str) -> str:
    """A measured value, delimited for reading, with its backslashes left alone.

    Not plain `repr`: it doubles every backslash, and a git credential helper is a
    shell command line where `/mnt/c/Program\\ Files/...` then reads as a config
    that escaped the space twice. `repr` is still right for a control character,
    which would otherwise break the row across two lines.
    """
    return repr(value) if any(character in value for character in '\n\r\t') else f"'{value}'"


def showing_evidence() -> bool:
    """Whether the per-item rows below a verdict are worth printing.

    Read off the console threshold rather than held as a second switch, so `-q`
    and `LOG_LEVEL` cannot disagree. The rows go through Rich rather than logging,
    so nothing else connects them to `-q`. The verdict is never suppressed.
    """
    import logging as stdlib

    from dotfiles import logging

    level, _ = logging.resolved_console()
    return stdlib.getLevelNamesMapping().get(level, stdlib.INFO) <= stdlib.INFO


def emit_json(data: Any) -> None:
    """Write machine-readable output to stdout, bypassing Rich entirely.

    `print`, not `console.print`: Rich wraps at the terminal width and reads square
    brackets as markup, either of which corrupts the document being parsed.
    """
    print(json.dumps(data, indent=2, default=str))


def emit_text(text: str) -> None:
    """Write a file's contents to stdout, byte for byte.

    `print`, not `console.print`, for the reason `emit_json` gives.
    """
    print(text, end='')


def tallies(result: ResourceResult) -> str:
    """The counts behind a verdict, worded for the verb asking.

    **Each verb shows only the count that is not its own answer**, because its own
    is already in the detail sentence beside this. So a converged `plan` row can
    carry a non-zero attention count without contradicting itself: the verdict
    answers for apply, and the tally is what `check` would report.
    """
    if str(result.lens) == 'check':
        return tally((result.pending, 'differ'), (result.unmeasured, 'unmeasured'))
    return tally((result.attention, NEED_ATTENTION), (result.unmeasured, 'unmeasured'), (result.privileged, 'need a password'))


def tally(*counts: tuple[int, str]) -> str:
    """The non-zero counts a section carries, in the punctuation every section uses.

    Separate from `tallies` so a heading that is not a `ResourceResult` — an
    `apply` group, `network check` — gets the same trailer from one owner. Zeroes
    are dropped rather than printed down every line of a healthy machine.
    """
    shown = [f'{count} {label}' for count, label in counts if count]
    return f'  ·  {", ".join(shown)}' if shown else ''


def section_line(mark: str, name: str, detail: str, colour: str = '', trailer: str = '') -> str:
    """One section's opening line as markup: a mark, the name of the thing, what it found.

    Returned rather than printed, because the reports sharing this geometry do not
    share a stream — a read verb's heading is stdout, an `apply`'s is stderr, and
    `machines show`'s is data. Colour is optional: a listing has no verdict, and an
    empty style tag renders as one.
    """
    marked = f'[{colour}]{mark}[/]' if colour else mark
    return f'{marked} [bold]{name:<{ADDRESS_COLUMN}}[/] {detail}{trailer}'


def render_section(address: str, detail: str, seconds: float = 0.0, mark: str = '✓', colour: str = 'green') -> None:
    """One part of an `apply`: what it holds, or what is about to happen to it.

    No verdict on the measure pass. An apply is about to act on what it found, so
    a row saying "drift" directly above its own repair expires as it is read.

    On stderr, since an `apply`'s stdout carries the run record and nothing else.
    """
    if not showing_evidence():
        return
    err_console.print(section_line(mark, address, detail, colour, elapsed(seconds)))


def render_result(result: ResourceResult, stream: Console) -> None:
    """One resource's section: its name, what it found, and the rows behind that.

    **The heading goes to `stream`; the rows are always evidence on stderr.** A
    read verb passes stdout, because its heading is the answer being asked for. An
    `apply` passes stderr, because its stdout is the run record.

    **`stream` has no default**, since neither answer is safe for the other caller:
    stdout on a write verb corrupts the document, stderr on a read verb sends the
    answer where a redirect will not find it.

    Keyed on the verdict's string value rather than the enum, so this module does
    not import `reconcile` at runtime.
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
    stream.print(section_line(mark, result.address, lines[0], colour, trailer if len(lines) == 1 else ''))
    for position, line in enumerate(lines[1:], start=2):
        stream.print(f'  {"":<{ADDRESS_COLUMN}} {line}{trailer if position == len(lines) else ""}')

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
    stream.print()


RULE_COLOUR = 'blue'
"""Explicit, because Rich draws a rule faint by default and faint is unreadable on
half the terminal themes this fleet uses."""


def render_rule(title: str, stream: Console) -> None:
    stream.rule(f'[bold]{title}[/]', style=RULE_COLOUR, align='left')


def render_summary_row(verdict: str, name: str, detail: str, stream: Console) -> None:
    """A summary row is its own section heading again, so it goes through the same
    builder — a recap worded afresh makes the reader compare phrasings."""
    stream.print(section_line(VERDICT_MARKS[verdict], name, detail, VERDICT_COLOURS[verdict]))


def render_verdict(word: str, sentence: str, stream: Console) -> None:
    """The run's answer, and the one place the verdict word is spelled out.

    Takes the word and the sentence rather than the results behind them: only the
    fold knows what each verb keeps, and `apply` has no lens at all.

    Ungated whatever `-q` says, because a run reporting by exit code alone is a
    worse command rather than a quieter one.
    """
    stream.print(f'[{VERDICT_COLOURS[word]}]{word:<{VERDICT_WIDTH}}[/] {sentence}')


def _listed(result: ResourceResult) -> tuple[tuple[Change, ...], tuple[Examined, ...]]:
    """What this section lists beyond its own findings, after the size threshold.

    The threshold is per group, not per resource: `system` measures a hundred
    declared packages and nine `system.yml` rows, and one threshold over both could
    only answer by suppressing both.
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

A reading threshold, not a performance one: where a section stops being one block
and starts being a page. `-v` expands anything above it.
"""


def listing_everything() -> bool:
    """Whether `-v` (or `LOG_LEVEL=debug`) asked for every item on screen.

    The same threshold `showing_evidence` reads, from the other end.
    """
    import logging as stdlib

    from dotfiles import logging

    level, _ = logging.resolved_console()
    return stdlib.getLevelNamesMapping().get(level, stdlib.INFO) <= stdlib.DEBUG


SLOW_RESOURCE_SECONDS = 2.0
"""Above this, a resource's own measurement is coloured rather than merely stated.

A reading threshold, not a performance one: long enough to have been waited on is
what makes a row the one somebody came back to the screen to find.
"""


def elapsed(seconds: float) -> str:
    """What one measurement cost, in the units a person compares.

    Minutes past sixty, nothing at all under a tenth of a second, and a slow one
    coloured against a plain one rather than against faint — faint is unreadable
    on half the terminal themes this fleet uses.
    """
    if seconds < 0.1:
        return ''
    rendered = f'{seconds:.1f}s' if seconds < 60 else f'{int(seconds // 60)}m{seconds % 60:04.1f}s'
    return f'  [yellow]{rendered}[/]' if seconds >= SLOW_RESOURCE_SECONDS else f'  {rendered}'


def announce(address: str, detail: str) -> None:
    """Say what is being measured, before it is.

    Two gates. `showing_evidence` is `-q`, per cli-design.md § "Quieten the
    evidence, never the answer". The terminal test is not about volume: this is
    read *during* the wait, and a scheduled or `--json` run has nobody sitting
    through one.
    """
    if not showing_evidence() or not err_console.is_terminal:
        return
    # Cropped rather than wrapped, which is also what makes `retract` correct: it
    # moves the cursor up exactly one row, and a line that wrapped would leave the
    # half above it on screen.
    err_console.print(section_line(PROGRESS_MARK, address, detail, 'blue'), no_wrap=True, overflow='ellipsis')


def retract() -> None:
    """Take back the progress line, now that the answer is ready to replace it.

    Gated as `announce` is, because a run where nothing was written must not eat
    the line above it.

    **Gated again on `-v`, and that is the trap.** This erases *the line above*
    rather than the announcement by identity, so it is only correct while nothing
    printed in between. At DEBUG that is false: `engine._measure` and every
    `effects.run` log to this console.
    """
    if not showing_evidence() or listing_everything() or not err_console.is_terminal:
        return
    err_console.control(Control((ControlType.CURSOR_UP, 1), (ControlType.CARRIAGE_RETURN,), (ControlType.ERASE_IN_LINE, 2)))


def render_change(change: Change, width: int = SUBJECT_COLUMN) -> None:
    """One item's verdict, on stderr — and, where there is one, the next step.

    `advice` takes its own line under `detail` rather than being appended, so a
    reader scanning for the instruction finds it in one column. `source` rides
    inside `observed`'s parenthesis, being meaningless without it and set on a
    handful of rows.
    """
    if not showing_evidence():
        return
    attribution = f' from {change.source}' if change.source else ''
    observed = f' (is {quoted(change.observed)}{attribution})' if change.observed else ''
    render_row(str(change.verdict), change.item, f'{change.detail}{observed}', CHANGE_COLOURS[str(change.verdict)], width)
    # One row per line, because advice is now assembled from what a diagnosis
    # measured — the owning package, then the command that removes it — and a
    # reader scanning for the command wants it on a line of its own rather than
    # inside a sentence.
    for line in change.advice.splitlines():
        render_advice(line, width)


def render_examined(row: Examined, width: int = SUBJECT_COLUMN) -> None:
    """One item a resource looked at and was happy with, in the changes' columns.

    Sharing their columns is what makes a section one list of every item, with the
    interesting ones coloured rather than segregated.
    """
    render_row(MATCHED, row.item, row.detail, CHANGE_COLOURS[MATCHED], width)


def render_row(label: str, subject: str, detail: str, colour: str = '', width: int = SUBJECT_COLUMN) -> None:
    """One evidence row: a label, the thing it is about, and what there is to say.

    The column contract in one place, since a section reads as one list only while
    every row agrees on the widths. Public because the bundle verbs render rows for
    things that are not `Change`es, and synthesising one to reach a renderer would
    put a unit of work into the record vocabulary for a file listing.
    """
    if not showing_evidence():
        return
    marked = f'[{colour}]{label:<{VERDICT_COLUMN}}[/]' if colour else f'{label:<{VERDICT_COLUMN}}'
    # Padded only where a third field follows it. A row with nothing to say would
    # otherwise end in a column of blanks, and the trailing space is what a copied
    # filename carries into the next command.
    written = f'{subject:<{width}} {detail}' if detail else subject
    err_console.print(f'{EVIDENCE_INDENT}{marked} {written}')


def render_advice(line: str, width: int = SUBJECT_COLUMN) -> None:
    """The next step, hung under the row it belongs to rather than beside it.

    One continuation shared by both renderers that produce these, so a run's
    findings and its failures put the same kind of instruction in one column.
    """
    if not showing_evidence():
        return
    err_console.print(f'{EVIDENCE_INDENT}{"":<{VERDICT_COLUMN}} {"":<{width}} [blue]→[/] {line}')


def render_note(text: str) -> None:
    """A plain line in the evidence column, for a fact with no verdict to carry.

    Through here rather than a bare `err_console.print`, so `-q` removes it with
    the rest of the evidence.
    """
    if not showing_evidence():
        return
    err_console.print(f'{EVIDENCE_INDENT}{text}')


def render_finding(section: str, message: str) -> None:
    """One declaration finding, on stderr, in the same column as a change.

    Evidence for the `machines` row the way a Change is for a resource's, so the
    two read as one list.
    """
    render_row('invalid', section, message, 'red')


def error(message: str) -> None:
    err_console.print(f'[red]✗[/] {message}')


def success(message: str) -> None:
    err_console.print(f'[green]✓[/] {message}')


def warn(message: str) -> None:
    err_console.print(f'[yellow]{NOTICE_MARK}[/] {message}')


def hint(message: str) -> None:
    err_console.print(f'[blue]→[/] {message}')


def report(refused: Refusal) -> ExitCode:
    """Print a refusal the way every door prints it, and answer with its code.

    A function rather than a method on `boundary.Boundary`, because there are two
    console scripts onto this package and only one of them is a Typer app.
    `packages` enters at `declaration.cli` and never touches a click group, so a
    handler living inside `Boundary.invoke` would leave that door printing a
    traceback for a misspelt name — losing the sentence, losing the `did you
    mean:` advice, and exiting 1, which this tool spends on DRIFT.

    Here rather than beside `Boundary`, so the door that has no click group can
    reach it without importing typer. `tests/test_dependencies.py` pins that.
    """
    first, *rest = str(refused).splitlines() or ['']
    error(first)
    for line in rest:
        # Aligned under the first line's text rather than its marker, so a
        # manifest with three faults reads as one refusal with three reasons.
        # Unindented, the second reason has no marker and looks like a separate
        # unattributed line.
        err_console.print(f'  {line}', markup=False, highlight=False)
    if refused.advice:
        hint(refused.advice)
    return refused.code
