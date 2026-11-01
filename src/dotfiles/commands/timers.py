"""The `user_timers` rows' runs. A unit starts `timers run`; a person can too."""

from __future__ import annotations

import json
import sys

import typer

from dotfiles import catalog
from dotfiles import timer_reports
from dotfiles.output import emit_json
from dotfiles.output import err_console
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='Commands this account runs on an interval, and what each run reported')

NameArgument = typer.Argument(..., help='The user_timers row to run')
JsonOption = typer.Option(False, '--json', help='Print the recorded line on stdout')


@app.command('run')
def run(name: str = NameArgument, as_json: bool = JsonOption) -> None:
    """Run one timer's command now and append what it did to the timer-reports file.

    Exit 0 when the command passed and 3 when it failed, so the unit that started
    it reads failed too. Exit 2 for a name no row declares.
    """
    rows = {entry.name: entry for entry in catalog.load().section('user_timers') if isinstance(entry, catalog.UserTimer)}
    entry = rows.get(name)
    if entry is None:
        err_console.print(f'no user_timers row is named {name!r}. Declared: {", ".join(sorted(rows)) or "none"}')
        raise typer.Exit(ExitCode.USAGE)
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
