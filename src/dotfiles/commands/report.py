"""Reading the run records.

Nothing here shells out — `sinks.keep` wrote the records on the way past, so this
reads them off disk and does not change when the resources move underneath it.

`path` exists to be substituted into another command: `ifiles upload "$(dotfiles
report path)"` is the whole fleet-analysis loop, which is why it prints a bare
path to stdout and nothing else. It is not the only place a path appears, though,
because a verb that makes you go and ask for one is a verb nobody knows about:
`latest` and `show` render it too, and a failed `apply` prints it unasked.
"""

from __future__ import annotations

import dataclasses
import dataclasses as dc
import statistics
from collections import defaultdict
from pathlib import Path

import typer
from rich.table import Table

from dotfiles import runs
from dotfiles.output import VERDICT_COLOURS
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import error
from dotfiles.resources import OutcomeStatus
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='What past runs did, and what they cost')

UNSUCCESSFUL = {str(OutcomeStatus.FAILED), str(OutcomeStatus.REFUSED)}

JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')


def _unsuccessful(record: runs.RunRecord) -> str:
    """What kept a run from converging, in the words `apply` used at the time.

    Not `RunRecord.converged`, which is true only where every item MATCHED — that
    is the right answer for `show`, whose reader is looking at one run, and the
    wrong one for a list, where it marks a healthy apply that repaired something
    the same as the run that could not examine a resource at all.
    """
    refused = [issue.address for issue in record.issues]
    failed = [outcome.address for outcome in record.outcomes if outcome.action in UNSUCCESSFUL]
    named = sorted(set(refused + failed))
    if not named:
        return ''
    shown = ', '.join(named[:3])
    return f'{len(named)} unconverged: {shown}' + (', …' if len(named) > 3 else '')


def _find(identifier: str | None) -> Path:
    """Resolve a run id to its record, or the newest run when none is given."""
    if identifier is None:
        if found := runs.latest():
            return found
        error('no runs recorded yet')
        raise typer.Exit(ExitCode.ISSUE)

    matches = [path for path in runs.list_runs() if path.stem.startswith(identifier)]
    if not matches:
        # The id every rendering leads with is the record's, and it appears nowhere
        # in the filename the stem match reads — so the one identifier a reader has
        # in front of them was the only one that did not resolve. Second, because
        # this reads every record and the stem match reads none.
        matches = [path for path in runs.list_runs() if runs.read(path).id.startswith(identifier)]
    if not matches:
        raise typer.BadParameter(f'no run matching {identifier!r}')
    if len(matches) > 1:
        raise typer.BadParameter(f'{identifier!r} matches {len(matches)} runs; give more of the id')
    return matches[0]


def _render(path: Path, record: runs.RunRecord) -> None:
    # `[{verdict}]` reads as a Rich style tag, so the word this line exists to say
    # was parsed as markup and dropped — every header printed a trailing blank.
    verdict = 'converged' if record.converged else 'drift'
    colour = VERDICT_COLOURS[verdict]
    console.print(f'[bold]{record.id}[/]  {record.box}  {record.verb}  [{colour}]{verdict}[/]')
    console.print(f'{record.started_at} · {record.duration_seconds:.1f}s')
    # What the reader wants the record *for* is usually to send it somewhere, and
    # the rendering that answers every other question about a run was the one place
    # its own location did not appear. Unwrapped and unparsed: this is meant to be
    # copied whole, and a path is not markup however many brackets it contains.
    console.print(str(path), soft_wrap=True, markup=False)

    if record.outcomes:
        table = Table(box=None, pad_edge=False)
        table.add_column('address')
        table.add_column('verdict')
        table.add_column('action')
        table.add_column('seconds', justify='right')
        for outcome in record.outcomes:
            table.add_row(outcome.address, outcome.verdict, outcome.action, f'{outcome.timing.duration_seconds:.2f}')
        console.print(table)

    # Only where it went wrong: a provider hands back a detail line for a success
    # too, and 112 of "installed zk" buries the four that say why nothing was.
    for outcome in record.outcomes:
        if outcome.message and outcome.action in UNSUCCESSFUL:
            console.print(f'[red]{outcome.action}[/] {outcome.address}: {outcome.message}')

    for issue in record.issues:
        console.print(f'[red]{issue.kind}[/] {issue.address}: {issue.message}')


def _emit(path: Path, record: runs.RunRecord, as_json: bool) -> None:
    if as_json:
        emit_json(dataclasses.asdict(record))
    else:
        _render(path, record)


@app.command('latest')
def latest(as_json: bool = JsonOption) -> None:
    """Show the most recent run."""
    found = _find(None)
    _emit(found, runs.read(found), as_json)


@app.command('list')
def list_runs(
    machine: str = typer.Option(None, '--machine', help='Only runs on this machine'),
    verb: str = typer.Option(None, '--verb', help='Only runs of this verb'),
    limit: int = typer.Option(20, '--limit', help='How many to show'),
    as_json: bool = JsonOption,
) -> None:
    """List recorded runs, newest first."""
    found = runs.list_runs(machine=machine, verb=verb, limit=limit)
    if as_json:
        emit_json([path.stem for path in found])
        return
    if not found:
        return
    # Names alone made this a directory listing with a filter: finding which run
    # failed meant opening each record in turn, and the fleet shares `runs/`, so
    # "which one went wrong" is the question the list is reached for.
    table = Table(box=None, pad_edge=False)
    table.add_column('run')
    table.add_column('outcome')
    for path in found:
        wrong = _unsuccessful(runs.read(path))
        colour = 'red' if wrong else 'green'
        table.add_row(path.stem, f'[{colour}]{wrong or "ok"}[/]')
    console.print(table)


@app.command('show')
def show(identifier: str = typer.Argument(..., help='Run id, or a unique prefix'), as_json: bool = JsonOption) -> None:
    """Show one run in full."""
    found = _find(identifier)
    _emit(found, runs.read(found), as_json)


@app.command('path')
def path(identifier: str = typer.Argument(None, help='Run id (default: the newest)')) -> None:
    """Print a run record's path, for piping into another command."""
    print(_find(identifier))


@app.command('stats')
def stats(as_json: bool = JsonOption) -> None:
    """Aggregate time per address across every recorded run.

    The question this answers is what is slow and whether it is getting slower,
    which no single run can say — which is why `stats` is its own verb rather
    than a flag on `show`.
    """
    durations: defaultdict[str, list[float]] = defaultdict(list)
    records = [runs.read(path) for path in runs.list_runs()]
    for record in records:
        for outcome in record.outcomes:
            durations[outcome.address].append(outcome.timing.duration_seconds)

    if not durations:
        error('no runs recorded yet')
        raise typer.Exit(ExitCode.ISSUE)

    summary = {
        address: {
            'runs': len(seconds),
            'total': round(sum(seconds), 2),
            'median': round(statistics.median(seconds), 2),
            'slowest': round(max(seconds), 2),
        }
        for address, seconds in sorted(durations.items(), key=lambda item: -sum(item[1]))
    }

    unconverged = _never_converged(records)

    if as_json:
        emit_json({'durations': summary, 'unconverged': [dc.asdict(entry) for entry in unconverged]})
        return

    table = Table(box=None, pad_edge=False)
    table.add_column('address')
    for heading in ('runs', 'total', 'median', 'slowest'):
        table.add_column(heading, justify='right')
    for address, row in summary.items():
        table.add_row(address, *(str(row[key]) for key in ('runs', 'total', 'median', 'slowest')))
    console.print(table)

    if unconverged:
        console.print()
        console.print('[bold yellow]never converged[/]  installed again on every recent apply')
        churn = Table(box=None, pad_edge=False)
        churn.add_column('address')
        churn.add_column('machine')
        churn.add_column('applies', justify='right')
        for entry in unconverged:
            churn.add_row(entry.address, entry.machine, str(entry.applies))
        console.print(churn)


CHURN_THRESHOLD = 3
"""Consecutive applies acting on one item before it is called unconverged.

Three rather than two because an item legitimately installs on two runs in a row
— a release lands between them, or the first apply was the machine's first. What
three consecutive says is that installing it does not make it installed, which is
never a fact about the world.
"""


@dc.dataclass(frozen=True, slots=True)
class Unconverged:
    """One item an apply keeps acting on, and how many runs deep it goes."""

    address: str
    machine: str
    applies: int


def _never_converged(records: list[runs.RunRecord]) -> list[Unconverged]:
    """Items an apply acts on every time, which no amount of applying settles.

    The failure mode this exists to name: `brew install pkg-config` succeeds,
    `brew list` reports `pkgconf` because the formula was renamed, and the
    evidence check looks for the declared name and finds nothing. The install
    reports success, the run reports converged, and the item is reinstalled
    forever — thirteen times before the fleet shared its run history and made the
    repetition visible at all.

    A registry package no longer reaches here, and that is not a regression.
    `_transact` re-observes what it installed and records `absent` rather than
    `done`, so the streak this counts never starts and the first run says it
    outright instead of the third. What still reaches here is everything that
    cannot be re-measured that cheaply, which is what three consecutive applies
    was always the fallback for.

    Counted per machine, from the newest apply backwards, stopping at the first
    run that left the item alone. A total count would rank a tool that drifted
    monthly for a year above one that has not converged since Tuesday, and only
    the second is broken.

    A converged item is *absent* from a record rather than present with no
    action — only changes get outcomes — so absence is what ends a streak. Making
    absence transparent instead kept counting through the runs that proved the
    item fine, which reported two long-fixed faults as current: the App Store
    rename and the awscli branch both showed six-deep streaks made entirely of
    history.
    """
    applies = [record for record in records if record.verb == 'apply']
    by_machine: defaultdict[str, list[runs.RunRecord]] = defaultdict(list)
    for record in applies:
        # By box, not by manifest. Keyed on the manifest, macmini's and mbp's
        # applies interleaved into one history, so either Mac leaving an item
        # alone ended the other's streak and a real fault on one of them read as
        # settled.
        by_machine[record.box].append(record)

    found: list[Unconverged] = []
    for machine, history in by_machine.items():
        ordered = sorted(history, key=lambda record: record.started_at, reverse=True)
        streaks: dict[str, int] = {}
        alive: set[str] | None = None
        for record in ordered:
            acted = {outcome.address for outcome in record.outcomes if outcome.action == 'done'}
            # The newest apply seeds the set: an item it left alone converged
            # there, whatever it did before, and this names what is wrong *now*.
            alive = acted if alive is None else alive & acted
            if not alive:
                break
            for address in alive:
                streaks[address] = streaks.get(address, 0) + 1
        found.extend(Unconverged(address, machine, count) for address, count in streaks.items() if count >= CHURN_THRESHOLD)
    return sorted(found, key=lambda entry: (-entry.applies, entry.address))
