"""Whether each self-updating tool's last release check succeeded."""

from __future__ import annotations

from pathlib import Path

import typer

from dotfiles import updates
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import verbosity
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import err_console
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help="Self-updating tools' release checks, read from their state files")

JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')
StateOption = typer.Option(None, '--state', help='State root the tools are read beneath (overrides $XDG_STATE_HOME)')


@app.command('check')
def check(
    as_json: bool = JsonOption,
    state: Path | None = StateOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Report the tools whose last release check failed, or whose state file cannot be read.

    Exit 3 when any did, 0 when none did. A tool with no state file is not
    reported: its gate writes nothing until it checks. `-q` prints the summary
    alone, and `-v` adds a row for each tool that checked cleanly.
    """
    verbosity(verbose, quiet)
    found = updates.scan(state or updates.state_home())
    if as_json:
        emit_json(found)
    else:
        if not quiet:
            for tool in found['failing']:
                console.print(f'{tool["tool"]}  last checked {tool["checked_at"] or "never"}  {tool["last_error"]}')
            for name in found['unreadable']:
                console.print(f'{name}  state file present and unreadable')
        if verbose:
            for tool in found['checked']:
                if not tool['last_error']:
                    console.print(f'{tool["tool"]}  last checked {tool["checked_at"] or "never"}')
        err_console.print(found['summary'] or f'{len(found["checked"])} tools checked, none reported a failure ({found["state_home"]})')
    raise typer.Exit(ExitCode.ISSUE if found['summary'] else ExitCode.CONVERGED)
