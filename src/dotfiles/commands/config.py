"""This tool's own config file, as this machine currently answers it.

The counterpart to `machines requirements`, which reads the *declaration*: this
reads the *resolution*. A register entry can be answered at three rungs and the
value alone does not say which one won, so a machine pointed at a stale registry
by an export somebody made in October behaves perfectly and reports nothing. A
resolved value reports which layer set it.

Only `check` printed the attribution before, and only on a finding, so a machine
where everything resolved had no way to ask which rung it resolved through.
"""

from __future__ import annotations

from pathlib import Path

import typer

from dotfiles import remote as transport
from dotfiles import settings
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.providers import schedule

app = typer.Typer(no_args_is_help=True, help="This tool's own config file and what it resolves to")


@app.command('show')
def show(as_json: bool = typer.Option(False, '--json', help='Emit machine-readable output on stdout')) -> None:
    """Show what each setting resolves to, and which rung answered.

    Not a `cat` of config.toml. Two of the three rungs are environment variables
    and the file is the last of them, so what the file says and what the tool will
    do are different questions — and only the second one is ever the one being
    asked.

    The remote is reported here beside the registers even though it resolves
    through one rung rather than three. It is the only other thing this file
    answers, and a reader sent here by a refusal that could not find one arrives
    asking what is declared — an answer that omitted it would send them to `cat`
    after all.

    The schedule is here for a sharper version of the same reason. It decides
    whether a background process runs on this machine and reaches the network on
    its own, and it is the one setting whose effect is invisible from the terminal
    that set it — so the question "does this box run a timer" has to be answerable
    without reading a unit file. `schedule.INTERVAL_SECONDS` is how often.
    """
    config = settings.read_config()
    path = settings.config_file()
    remote = transport.read(config)
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
                'remote': {
                    'declared': remote.declared,
                    'problem': remote.problem,
                    'root': remote.remote.root if remote.remote else '',
                    'program': remote.remote.transport.program if remote.remote else '',
                    'operations': sorted(str(name) for name in remote.remote.transport.commands) if remote.remote else [],
                    'keep_bundles': remote.remote.keep_bundles if remote.remote else 0,
                    'from_table': sorted(remote.remote.from_table) if remote.remote else [],
                    **{name: bool(remote.remote and getattr(remote.remote, name)) for name in transport.FLAGS},
                },
                'schedule': {'enabled': schedule.enabled(config)},
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

    console.print()
    console.print(f'  {"REMOTE":<{width}}  {_remote(remote)}')
    if remote.remote:
        console.print(f'  {"":<{width}}  via {remote.remote.transport.program}, keeping {remote.remote.keep_bundles}')
        console.print(f'  {"":<{width}}  {_kept_from(remote.remote)}')
        # Every setting in the table, read from the one list that names them.
        # These decide whether a document leaves the machine unasked, which is at
        # least as worth seeing as a retention count.
        for name in transport.FLAGS:
            console.print(f'  {"":<{width}}  {name} {"on" if getattr(remote.remote, name) else "off"} ({_layer(remote.remote, name)})')

    console.print()
    wanted = schedule.enabled(config)
    stated = isinstance(config.values.get(schedule.TABLE), dict) and 'enabled' in config.values[schedule.TABLE]
    console.print(f'  {"SCHEDULE":<{width}}  {"a check every " + schedule.cadence() if wanted else "no periodic check"}')
    console.print(
        f'  {"":<{width}}  {schedule.TABLE}.enabled {"on" if wanted else "off"} ({str(path) if stated else "this tool’s default"})'
    )


def _layer(found: transport.Remote, key: str) -> str:
    """Which layer decided one setting, the way the registers above say it.

    A resolved value reports which layer set it, and the failure this prevents is a
    plausible value rather than a wrong one. These govern deletion from a server and
    whether a document leaves the machine unasked, and unattributed beside rows that
    all carry `from {source}` they read as declared on a machine that declared
    nothing.
    """
    return f'from {transport.TABLE}.{key}' if key in found.from_table else 'this tool’s default'


def _kept_from(found: transport.Remote) -> str:
    return _layer(found, 'keep_bundles')


def _remote(found: transport.Configured) -> str:
    """One line for the remote, saying which of its three states this machine is in."""
    if found.problem:
        return f'[red]cannot be read[/] — {found.problem.splitlines()[0]}'
    if found.remote is None:
        return f'[yellow]{transport.UNCONFIGURED}[/]'
    return found.remote.root
