"""The `user_timers` rows and their runs. A unit starts `timers run`; a person can too."""

from __future__ import annotations

import json
import sys
from typing import Any

import typer
from rich.markup import escape
from rich.table import Table

from dotfiles import catalog
from dotfiles import timer_reports
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import err_console
from dotfiles.vocabulary import ExitCode

app = typer.Typer(
    no_args_is_help=True,
    help='Commands this account runs on an interval, and what each run reported',
    epilog=(
        'Examples:\n\n'
        'dotfiles timers list — every declared timer, and how its last run here went\n\n'
        'dotfiles timers show update-check — one timer, with the line its last run recorded\n\n'
        'dotfiles timers run update-check — run a timer now rather than wait for it'
    ),
)

NameArgument = typer.Argument(..., help='The user_timers row to run')
ShownArgument = typer.Argument(..., help='The user_timers row to show')
JsonOption = typer.Option(False, '--json', help='Print the recorded line on stdout')
RowsJsonOption = typer.Option(False, '--json', help='Print each row and its last recorded run as JSON')


def declared() -> dict[str, catalog.UserTimer]:
    return {entry.name: entry for entry in catalog.load().section('user_timers') if isinstance(entry, catalog.UserTimer)}


def named(name: str) -> catalog.UserTimer:
    """The row called `name`, or exit 2 naming the rows that are declared."""
    rows = declared()
    entry = rows.get(name)
    if entry is None:
        err_console.print(f'no user_timers row is named {name!r}. Declared: {", ".join(sorted(rows)) or "none"}')
        raise typer.Exit(ExitCode.USAGE)
    return entry


def described(entry: catalog.UserTimer) -> dict[str, Any]:
    """The row as declared, beside this host's newest recorded run of it, or None where none is kept."""
    return {'name': entry.name, 'argv': list(entry.argv), 'every': entry.every, 'at': entry.at, 'latest': timer_reports.latest(entry.name)}


def schedule(row: dict[str, Any]) -> str:
    return f'{row["every"]} at {row["at"]}' if row['at'] else row['every']


def last_run(row: dict[str, Any]) -> str:
    line = row['latest']
    if line is None:
        return '[dim]no run recorded here[/]'
    color = 'green' if line['outcome'] == 'pass' else 'red'
    return f'[{color}]{line["outcome"]}[/] {line["timestamp"]} — {escape(line["summary"])}'


@app.command(
    'list',
    epilog=(
        'Examples:\n\n'
        'dotfiles timers list — each timer, its interval, and how its last run here went\n\n'
        'dotfiles timers list --json — the rows with each last recorded line'
    ),
)
def list_timers(as_json: bool = RowsJsonOption) -> None:
    """List the declared timers, each with the outcome of its newest run on this host."""
    rows = [described(entry) for entry in sorted(declared().values(), key=lambda entry: entry.name)]
    if as_json:
        emit_json(rows)
        return
    table = Table(box=None, pad_edge=False)
    table.add_column('timer')
    table.add_column('every')
    table.add_column('last run')
    for row in rows:
        table.add_row(row['name'], schedule(row), last_run(row))
    console.print(table)


@app.command(
    'show',
    epilog=(
        'Examples:\n\n'
        'dotfiles timers show update-check — the command, its interval and its last run\n\n'
        'dotfiles timers show update-check --json — the row and the whole recorded line'
    ),
)
def show(name: str = ShownArgument, as_json: bool = RowsJsonOption) -> None:
    """Show one timer's command and interval, and the line its newest run recorded.

    Exit 2 for a name no row declares.
    """
    row = described(named(name))
    if as_json:
        emit_json(row)
        return
    console.print(row['name'], markup=False)
    console.print(f'  command   {" ".join(row["argv"])}', soft_wrap=True, markup=False)
    console.print(f'  every     {schedule(row)}')
    console.print(f'  last run  {last_run(row)}', soft_wrap=True)
    if row['latest'] is not None:
        console.print(f'  recorded  {row["latest"]["seconds"]}s, exit {row["latest"]["exit_code"]}')


@app.command(
    'run',
    epilog=(
        'Examples:\n\n'
        'dotfiles timers run update-check — run it now, and record it as the timer would\n\n'
        'dotfiles timers run update-check --json — and print the recorded line'
    ),
)
def run(name: str = NameArgument, as_json: bool = JsonOption) -> None:
    """Run one timer's command now and append what it did to the timer-reports file.

    Exit 0 when the command passed and 3 when it failed, so the unit that started
    it reads failed too. Exit 2 for a name no row declares.
    """
    entry = named(name)
    line = timer_reports.run(entry)
    try:
        path = timer_reports.record(line)
    except OSError as failed:
        err_console.print(f'{name}: could not record the run in {timer_reports.REPORTS_DIR}: {failed}', soft_wrap=True)
        sys.stderr.write(json.dumps(line) + '\n')
        raise typer.Exit(ExitCode.ISSUE) from failed
    if as_json:
        emit_json(line)
    else:
        err_console.print(f'{name}: {line["outcome"]} — {line["summary"]} (recorded in {path})')
    raise typer.Exit(ExitCode.CONVERGED if line['outcome'] == 'pass' else ExitCode.ISSUE)
