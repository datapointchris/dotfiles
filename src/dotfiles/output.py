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

PROGRESS_MARK = '⋯'
"""What stands in front of a line stated in the present tense — a resource being
measured, a group about to be acted on.

Deliberately not one of `VERDICT_MARKS`. A section printed before its work has
happened has no verdict to carry, and borrowing one would put a tick in front of
an install that has not run."""

NOTICE_MARK = '!'
"""What stands in front of a set the run walked past rather than judged.

`warn`'s mark, because that is what these sections are: `apply` names what it
declined to act on and what it could not measure, and neither is a verdict about
the machine. Which of the two a reader is looking at is the section's name, which
is the heading."""

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
longest item in it, so one long address cannot shove that row's detail past its
neighbours' — an alignment that holds for most rows and breaks for a few reads as
a broken table rather than a wide word."""

SUBJECT_CEILING = 44
"""Where a section stops widening for one long item.

Past this the column costs every other row more than the long one gains, and the
detail is pushed off a narrow terminal entirely. The over-long item takes the hit
alone, which is the same trade `announce` makes by cropping."""

ADDRESS_COLUMN = max(len(resource) for resource in vocabulary.RESOURCES)
"""How wide the name column is on a section heading, in every report that has one.

Derived from the vocabulary rather than typed, because the number *is* the widest
resource name and a literal is a second copy of that fact which nothing would
notice going stale. A read verb's sections, an `apply`'s, `machines show`'s stage
groups and the requirement register all pad to it, so a reader moving between them
finds the detail in one place.

A longer name — `packages/ghrelease` when a batch announces itself, or a stage
called `system_upgrade` — pushes its own detail right rather than being cut. The
name is what the reader came for, and the rows under it are aligned among
themselves whatever the heading did."""

VERDICT_WIDTH = max(len(word) for word in VERDICT_COLOURS)
"""How wide the closing line's verdict word is: the longest of them.

So the sentence after it starts in one place whether the run converged or refused,
and so a reader scanning several runs' last lines reads one column rather than
three ragged ones."""


def quoted(value: str) -> str:
    """A measured value, delimited for reading, with its backslashes left alone.

    `repr` was doing this and doubles every backslash, which is wrong in the one
    place a backslash carries meaning: a git credential helper is a shell command
    line, so `/mnt/c/Program\\ Files/...` printed as `Program\\\\ Files` reads as a
    config that escaped the space twice. That is unreadable exactly when someone
    is reading it to count them.

    The quotes stay, because a value's leading or trailing space is otherwise
    invisible. So does `repr`, for a value carrying a control character — a raw
    newline would break the row into two and put the second half in a column that
    means something else.
    """
    return repr(value) if any(character in value for character in '\n\r\t') else f"'{value}'"


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

    Without them "converged" means whatever the reader assumes it means. Each
    answers a question the verdict alone leaves open: how much the other verb
    would report, how much nothing could measure either way, and how much of the
    work will ask for a password.

    **Each verb shows only the count that is not its own answer.** A `plan` row
    saying `converged` beside `4 need attention` is not contradicting itself:
    apply has nothing to do here, and four tools are logged out, and both are
    true. The verdict is scoped to the verb that produced it, which `lens`
    decides, and the tally beside it is what the other verb would report. The
    mirror case is a `check` row saying `converged` beside a non-zero `pending`,
    which is a declared package merely absent — drift, and not something wrong.

    The count a verb *does* answer with never appears, because its own detail
    sentence already states it. `4 item(s) need attention: learning, meso, ...`
    followed by `4 need attention` is the sentence twice.

    Only non-zero counts appear. A converged resource with zeroes would otherwise
    print a row of noughts on every line of a healthy machine, which is the "pages
    of output" this is trying not to become.
    """
    if str(result.lens) == 'check':
        return tally((result.pending, 'differ'), (result.unmeasured, 'unmeasured'))
    return tally((result.attention, 'need attention'), (result.unmeasured, 'unmeasured'), (result.privileged, 'need a password'))


def tally(*counts: tuple[int, str]) -> str:
    """The non-zero counts a section carries, in the punctuation every section uses.

    Separate from `tallies` because a heading that is not a `ResourceResult` wants
    the same trailer: the group `apply` is about to act on says how much of it will
    ask for a password, and `network check` says how many sources it could not
    probe. Written out at each of them, the separator was the thing that would drift
    — and it is the whole of what makes a trailer read as a trailer rather than as
    more sentence.

    Only non-zero counts appear, so a converged section does not print a row of
    noughts on every line of a healthy machine.
    """
    shown = [f'{count} {label}' for count, label in counts if count]
    return f'  ·  {", ".join(shown)}' if shown else ''


def section_line(mark: str, name: str, detail: str, colour: str = '', trailer: str = '') -> str:
    """One section's opening line as markup: a mark, the name of the thing, what it found.

    The shape rather than the printing, because the reports that share it do not
    share a stream. A read verb's heading is the answer to the question asked and
    goes to stdout; an `apply`'s is the working and goes to stderr beside the rows
    it introduces; `machines show`'s is a listing and is data. Returning the line
    lets each keep its own stream and its own quiet gate while nothing owns the
    geometry twice — the argument `SUBJECT_COLUMN` makes one row further down,
    applied to the row above it.

    Colour is optional for the reason it is on `render_row`: a listing has no
    verdict to colour, and an empty style tag renders as one.
    """
    marked = f'[{colour}]{mark}[/]' if colour else mark
    return f'{marked} [bold]{name:<{ADDRESS_COLUMN}}[/] {detail}{trailer}'


def render_section(address: str, detail: str, seconds: float = 0.0, mark: str = '✓', colour: str = 'green') -> None:
    """One part of an `apply`: what it holds, or what is about to happen to it.

    The write verb's counterpart to the section `render_result` prints, and the one
    shape behind every heading it puts on screen — what a resource was measured to
    hold, what a group of work is about to do, and the two sets the run walks past.
    Three grammars in one screen is a screen where nothing tells the reader which
    lines are peers.

    It renders no verdict on the measure pass, because an apply is about to act on
    what was found and a row saying "drift" immediately above the repair for it is
    a fact that expires as the reader looks at it. What does not expire is which
    part of the machine the wait belonged to.

    On stderr, and gated with the rest of the narration: an `apply`'s stdout
    carries the run record and nothing else, and `-q` is a request for less of
    exactly this.
    """
    if not showing_evidence():
        return
    err_console.print(section_line(mark, address, detail, colour, elapsed(seconds)))


def render_result(result: ResourceResult, stream: Console) -> None:
    """One resource's section: its name, what it found, and the rows behind that.

    **The resource's name is the heading.** The left column spelled the verdict on
    every section, so a healthy run was the word `converged` nine deep in the one
    position a reader scans for the name of the thing. The verdict is a mark now,
    and the word itself appears once, on the closing line where it is the run's
    answer rather than a label on each part of it.

    **The rows come after the heading, and belong to it.** They were printed while
    the fold was still running, which put the whole walk's evidence above the whole
    walk's verdicts: four logged-out CLIs appeared under the progress line for
    `credentials`, and the `credentials` verdict two lines later said converged.
    Nothing on screen tied a row to the resource that found it.

    **`stream` is where the heading goes, and the rows are always evidence.** For a
    read verb it is stdout, because the heading is the answer to the question asked
    — interleaved on a terminal the two read as one section, and redirected they
    separate into an answer and a transcript. An `apply` renders the declaration it
    refused on through here too, and passes stderr: that verb's stdout is the run
    record, so a `--json` run whose gate fired would otherwise hand its caller a
    heading where the document should be.

    **It has no default, because the stream belongs to the verb rather than to the
    result.** Neither answer is safe for the other caller: stdout put on a write verb
    corrupts the document a caller parses, and stderr put on a read verb sends the
    answer somewhere a redirect will not find it. A parameter whose two callers want
    opposite values is one every caller states.

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

    The run as a whole is what a person came for, and it belongs at the bottom,
    where the terminal stops scrolling. In the left column of every section instead,
    the word is `converged` nine deep on a healthy machine and says nothing about
    the run.

    All three verbs close here, so a `plan`, a `check` and an `apply` end on one
    shape: the verdict word, then a sentence carrying the counts behind it and the
    command that answers whatever is left.

    **The word and the sentence, rather than the results they are folded from.**
    Composing them is the fold's, since only it knows what each verb keeps and
    `apply` has no lens at all — and this module sits below `reconcile`, so asking
    would mean importing it back at call time.

    `stream` has no default for the reason it has none on `render_result`.

    Ungated, whatever `-q` says: the result the command was asked for keeps its
    channel, and a run reporting by exit code alone is a worse command rather than
    a quieter one.
    """
    stream.print(f'[{VERDICT_COLOURS[word]}]{word:<{VERDICT_WIDTH}}[/] {sentence}')


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
    headings as exactly what it removes. `render_section` beside it is gated the
    same way, and a progress line outranking the section it announces would be the
    odd one out.

    The terminal test is the second, and it is not about volume: this exists to
    be read *during* the wait, and a wait nobody is sitting through does not need
    narrating. The scheduled check writes into the journal and a `--json` run is
    parsed, so in both this is a second row per resource carrying nothing the
    verdict row does not.

    In the section's own columns, since the section is what replaces it: the answer
    landing in a different place from the question it answers is the flicker
    `retract` exists to remove.
    """
    if not showing_evidence() or not err_console.is_terminal:
        return
    # Cropped rather than wrapped, which is also what makes `retract` correct: it
    # moves the cursor up exactly one row, and a line that wrapped would leave the
    # half above it on screen.
    err_console.print(section_line(PROGRESS_MARK, address, detail, 'blue'), no_wrap=True, overflow='ellipsis')


def retract() -> None:
    """Take back the progress line, now that the answer is ready to replace it.

    A progress line is a statement about the present tense, and leaving it on
    screen turns it into a second, worse report. Left up, a healthy `check` prints
    one `⋯` line per resource carrying its help text, then one verdict row per
    resource carrying its answer, and the reader's question
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

    `matched` is the label, which is the verdict a `Change` would have carried had
    the resource had anything to say about it — so a section reads as one list of
    every item, with the interesting ones coloured rather than segregated.
    """
    render_row(MATCHED, row.item, row.detail, CHANGE_COLOURS[MATCHED], width)


def render_row(label: str, subject: str, detail: str, colour: str = '', width: int = SUBJECT_COLUMN) -> None:
    """One evidence row: a label, the thing it is about, and what there is to say.

    The column contract in one place. A change's row, a matched row and a declaration
    finding were three f-strings repeating the same three widths, and the alignment
    that makes a section read as one list held only while all three agreed — which is
    what `SUBJECT_COLUMN`'s own docstring says the named constants exist to prevent,
    one level below where they were doing it.

    Public because the bundle verbs render rows for things that are not `Change`es.
    Synthesising a `Change` to reach a renderer would put a unit of work into the
    record vocabulary for a file listing, which is what `Examined` exists to avoid.
    """
    if not showing_evidence():
        return
    marked = f'[{colour}]{label:<{VERDICT_COLUMN}}[/]' if colour else f'{label:<{VERDICT_COLUMN}}'
    err_console.print(f'{EVIDENCE_INDENT}{marked} {subject:<{width}} {detail}')


def render_advice(line: str, width: int = SUBJECT_COLUMN) -> None:
    """The next step, hung under the row it belongs to rather than beside it.

    One continuation shared by the two renderers that produce these. `render_change`
    aligned advice under the detail column and `apply`'s outcome renderer indented it
    by two, so a single run's findings and its failures put the same kind of
    instruction in two different places — and a reader scanning a column for the
    command found half of them.
    """
    if not showing_evidence():
        return
    err_console.print(f'{EVIDENCE_INDENT}{"":<{VERDICT_COLUMN}} {"":<{width}} [blue]→[/] {line}')


def render_note(text: str) -> None:
    """A plain line in the evidence column, for a fact with no verdict to carry.

    The staged bundle's per-category counts are the case: they are evidence for the
    line above rather than a finding about an item, so they take the indent and none
    of the verdict column. Printed through here rather than as a bare
    `err_console.print` so `-q` removes it with the rest of the evidence — a run
    asked for less must not keep one section's rows on a rule of its own.
    """
    if not showing_evidence():
        return
    err_console.print(f'{EVIDENCE_INDENT}{text}')


def render_finding(section: str, message: str) -> None:
    """One declaration finding, on stderr, in the same column as a change.

    A finding is evidence for the `machines` row the way a Change is evidence for
    a resource's, so it reads as one list rather than two — and it goes to stderr
    for the reason every diagnostic here does: `--json` is what a caller parses.
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
