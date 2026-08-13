"""This tool's own config file, as this machine currently answers it.

The counterpart to `machines requirements`, which reads the *declaration*: this
reads the *resolution*. A register entry can be answered at three rungs and the
value alone does not say which one won, so a machine pointed at a stale registry
by an export somebody made in October behaves perfectly and reports nothing —
standards/configuration.md § "A resolved value reports which layer set it".

Only `check` printed the attribution before, and only on a finding, so a machine
where everything resolved had no way to ask which rung it resolved through.
"""

from __future__ import annotations

from pathlib import Path

import typer

from dotfiles import settings
from dotfiles.output import console
from dotfiles.output import emit_json

app = typer.Typer(no_args_is_help=True, help="This tool's own config file and what it resolves to")


@app.command('show')
def show(as_json: bool = typer.Option(False, '--json', help='Emit machine-readable output on stdout')) -> None:
    """Show what each setting resolves to, and which rung answered.

    Not a `cat` of config.toml. Two of the three rungs are environment variables
    and the file is the last of them, so what the file says and what the tool will
    do are different questions — and only the second one is ever the one being
    asked.
    """
    config = settings.read_config()
    path = settings.config_file()
    # Never through a Session, which needs a machine name: the state this is most
    # worth running in is one where ~/.env answered nothing, and resolving a
    # machine first would exit before printing why.
    described = settings.describe(config, Path.home() / '.env')

    if as_json:
        emit_json(
            {
                'config_file': str(path),
                'exists': path.is_file(),
                'problem': config.problem,
                'settings': [
                    {
                        'name': entry.name,
                        'value': entry.value,
                        'source': entry.source,
                        'exists': entry.exists,
                        'advice': entry.advice,
                    }
                    for entry in described
                ],
            }
        )
        return

    console.print(f'[bold]{path}[/]  {"" if path.is_file() else "not present"}')
    if config.problem:
        console.print(f'  [red]cannot be read[/] — {config.problem}')
    console.print()

    width = max((len(entry.name) for entry in described), default=0)
    for entry in described:
        if not entry.answered:
            console.print(f'  {entry.name:<{width}}  [yellow]nothing names it[/]')
            console.print(f'  {"":<{width}}  {entry.advice}')
            continue
        missing = '' if entry.exists else '  [yellow](no file there)[/]'
        console.print(f'  {entry.name:<{width}}  {entry.value}{missing}')
        console.print(f'  {"":<{width}}  from {entry.source}')
