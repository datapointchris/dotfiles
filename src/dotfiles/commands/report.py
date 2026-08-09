"""Reading the run records — the one part of the tree that is already real.

Nothing here shells out. The records were written by the observability spine in
step 1, so this reads them directly and will not change when the resources move
underneath it.

`path` exists to be substituted into another command: `ifiles put "$(dotfiles
report path)"` is the whole fleet-analysis loop, which is why it prints a bare
path to stdout and nothing else.
"""

from __future__ import annotations

import dataclasses
import statistics
from collections import defaultdict
from pathlib import Path

import typer
from rich.table import Table

from dotfiles import runs
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import error
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='What past runs did, and what they cost')

JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')


def _find(identifier: str | None) -> Path:
    """Resolve a run id to its record, or the newest run when none is given."""
    if identifier is None:
        if found := runs.latest():
            return found
        error('no runs recorded yet')
        raise typer.Exit(ExitCode.ISSUE)

    matches = [path for path in runs.list_runs() if path.stem.startswith(identifier)]
    if not matches:
        raise typer.BadParameter(f'no run matching {identifier!r}')
    if len(matches) > 1:
        raise typer.BadParameter(f'{identifier!r} matches {len(matches)} runs; give more of the id')
    return matches[0]


def _render(record: runs.RunRecord) -> None:
    verdict = 'converged' if record.converged else 'drift'
    console.print(f'[bold]{record.id}[/]  {record.machine}  {record.verb}  [{verdict}]')
    console.print(f'{record.started_at} · {record.duration_seconds:.1f}s')

    if record.outcomes:
        table = Table(box=None, pad_edge=False)
        table.add_column('address')
        table.add_column('verdict')
        table.add_column('action')
        table.add_column('seconds', justify='right')
        for outcome in record.outcomes:
            table.add_row(outcome.address, outcome.verdict, outcome.action, f'{outcome.timing.duration_seconds:.2f}')
        console.print(table)

    for issue in record.issues:
        console.print(f'[red]{issue.kind}[/] {issue.address}: {issue.message}')


def _emit(record: runs.RunRecord, as_json: bool) -> None:
    if as_json:
        emit_json(dataclasses.asdict(record))
    else:
        _render(record)


@app.command('latest')
def latest(as_json: bool = JsonOption) -> None:
    """Show the most recent run."""
    _emit(runs.read(_find(None)), as_json)


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
    for path in found:
        console.print(path.stem)


@app.command('show')
def show(identifier: str = typer.Argument(..., help='Run id, or a unique prefix'), as_json: bool = JsonOption) -> None:
    """Show one run in full."""
    _emit(runs.read(_find(identifier)), as_json)


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
    for record_path in runs.list_runs():
        for outcome in runs.read(record_path).outcomes:
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

    if as_json:
        emit_json(summary)
        return

    table = Table(box=None, pad_edge=False)
    table.add_column('address')
    for heading in ('runs', 'total', 'median', 'slowest'):
        table.add_column(heading, justify='right')
    for address, row in summary.items():
        table.add_row(address, *(str(row[key]) for key in ('runs', 'total', 'median', 'slowest')))
    console.print(table)
