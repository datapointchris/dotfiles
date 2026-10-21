"""What this machine has installed, as the document that travels to build a bundle.

The other half of the offline loop. `bundle` moves installers *to* the firewalled
box; this moves the one thing that has to come back — what it already has — so a
machine with a network can build it a bundle carrying only what it lacks.

**No new document type.** `docs/architecture/observability.md` already settled
that the interchange document is what `plan --json` and `check --json` emit. One
concept takes one word, so a third word for that record is a defect.
What is new is the *width*: this one covers the resources a bundle builder can act
on, and `scope` in the document says so. One schema, one version, one word.

The width is not a convenience. `check --json` carries the whole machine, and on
the box this exists for that includes a non-personal git identity and the
`WINDOWS_DOMAIN` in `~/.env` — `publishing` is where that reasoning lives, and the
gate it exports runs before any byte moves.
"""

from __future__ import annotations

import typer

from dotfiles import paths
from dotfiles import publishing
from dotfiles import remote as transport
from dotfiles import status as status_document
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import kept
from dotfiles.commands import limit_option
from dotfiles.commands import verbosity
from dotfiles.output import VERDICT_COLORS
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
from dotfiles.results import ResourceVerdict
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='What this machine has installed, for the machine that builds its bundles')

JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')
MachineOption = typer.Option(None, '--machine', help='Whose shelf to read (default: this machine)')


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

    **What `--json` prints is what would be sent**, screened rows and all, because
    the advice on a refusal says exactly that and a document shown unscreened would
    make it false. Which rows were withheld is therefore not a key in it: the
    document is the artifact, and a field describing the act of composing it would
    travel to the server as part of the thing it describes. A caller wanting the
    set diffs this against `plan --json`, which walks the same resources unscreened
    — and the *builder* needs nothing, because a row absent from the document is
    already `unmeasured` and gets carried.

    The verdict on the headline is about *publishability*, which is what this
    command's exit code answers; the resource rows below carry the machine's own.
    A headline reporting one while the exit reports the other leaves a reader
    working out which of two vocabularies a `3` came from.
    """
    verbosity(verbose, quiet)
    found = status_document.composed(machine)
    # Measured once and read by both doors, so the exit code and the rows cannot
    # disagree — a red issue row above a CONVERGED exit sends `status show &&
    # status upload` straight into a refusal the first command already found.
    # `remote check` derives its verdict from its faults the same way.
    screen = publishing.screened(found.document, publishing.identifying(found.trust))

    if as_json:
        emit_json(screen.document)
        raise typer.Exit(ExitCode.ISSUE if screen.problems else ExitCode.CONVERGED)

    word = 'issue' if screen.problems else str(ResourceVerdict.CONVERGED)
    console.print(section_line(VERDICT_MARKS[word], 'status', f'{found.machine} — {found.scope}', VERDICT_COLORS[word]))
    for result in found.results:
        render_row(str(result.verdict), result.address, result.detail)
    for name in screen.withheld:
        render_row('withheld', name, 'it carries a name that identifies this machine, so the row stays here')
    for problem in screen.problems:
        render_row('issue', 'unpublishable', problem, VERDICT_COLORS['issue'])
    raise typer.Exit(ExitCode.ISSUE if screen.problems else ExitCode.CONVERGED)


@app.command('upload')
def upload(
    machine: str = MachineOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Send this machine's status to the remote, so a bundle can be built from it.

    The gate runs before anything moves. A refusal here leaves nothing on the
    server: everything that can refuse runs before the first byte of data, which
    holds for a remote exactly as it holds for stdout.
    """
    verbosity(verbose, quiet)
    where = transport.reachable()
    published = status_document.publish(where, machine)

    success(f'uploaded {published.name} to {published.directory}')
    render_note(f'covering {published.composition.scope} and nothing else')
    # `warn`, not a note: `render_note` returns early under `-q`, so a publish that
    # dropped rows said nothing at all on the one invocation a script makes. A row
    # that did not travel is a warning about the artifact rather than evidence
    # under a verdict.
    for withheld in published.withheld:
        warn(f'{withheld} was left out of {published.name}: its version string names this machine')
    raise typer.Exit(ExitCode.CONVERGED)


def publish_after_apply(machine: str | None) -> None:
    """Publish this machine's status, where it asked for that to be automatic.

    Off unless `remote.publish_status_after_offline_apply` says otherwise, and the
    default is what a machine that declares nothing gets. The box this exists for
    sits on a monitored network where the concern is observation rather than
    capability, and a converge that reaches a server unasked is a change in
    posture — the loop is worth automating and is not worth automating quietly.

    **Every failure is a warning rather than an exit code, and that means every
    one.** The apply already succeeded and its verdict is about the machine;
    failing the run because a server did not answer would report a converged box as
    broken. Catching `Refusal` alone left the sentence false — this wraps a full
    offline survey plus `json.dumps`, a `write_text` and a `TemporaryDirectory`, so
    a read-only `/tmp` ended a converged apply in a traceback. The reasoning does
    not distinguish faults by class, so neither does the handler.
    """
    found = transport.read()
    if found.remote is None or not found.remote.publish_status_after_offline_apply:
        return
    try:
        published = status_document.publish(found.remote, machine)
    except Exception as failed:
        warn(f'this machine converged and its status was not published: {failed}')
        return
    render_note(f'published {published.name}, so the next bundle can be built against it')
    # Named here as `upload` names them. This is the path nobody is watching, so a
    # row dropped silently is one the builder then carries a tool for with nothing
    # anywhere recording why — degrading is right, degrading silently is not.
    for withheld in published.withheld:
        warn(f'{withheld} was left out of {published.name}: its version string names this machine')


@app.command('list')
def list_statuses(
    machine: str = MachineOption,
    limit: int | None = limit_option('statuses'),
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """List the statuses the remote holds for a machine, newest first."""
    verbosity(verbose, quiet)
    where = transport.reachable()
    named = machine or Session.resolve(None).machine_name
    listed = status_document.on_remote(where, named)
    # `on_remote` sorts newest first, so the newest statuses are at the front.
    shown = kept(listed, limit, newest_at='start')

    if as_json:
        emit_json({'machine': named, 'directory': transport.statuses_for(where, named), 'statuses': list(shown), 'total': len(listed)})
        raise typer.Exit(ExitCode.CONVERGED)

    word = str(ResourceVerdict.CONVERGED)
    console.print(section_line(VERDICT_MARKS[word], 'statuses', f'{len(listed)} for {named}', VERDICT_COLORS[word]))
    for name in shown:
        render_row(publishing.age_column(name), name, '')
    if limit is not None and len(listed) > limit:
        hint(f'see the rest with: dotfiles status list --machine {named}')
    raise typer.Exit(ExitCode.CONVERGED)


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
    nothing a person authored. A destructive operation requires an explicit flag,
    which scales the friction to the blast radius, and there is none here.
    """
    verbosity(verbose, quiet)
    where = transport.reachable()
    named = machine or Session.resolve(None).machine_name
    listed = status_document.on_remote(where, named)
    if not listed:
        error(f'the remote holds no status for {named} at {transport.statuses_for(where, named)}')
        hint(f'publish one from that machine with: dotfiles status upload --machine {named}')
        raise typer.Exit(ExitCode.ISSUE)

    wanted = status_name or listed[0]
    if wanted not in listed:
        raise typer.BadParameter(f'--status: {wanted} is not on the remote. Newest is {listed[0]}')

    destination = paths.status_cache() / wanted
    transport.pull(where, f'{transport.statuses_for(where, named)}/{wanted}', destination)

    if print_path:
        print(destination)
    else:
        success(f'downloaded {wanted} to {paths.under_home(destination)}')
        err_console.print('')
        hint(f'build against it with: dotfiles bundle create --machine {named} --arch ARCH --against {destination}')
    raise typer.Exit(ExitCode.CONVERGED)
