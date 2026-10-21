"""Asking whether this network can reach what a machine installs from.

One verb, because the question has one answer and `check` is already the word for
"report what is wrong". It writes nothing to the machine: the results file is a
rendering destination in the same family as `--json`, not a write the flag turns
on, and the default is a pure read like every other `check`.

**`--output` has no default, and that is a property rather than an omission.** A
rendered measurement is one machine's answer on one day, and it can only be
re-taken from the same network — so committed it goes stale where nothing can
refresh it, and `tests/install/test_network.py` asserts none is tracked. A default
path is how one arrives anyway: it turns a routine check into a write, and the
write lands in a working tree somebody later commits without reading.

Nothing here decides what the firewalled e2e containers block. That is declared
in `tests/e2e/harness.py`, against a plan resolved from the manifest, so the
rehearsal needs no record of any real network.

The measurement is what tells `bundle create` what an offline machine will need,
which is why this sits beside the bundler rather than among the resources — there
is no desired state here to converge on.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import platform
import time
from collections.abc import Sequence
from pathlib import Path

import typer

from dotfiles import catalog
from dotfiles import coordinates
from dotfiles import machine as machines
from dotfiles import network
from dotfiles import paths
from dotfiles import registry
from dotfiles import resolve
from dotfiles import routing
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import verbosity
from dotfiles.output import SUBJECT_COLUMN
from dotfiles.output import VERDICT_COLORS
from dotfiles.output import VERDICT_MARKS
from dotfiles.output import Phrase
from dotfiles.output import console
from dotfiles.output import elapsed
from dotfiles.output import emit_json
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import render_advice
from dotfiles.output import render_row
from dotfiles.output import render_verdict
from dotfiles.output import section_line
from dotfiles.output import success
from dotfiles.output import tally
from dotfiles.results import ResourceVerdict
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
    except machines.NoSuchMachine as unknown:
        raise typer.BadParameter(str(unknown)) from unknown
    except (machines.MachineError, FileNotFoundError) as unresolved:
        error(str(unresolved))
        raise typer.Exit(ExitCode.ISSUE) from unresolved

    # Clocked, because the report says what the wait bought. Forty-odd hosts at a
    # timeout each is the one command here that a reader sits through, and every
    # other section in this tool already reports what measuring it cost.
    started = time.monotonic()
    measurement = network.measure_all(machine)
    seconds = time.monotonic() - started
    verdicts = measurement.verdicts
    blocked = [verdict for verdict in verdicts if not verdict.reachable]
    found = declared(machine, measurement)

    if as_json:
        emit_json(
            {
                'machine': machine.name,
                'reachable': len(verdicts) - len(blocked),
                'blocked': len(blocked),
                # The wait is the one thing this verb costs, and the human line
                # reports it — so a caller that cannot see the screen has a door to
                # it too, as `ResourceResult.as_counts` gives every other section.
                # The results file is no substitute: it records `when`, not how long.
                'seconds': round(seconds, 3),
                'unprobed': list(measurement.unprobed),
                'declared': {
                    'source': found.routes.source,
                    'blocked': sorted(found.routes.blocked),
                    'undeclared': list(found.undeclared),
                    'answered': list(found.answered),
                    'items': found.reaching,
                },
                'probes': [
                    {
                        'section': verdict.probe.section,
                        'name': verdict.probe.name,
                        'target': verdict.probe.target,
                        'reach': str(verdict.probe.reach),
                        'reachable': verdict.reachable,
                        'landed': verdict.landed,
                        'refusal': str(verdict.refusal),
                        'refusal_detail': verdict.detail,
                    }
                    for verdict in verdicts
                ],
            }
        )
    else:
        render(machine.name, measurement, blocked, seconds, found)

    if output is not None:
        written = network.render(
            machine,
            measurement,
            when=dt.datetime.now().astimezone().strftime('%a %d %b %Y %I:%M:%S %p %Z'),
            system=f'{platform.system()} {platform.release()}',
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(written)
        success(f'results written to {output}')

    raise typer.Exit(ExitCode.ISSUE if blocked else ExitCode.CONVERGED)


def render(
    machine_name: str, measurement: network.Measurement, blocked: Sequence[network.ProbeResult], seconds: float, found: Declared
) -> None:
    """The probe run as a section, its refusals as rows, and one closing verdict.

    This is a `check`, so it reads beside the reconcile verbs and is written in
    their grammar: a mark, so a converged run and a blocked one do not open the same
    way; a name, so the counts belong to something; an elapsed, after the longest
    read in the tool; and a closing command, on the one screen whose whole purpose
    is to say what to do about a firewall. A tally alone at column 0 has none of
    them.

    **`N reachable, M blocked` is the section's detail, word for word.** It is the
    same phrase `network.render` puts on the results file's `Summary:` line, so
    rewording it here would leave the screen and the file it writes disagreeing
    about one measurement.

    **The verdict is the enum rather than the two words spelled here.** Every other
    caller of `VERDICT_MARKS` and `VERDICT_COLORS` keys them on `str(...)` of a
    member, and a literal that misses a rename lands as a `KeyError` on whoever runs
    this command. `output.MATCHED` is the shape a deliberate literal takes — a
    named constant with a test asserting it agrees with the member it stands in for
    — and there is nothing here that reading the member does not already give.

    The rows are on stderr, as the evidence for the line above.
    """
    intercepted = [verdict for verdict in blocked if verdict.refusal is network.Refusal.INTERCEPTED]
    reachable = len(measurement.verdicts) - len(blocked)
    verdict_word = str(ResourceVerdict.ISSUE if blocked else ResourceVerdict.CONVERGED)
    console.print(
        section_line(
            VERDICT_MARKS[verdict_word],
            'network',
            f'{reachable} reachable, {len(blocked)} blocked',
            VERDICT_COLORS[verdict_word],
            f'{tally((len(measurement.unprobed), Phrase.UNPROBED))}{elapsed(seconds)}',
        )
    )

    width = max([SUBJECT_COLUMN, *(len(f'{one.probe.section}/{one.probe.name}') for one in blocked)])
    for verdict in blocked:
        render_row('blocked', f'{verdict.probe.section}/{verdict.probe.name}', verdict.probe.target, 'red', width)
        # Under the row rather than appended to it. The target is already the
        # longest field on a line that has to stay scannable, and the reason is
        # what turns a NO into an action — a refused connection wants a bundle
        # and an untrusted certificate wants a CA.
        if verdict.detail:
            render_advice(verdict.detail, width)
    for reason in measurement.unprobed:
        # Nothing to ask rather than asked and refused, which is the same
        # distinction `unmeasured` carries everywhere else in this report.
        #
        # The same member the tally above counts with, because it is the same word
        # for the same set on the same screen. A literal here reworded only the
        # rows or only the count, and the two sit three lines apart.
        render_row(Phrase.UNPROBED, '', reason, 'magenta', width)
    render_declared(found, max([width, *(len(host) for host in (*found.reaching, *found.undeclared, *found.answered))]))

    console.print()
    standing = Phrase.CANNOT_INSTALL if blocked else Phrase.CAN_INSTALL
    render_verdict(verdict_word, machine_name, standing, closing(len(blocked), len(intercepted)), console)
    if intercepted:
        # Said once at the end as well as per row, because this is the one
        # refusal whose fix is a single act covering every row that shows it —
        # and the closing line is what a reader takes away from forty rows.
        hint('install the proxy CA and re-run: dotfiles network check')


@dc.dataclass(frozen=True, slots=True)
class Declared:
    """The measurement set beside the hosts this machine's config declares blocked."""

    routes: routing.Routes
    undeclared: tuple[str, ...]
    """Refused here, but not declared, so an apply asks the network and fails."""

    answered: tuple[str, ...]
    """Declared blocked, but answered here, so an apply takes from the bundle what the network serves."""

    reaching: dict[str, tuple[str, ...]]
    """Each declared host, and the items whose version check or download reaches it."""


def declared(machine: machines.Machine, measurement: network.Measurement) -> Declared:
    """Compare what refused against `[network] blocked`, and name what each declared host affects.

    Read through `registry.hosts`, the same answer an apply routes by, so the two
    cannot name different hosts for one item.
    """
    routes = routing.read(offline=False, declared_at=routing.trust_copy(paths.REPO_ROOT, machine.coordinates.network_trust))
    refused = {verdict.landed or verdict.probe.host for verdict in measurement.verdicts if not verdict.reachable}
    answered = {host for verdict in measurement.verdicts if verdict.reachable for host in (verdict.probe.host, verdict.landed) if host}
    target = coordinates.target_for(machine.coordinates)
    items = resolve.resolve(catalog.load(), machine).items
    return Declared(
        routes,
        tuple(sorted(refused - routes.blocked)),
        tuple(sorted(routes.blocked & answered)),
        {host: tuple(item.address for item in items if host in registry.hosts(item, target).every) for host in sorted(routes.blocked)},
    )


def render_declared(found: Declared, width: int) -> None:
    """One row per declared host with the items it sends to the bundle, then each disagreement."""
    where = found.routes.source or 'no config'
    for host, items in found.reaching.items():
        render_row(
            'declared', host, f'{len(items)} item(s) reach it: {", ".join(items)}' if items else 'no item reaches it', 'yellow', width
        )
    for host in found.undeclared:
        render_row(
            'undeclared', host, f'refused here, but {where} does not declare it blocked, so an apply asks it and fails', 'red', width
        )
    for host in found.answered:
        render_row(
            'answered',
            host,
            f'answered here, but {where} declares it blocked, so an apply takes from the bundle what it serves',
            'red',
            width,
        )


def closing(blocked: int, intercepted: int) -> str:
    """What a blocked network means for installing here, and the command that answers it.

    **The bundle is built elsewhere, so the command is named for the machine that
    can run it.** Pointing a blocked box at `dotfiles bundle create` and leaving it
    there is an instruction that fails on the machine reading it; the sentence
    carries the where, and the command stays last so it survives a copy-paste.

    An intercepted host is called out separately because a bundle does not fix it.
    The connection succeeded and the certificate was somebody else's, so the answer
    is a CA rather than a tarball — which is the one distinction a reader of forty
    identical-looking `blocked` rows would otherwise have to find for themselves.
    """
    if not blocked:
        return 'every source this machine installs from is reachable'
    proxied = f' ({intercepted} of them presented an untrusted certificate, which a bundle does not fix)' if intercepted else ''
    return f'{blocked} source(s) unreachable{proxied}, so installing here needs a bundle built elsewhere; run: dotfiles bundle create'
