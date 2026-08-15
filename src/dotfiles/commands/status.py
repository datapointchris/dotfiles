"""What this machine has installed, as the document that travels to build a bundle.

The other half of the offline loop. `bundle` moves installers *to* the firewalled
box; this moves the one thing that has to come back — what it already has — so a
machine with a network can build it a bundle carrying only what it lacks.

**No new document type.** `docs/architecture/observability.md` already settled
that the interchange document is what `plan --json` and `check --json` emit, and
`help.md` § "One concept, one word" makes a third word for that record a defect.
What is new is the *width*: this one covers the resources a bundle builder can act
on, and `scope` in the document says so. One schema, one version, one word.

The width is not a convenience. `check --json` carries the whole machine, and on
the box this exists for that includes an employer git identity and the
`WINDOWS_DOMAIN` in `~/.env` — `publishing` is where that reasoning lives, and the
gate it exports runs before any byte moves.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path

import typer

from dotfiles import paths
from dotfiles import publishing
from dotfiles import reconcile
from dotfiles import remote as transport
from dotfiles import runs
from dotfiles import sinks
from dotfiles import status as status_document
from dotfiles import vocabulary
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import resolved
from dotfiles.commands import verbosity
from dotfiles.output import VERDICT_COLOURS
from dotfiles.output import VERDICT_MARKS
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import err_console
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import render_note
from dotfiles.output import render_row
from dotfiles.output import section_line
from dotfiles.output import success
from dotfiles.output import warn
from dotfiles.reconcile import ResourceVerdict
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='What this machine has installed, for the machine that builds its bundles')

JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')
MachineOption = typer.Option(None, '--machine', help='Whose shelf to read (default: this machine)')

PREFIX = 'dotfiles-status-v'
SUFFIX = '.json'


def discriminator() -> str:
    """Eight hex characters standing in for this box, carrying nothing of its name.

    Two machines legitimately share one manifest — `macos-personal-workstation` is
    both Macs — so a filename keyed on the manifest alone has one silently
    overwrite the other, which is the collision standards/data.md § "In a synced
    directory, every machine writes its own file" exists to make unreachable.

    A digest rather than the hostname that would ordinarily key it, because that
    hostname is an employer asset tag on the machine this feature exists for. The
    digest disambiguates and identifies nothing.
    """
    return hashlib.blake2b(paths.machine_id().encode(), digest_size=4).hexdigest()


def filename(machine: str, when: dt.datetime) -> str:
    stamped = when.astimezone(dt.UTC).strftime('%Y%m%dT%H%M%SZ')
    return f'{PREFIX}{stamped}-{machine}-{discriminator()}{SUFFIX}'


@dc.dataclass(frozen=True, slots=True)
class Composed:
    """The publishable document and the rows it was folded from.

    Both, because the two surfaces want different halves: `--json` wants the
    document exactly as it will travel, and the terminal wants the typed results,
    which reading them back out of the document would only cast to `object`.
    """

    document: dict[str, object]
    results: tuple[reconcile.ResourceResult, ...]
    machine: str

    @property
    def scope(self) -> str:
        return ', '.join(publishing.PUBLISHABLE)


def composed(machine: str | None) -> Composed:
    """The publishable document, and the machine it is about.

    Composed by walking with everything outside `publishing.PUBLISHABLE` skipped,
    which is the allowlist expressed through the narrowing the engine already has.
    A resource added to `vocabulary.RESOURCES` later is skipped here without anyone
    editing this, which is the direction the boundary has to fail in.

    `plan` rather than `check`: what a bundle builder wants is what would *change*,
    and `check` deliberately keeps a different set of findings.

    Rewritten `~`-rooted before it is returned. A row's evidence is usually the
    path a tool was found at, which carries the account name, and the account name
    is what the gate refuses — so an unrooted document refuses itself. A builder
    wants the version rather than which home it sat in, so nothing is lost.
    """
    named = resolved(machine).machine_name
    withheld = frozenset(vocabulary.RESOURCES) - frozenset(publishing.PUBLISHABLE)
    identity = runs.begin(named, 'plan')
    sinks.open_log(identity)
    walked = reconcile.survey(reconcile.Lens.PLAN, withheld, machine, report=None)
    sinks.keep(walked.events, identity, {'skip': sorted(withheld), 'offline': False})
    document = status_document.document(walked.results, named, identity.started, verb='plan')
    return Composed(publishing.rooted(document, str(Path.home())), tuple(walked.results), named)


@app.command('show')
def show(
    machine: str = MachineOption,
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Show what this machine has installed, in the shape a bundle is planned from.

    The same document `plan --json` emits, narrowed to the resources a bundle can
    act on. `scope` in it says which those are, so a reader never has to infer that
    an unmentioned resource has nothing rather than was not looked at.
    """
    verbosity(verbose, quiet)
    found = composed(machine)

    if as_json:
        emit_json(found.document)
        raise typer.Exit(ExitCode.CONVERGED)

    word = str(found.document['verdict'])
    console.print(section_line(VERDICT_MARKS[word], 'status', f'{found.machine} — {found.scope}', VERDICT_COLOURS[word]))
    for result in found.results:
        render_row(str(result.verdict), result.address, result.detail)
    for problem in publishing.redacted(found.document, publishing.identifying()):
        render_row('issue', 'unpublishable', problem, VERDICT_COLOURS['issue'])
    raise typer.Exit(ExitCode.CONVERGED)


@app.command('upload')
def upload(
    machine: str = MachineOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Send this machine's status to the remote, so a bundle can be built from it.

    The gate runs before anything moves. A refusal here leaves nothing on the
    server, which is the property `standards/cli-design.md` § "Everything that can
    refuse runs before the first byte of data" states about stdout and means the
    same about a remote.
    """
    verbosity(verbose, quiet)
    where = transport.reachable()
    found = composed(machine)
    publishing.refuse_unpublishable(found.document)

    name = filename(found.machine, dt.datetime.now(dt.UTC))
    directory = transport.statuses_for(where, found.machine)
    with tempfile.TemporaryDirectory() as workspace:
        local = Path(workspace) / name
        local.write_text(json.dumps(found.document, indent=2) + '\n')
        transport.push(where, local, directory)

    success(f'uploaded {name} to {directory}')
    render_note(f'covering {found.scope} and nothing else')
    raise typer.Exit(ExitCode.CONVERGED)


def publish_after_apply(machine: str | None) -> None:
    """Publish this machine's status, where it asked for that to be automatic.

    Off unless `remote.publish_status_after_offline_apply` says otherwise, and the
    default is what a machine that declares nothing gets. The box this exists for
    sits on an employer network where the concern is monitoring rather than
    capability, and a converge that reaches a server unasked is a change in
    posture — the loop is worth automating and is not worth automating quietly.

    Every failure is a warning rather than an exit code. The apply already
    succeeded and its verdict is about the machine; failing the run because a
    server did not answer would report a converged box as broken. The gate is the
    one exception in spirit and not in mechanism: it refuses, the refusal is
    reported here, and nothing leaves.
    """
    found = transport.read()
    if found.remote is None or not found.remote.publish_status_after_offline_apply:
        return
    try:
        composition = composed(machine)
        publishing.refuse_unpublishable(composition.document)
        name = filename(composition.machine, dt.datetime.now(dt.UTC))
        with tempfile.TemporaryDirectory() as workspace:
            local = Path(workspace) / name
            local.write_text(json.dumps(composition.document, indent=2) + '\n')
            transport.push(found.remote, local, transport.statuses_for(found.remote, composition.machine))
    except Refusal as refused:
        warn(f'this machine converged and its status was not published: {refused}')
        return
    render_note(f'published {name}, so the next bundle can be built against it')


@app.command('list')
def list_statuses(
    machine: str = MachineOption,
    limit: int = typer.Option(0, '--limit', '-n', help='Most recent N only (0 for all)'),
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """List the statuses the remote holds for a machine, newest first."""
    verbosity(verbose, quiet)
    where = transport.reachable()
    named = machine or resolved(None).machine_name
    listed = remote_statuses(where, named)
    shown = listed[:limit] if limit else listed

    if as_json:
        emit_json({'machine': named, 'directory': transport.statuses_for(where, named), 'statuses': list(shown), 'total': len(listed)})
        raise typer.Exit(ExitCode.CONVERGED)

    word = str(ResourceVerdict.CONVERGED)
    console.print(section_line(VERDICT_MARKS[word], 'statuses', f'{len(listed)} for {named}', VERDICT_COLOURS[word]))
    for name in shown:
        render_row('remote', name, '')
    if limit and len(listed) > limit:
        hint(f'see the rest with: dotfiles status list --machine {named}')
    raise typer.Exit(ExitCode.CONVERGED)


def remote_statuses(where: transport.Remote, machine: str) -> tuple[str, ...]:
    """Every status on a machine's shelf, newest first.

    Public because `bundle create --against latest` resolves one through it, and a
    second listing written there would be a second place the naming is known.
    """
    directory = transport.statuses_for(where, machine)
    if not transport.exists(where, directory):
        return ()
    listed = transport.names(where, directory)
    return tuple(sorted((name for name in listed if name.startswith(PREFIX) and name.endswith(SUFFIX)), reverse=True))


@app.command('download')
def download(
    machine: str = MachineOption,
    status_name: str = typer.Option(None, '--status', help='Fetch this one rather than the newest'),
    print_path: bool = typer.Option(False, '--print-path', help='Print the local path on stdout, for a pipeline'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Fetch a machine's status into the local cache, to build a sparse bundle from.

    No confirmation, deliberately: this is a few kilobytes and it overwrites
    nothing a person authored. `standards/cli-design.md` § "Destructive operations
    require an explicit flag" scales the friction to the blast radius, and there
    is none here — the same reasoning its own Known-gaps section records for
    `ifiles shares rm`.
    """
    verbosity(verbose, quiet)
    where = transport.reachable()
    named = machine or resolved(None).machine_name
    listed = remote_statuses(where, named)
    if not listed:
        error(f'the remote holds no status for {named} at {transport.statuses_for(where, named)}')
        hint(f'publish one from that machine with: dotfiles status upload --machine {named}')
        raise typer.Exit(ExitCode.ISSUE)

    wanted = status_name or listed[0]
    if wanted not in listed:
        raise typer.BadParameter(f'--status: {wanted} is not on the remote. Newest is {listed[0]}')

    destination = paths.STATUS_CACHE / wanted
    transport.pull(where, f'{transport.statuses_for(where, named)}/{wanted}', destination)

    if print_path:
        print(destination)
    else:
        success(f'downloaded {wanted} to {paths.under_home(destination)}')
        err_console.print('')
        hint(f'build against it with: dotfiles bundle create --machine {named} --arch ARCH --against {destination}')
    raise typer.Exit(ExitCode.CONVERGED)
