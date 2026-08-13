"""Asking whether this network can reach what a machine installs from.

One verb, because the question has one answer and `check` is already the word for
"report what is wrong". It writes nothing to the machine: the results file is a
rendering destination in the same family as `--json`, not a write the flag turns
on, and the default is a pure read like every other `check`.

**`--output` names the path rather than defaulting to the committed one, and that
is a safety property.** `install/offline/connectivity-results.txt` is the *work
box's* measurement, taken behind the firewall it describes, and the firewalled e2e
containers blackhole hosts based on it. A run on any unfirewalled machine finds
everything reachable, so a default output path would let a routine check on the
personal box silently replace the only record of what work blocks — and the
containers would then rehearse no firewall at all while still reporting green.

The measurement is what tells `bundle create` what an offline machine will need,
which is why this sits beside the bundler rather than among the resources — there
is no desired state here to converge on.
"""

from __future__ import annotations

import datetime as dt
import getpass
import platform
import socket
from pathlib import Path

import typer

from dotfiles import machine as machines
from dotfiles import network
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import verbosity
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import success
from dotfiles.output import warn
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='Whether this network reaches what this machine installs from')

MachineOption = typer.Option(None, '--machine', '-m', help='Measure what this manifest would install, not this machine')
OutputOption = typer.Option(None, '--output', '-o', help='Write the results file a bundle is planned from')
JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')


@app.command('check')
def check(
    machine_name: str | None = MachineOption,
    output: Path | None = OutputOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Probe every source this machine installs from, and report what is blocked.

    Exit 3 on a block rather than 0, so a scheduled run or a container assertion
    does not have to parse the output to learn the answer. A blocked source is a
    real finding: it means an install here would fail, or would need a bundle.
    """
    verbosity(verbose, quiet)
    try:
        machine = machines.load(machine_name) if machine_name else Session.resolve().machine
    except (machines.MachineError, FileNotFoundError) as unresolved:
        error(str(unresolved))
        raise typer.Exit(ExitCode.ISSUE) from unresolved

    measurement = network.measure_all(machine)
    verdicts = measurement.verdicts
    blocked = [verdict for verdict in verdicts if not verdict.reachable]

    if as_json:
        emit_json(
            {
                'machine': machine.name,
                'reachable': len(verdicts) - len(blocked),
                'blocked': len(blocked),
                'unprobed': list(measurement.unprobed),
                'probes': [
                    {
                        'section': verdict.probe.section,
                        'name': verdict.probe.name,
                        'target': verdict.probe.target,
                        'reach': str(verdict.probe.reach),
                        'reachable': verdict.reachable,
                        'landed': verdict.landed,
                        'refusal': verdict.refusal,
                    }
                    for verdict in verdicts
                ],
            }
        )
    else:
        for verdict in blocked:
            console.print(f'[red]blocked[/red]  {verdict.probe.section}/{verdict.probe.name}  {verdict.probe.target}')
            # Under the row rather than appended to it. The target is already the
            # longest field on a line that has to stay scannable, and the reason is
            # what turns a NO into an action — a refused connection wants a bundle
            # and an untrusted certificate wants a CA.
            if verdict.refusal:
                hint(verdict.refusal)
        for reason in measurement.unprobed:
            warn(reason)
        intercepted = [verdict for verdict in blocked if verdict.refusal and 'CA this machine trusts' in verdict.refusal]
        console.print(f'{len(verdicts) - len(blocked)} reachable, {len(blocked)} blocked')
        if intercepted:
            # Said once at the end as well as per row, because this is the one
            # refusal whose fix is a single act covering every row that shows it —
            # and the closing line is what a reader takes away from forty rows.
            warn(f'{len(intercepted)} host(s) were reachable but presented an untrusted certificate, which a bundle does not fix')
            hint('install the proxy CA and re-run: dotfiles network check')

    if output is not None:
        written = network.render(
            machine,
            measurement,
            host=socket.gethostname(),
            when=dt.datetime.now().astimezone().strftime('%a %d %b %Y %I:%M:%S %p %Z'),
            user=getpass.getuser(),
            system=f'{platform.system()} {platform.release()}',
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(written)
        success(f'results written to {output}')

    raise typer.Exit(ExitCode.ISSUE if blocked else ExitCode.CONVERGED)
