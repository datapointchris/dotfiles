"""Offline bundles: this repo's installers, staged for a machine with no network.

It exists for a work box behind a firewall that cannot reach GitHub. The bundle
is built where the network is, for a machine that is not the one building it,
which is why neither `--machine` nor `--arch` has a default.

One group, for every machine. A Windows box is addressed by its own manifest and
built for like any other target, so its executables are a category inside the
bundle rather than a bundle of their own — `create_bundle.add_winget_binaries`
stages them beside the wheels and the release assets.
"""

from __future__ import annotations

import contextlib
import dataclasses as dc
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import typer

from dotfiles import coordinates as axes
from dotfiles import github_release
from dotfiles import machine as machines
from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import providers
from dotfiles import reconcile
from dotfiles import remote as transport
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import status as status_commands
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
from dotfiles.reconcile import ResourceVerdict
from dotfiles.refusal import Refusal
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

bundle_app = typer.Typer(no_args_is_help=True, help='Offline bundles for a machine with no network')


class BundleTransferError(Refusal):
    """A bundle that could not be moved, carrying the reason a person needs."""


JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')

ArchOption = typer.Option(None, '--arch', help='CPU of the machine that will install this bundle')
"""Module scope because the annotation is an enum.

B008 exempts a call in a default only where the annotation is an immutable
builtin, which `str` and `bool` are and `axes.Arch` cannot be shown to be. The
singleton is what its message asks for and what every other option here already
is."""


def _pointed_at(value: str | None, flag: str, options: Sequence[str], question: str, *, no_input: bool) -> str:
    """The value a flag carries, or the one a person points at in a list.

    Click's own `prompt=` does this in one argument and is not used, for a reason
    that showed up the moment it was tried: a prompt reaching EOF raises `Abort`,
    which click exits 1 on, and 1 is `DRIFT` here — the machine differs from its
    declaration. A pipeline that forgot a flag would report pending changes. A
    missing required value is `USAGE`, and `BadParameter` is what says so.

    Listed by number rather than asking for the name, because a manifest name is
    long, hyphenated and easy to typo, and the whole point of asking is that the
    caller did not have one to hand.

    A value that was passed is returned unexamined. Whether it names something
    real is the caller's question and is answered where that question already
    has one sentence — `machines.manifest_path` for a machine, the `axes.Arch`
    annotation for a CPU. Checking here as well is how one tool comes to answer
    "no such machine" two different ways.
    """
    if value is not None:
        return value
    if no_input or not sys.stdin.isatty():
        raise typer.BadParameter(f'{flag} is required without a terminal to ask. Valid: {", ".join(options)}')

    for index, option in enumerate(options, start=1):
        err_console.print(f'  [bold]{index}[/]  {option}')
    picked = typer.prompt(question, err=True, type=int)
    if not 1 <= picked <= len(options):
        raise typer.BadParameter(f'{flag}: pick 1 to {len(options)}, or pass the flag')
    return options[picked - 1]


@bundle_app.command('create')
def create(
    machine: str = typer.Option(None, '--machine', help='Machine manifest to build for'),
    # Typed as the enum rather than narrowed by a `click.Choice`, which is what it
    # was: typer renders `<x86_64|arm64>` in the help and rejects anything else
    # with exit 2 from the enum alone, and importing click to say the same thing
    # is a direct dependency on a package typer 0.27 stopped having.
    arch: axes.Arch = ArchOption,
    against: str = typer.Option(None, '--against', help="Build sparsely against a status document, or 'latest' to fetch one"),
    print_path: bool = typer.Option(False, '--print-path', help='Print the archive path on stdout, for a pipeline'),
    no_cache: bool = typer.Option(False, '--no-cache', help='Re-download every asset, ignoring the download cache'),
    no_input: bool = typer.Option(False, '--no-input', help='Never prompt; fail naming the flag that would have answered'),
) -> None:
    """Download every installer this repo needs into one archive.

    Neither value has a default, and it is the same reason for both: this runs
    where the network is, for a machine that is not this one. A default silently
    builds for whichever box was convenient when the default was written, and the
    only signal is a bundle that installs the wrong tools, days later, somewhere
    else.

    The OS is not asked for because the manifest declares it. The CPU is asked for
    because a manifest deliberately never says one — `coordinates.Arch` is
    measured, never declared, since no machine file states what processor a box
    has.

    Both are offered as a numbered list on a terminal. Neither blocks without one:
    without a TTY, or under `--no-input`, the usage error names the flag instead.

    `--no-cache` re-downloads every asset. Assets are kept for 90 days, so the
    one thing no other flag can reach is a cached file that is wrong — truncated,
    or a release republished under a tag it already used.

    **`--against` makes the build sparse**, and it parameterises the build rather
    than adding an effect to it: what changes is which installers are staged, not
    whether an archive is written. A tool the named status reports at the version
    upstream currently publishes is left out and recorded in `bundle.json` as
    measured, so the machine reading the bundle can tell that omission from a
    failure to carry it.

    `latest` fetches the newest status the remote holds for that machine, which is
    a read of the input rather than a second effect — the same act as opening the
    file a path names.
    """
    from dotfiles import create_bundle

    chosen_machine = _pointed_at(machine, '--machine', machines.names(), 'Machine this bundle is for', no_input=no_input)
    offered = [str(value) for value in axes.Arch]
    chosen_arch = _pointed_at(str(arch) if arch else None, '--arch', offered, "That machine's CPU", no_input=no_input)
    # The one sentence this tool has for a name nothing declares, rather than a
    # second one worded here. It names where it looked and lists what exists, and
    # `NoSuchMachine` carries USAGE, so it travels to the boundary as exit 2.
    machines.manifest_path(chosen_machine)

    built = create_bundle.build(chosen_machine, chosen_arch, use_cache=not no_cache, against=_status_for(against, chosen_machine))

    if print_path:
        print(built)
    raise typer.Exit(ExitCode.CONVERGED)


LATEST = 'latest'


def _status_for(named: str | None, machine: str) -> Path | None:
    """The status document a sparse build is planned against, or None for a full one.

    `latest` reaches the remote and everything else is a path. Resolved here rather
    than inside the builder, so the builder takes a file and nothing else — a
    module that reached a network to read its own input would have no way to be
    tested without one.
    """
    if named is None:
        return None
    if named != LATEST:
        found = Path(named)
        if not found.is_file():
            raise typer.BadParameter(f'--against: {found} is not a file. Fetch one with: dotfiles status download --machine {machine}')
        return found

    where = transport.require()
    listed = status_commands.remote_statuses(where, machine)
    if not listed:
        raise BundleTransferError(
            f'the remote holds no status for {machine}, so there is nothing to build sparsely against',
            code=ExitCode.ISSUE,
            advice=f'publish one from that machine with: dotfiles status upload --machine {machine}',
        )
    destination = paths.STATUS_CACHE / listed[0]
    transport.pull(where, f'{transport.statuses_for(where, machine)}/{listed[0]}', destination)
    return destination


@bundle_app.command('stage')
def stage(archive: str = typer.Argument(None, help='Path to a bundle archive (default: the newest one found)')) -> None:
    """Unpack a bundle so an install can read it, without installing anything.

    Named only where the default is wrong. A bundle's name carries a stamp nobody
    types, and the three directories searched are the ones a tarball is ever found
    in — the download cache, beside the checkout, and `$HOME`. That is the same
    discovery the bootstrap does, for the same reason.
    """
    found = Path(archive) if archive else offline_bundle.newest()
    if found is None:
        error(f'no bundle archive in {paths.ARCHIVE_DIR}, {Path.cwd()} or {Path.home()}, and none named')
        hint('fetch one with: dotfiles bundle download')
        raise typer.Exit(ExitCode.ISSUE)

    staged = offline_bundle.stage(found)

    success(f'staged {found.name} at {staged}')


@bundle_app.command('upload')
def upload(
    archive: str = typer.Argument(None, help='Path to a bundle archive (default: the newest one found)'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Send a bundle to the remote, so the machine it is for can fetch it.

    Its own verb rather than a flag on `create`, per standards/cli-design.md § "A
    flag never decides whether the command writes" — a push is a second effect
    rather than a parameter of the build, and a flag whose help has to explain
    what the command *becomes* is a verb. Nothing is lost to the split: this finds
    the newest archive itself, so the loop is `bundle create && bundle upload`
    rather than a substitution.

    A record is written beside the archive, carrying its size, its digest and what
    the bundle says it is. It is a few hundred bytes and it is what `download`
    reads to describe a bundle before spending the transfer on it.
    """
    verbosity(verbose, quiet)
    where = transport.require()
    found = Path(archive) if archive else offline_bundle.newest()
    if found is None:
        error(f'no bundle archive in {paths.ARCHIVE_DIR}, {Path.cwd()} or {Path.home()}, and none named')
        hint('build one with: dotfiles bundle create --machine NAME --arch ARCH')
        raise typer.Exit(ExitCode.ISSUE)

    record = offline_bundle.described_record(found)
    machine = record.description.machine
    if not machine:
        error(f'{found.name} does not say which machine it is for, so there is no shelf to put it on')
        hint('rebuild it: dotfiles bundle create --machine NAME --arch ARCH')
        raise typer.Exit(ExitCode.ISSUE)

    directory = transport.bundles_for(where, machine)
    with tempfile.TemporaryDirectory() as workspace:
        sidecar = Path(workspace) / f'{found.name}{offline_bundle.SIDECAR_SUFFIX}'
        sidecar.write_text(json.dumps(record.as_dict(), indent=2) + '\n')
        # The archive first. A record that arrives before the bytes it describes
        # is a row `bundle list` shows and `bundle download` then fails to fetch,
        # which reads as a broken remote rather than an interrupted upload.
        landed = transport.push(where, found, directory)
        transport.push(where, sidecar, directory)

    success(f'uploaded {found.name} to {landed.rsplit("/", 1)[0]}')
    _report_retention(where, directory)
    raise typer.Exit(ExitCode.CONVERGED)


def _report_retention(where: transport.Remote, directory: str) -> None:
    """Say what has accumulated, and never remove it.

    Reported rather than swept, so nothing this tool does as a side effect of an
    upload deletes bytes from a server. `bundle prune` is where that happens, and
    it is typed.
    """
    archives = [name for name in transport.names(where, directory) if not name.endswith(offline_bundle.SIDECAR_SUFFIX)]
    superseded = transport.superseded(tuple(archives), where.keep)
    if superseded:
        render_note(f'{len(superseded)} bundle(s) past the {where.keep} kept: oldest is {superseded[0]}')
        hint('remove them with: dotfiles bundle prune --remote')


@bundle_app.command('list')
def list_bundles(
    machine: str = typer.Option(None, '--machine', help='Whose shelf to read (default: this machine)'),
    limit: int = typer.Option(0, '--limit', '-n', help='Most recent N only (0 for all)'),
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """List the bundles the remote holds for a machine, newest first.

    Names only, because the name carries everything the ordering needs: a UTC
    stamp to the second, the manifest, the platform, and whether it is sparse.
    Reading the record for every row would be one transfer per bundle to answer
    a question the listing already answers.
    """
    verbosity(verbose, quiet)
    where = transport.require()
    named = machine or Session.resolve(None).machine_name
    listed = _remote_bundles(where, named)
    shown = listed[:limit] if limit else listed

    if as_json:
        emit_json({'machine': named, 'directory': transport.bundles_for(where, named), 'bundles': list(shown), 'total': len(listed)})
        raise typer.Exit(ExitCode.CONVERGED)

    word = str(ResourceVerdict.CONVERGED)
    console.print(section_line(VERDICT_MARKS[word], 'bundles', f'{len(listed)} for {named}', VERDICT_COLOURS[word]))
    for name in shown:
        render_row('remote', name, _age_of(name))
    if limit and len(listed) > limit:
        hint(f'see the rest with: dotfiles bundle list --machine {named}')
    raise typer.Exit(ExitCode.CONVERGED)


def _remote_bundles(where: transport.Remote, machine: str) -> tuple[str, ...]:
    """Every archive on a machine's shelf, newest first, records excluded."""
    directory = transport.bundles_for(where, machine)
    if not transport.exists(where, directory):
        return ()
    listed = transport.names(where, directory)
    return tuple(sorted((name for name in listed if name.endswith('.tar.gz')), reverse=True))


def _age_of(name: str) -> str:
    """How long ago a bundle was built, from the stamp in its own name.

    From the name rather than the record, so a listing costs one transfer however
    many rows it has. The name is what the stamp went into for this.
    """
    stamped = re.search(r'-v(\d{8}T\d{6}Z)-', name)
    if stamped is None:
        return 'built at an unrecorded time'
    built = dt.datetime.strptime(stamped.group(1), '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.UTC)
    return f'built {_elapsed(dt.datetime.now(dt.UTC) - built)} ago'


def _elapsed(since: dt.timedelta) -> str:
    """A duration in the largest unit that keeps it a small number.

    Rounded, and deliberately: the question is whether a bundle is fresh, and
    `3 days` answers it where `3 days, 4:07:19.284` makes a reader do arithmetic
    to reach the same conclusion.
    """
    if since.days >= 1:
        return f'{since.days} day(s)'
    hours = since.seconds // 3600
    return f'{hours} hour(s)' if hours else f'{max(since.seconds // 60, 0)} minute(s)'


@bundle_app.command('download')
def download(
    machine: str = typer.Option(None, '--machine', help='Whose shelf to read (default: this machine)'),
    bundle_name: str = typer.Option(None, '--bundle', help='Fetch this one rather than the newest'),
    yes: bool = typer.Option(False, '--yes', help='Skip the confirmation'),
    no_input: bool = typer.Option(False, '--no-input', help='Never prompt; fail naming the flag that would have answered'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Fetch a bundle from the remote into the local cache, and verify it.

    The newest by default, described and confirmed before the transfer rather
    than after: a bundle is hundreds of megabytes over a restricted network, and
    the thing worth knowing first is whether it was built for this machine and how
    long ago.

    The record beside it is fetched first — a few hundred bytes — and the digest
    it carries is checked against the archive that arrives. A truncated transfer
    otherwise surfaces as a corrupt tarball part way into an apply, which reads as
    a broken bundle rather than a failed download.

    Nothing is staged here. `bundle stage` unpacks, and keeping the two apart is
    what lets a download be repeated without disturbing what is already staged.
    """
    verbosity(verbose, quiet)
    where = transport.require()
    named = machine or Session.resolve(None).machine_name
    listed = _remote_bundles(where, named)
    if not listed:
        error(f'the remote holds no bundle for {named} at {transport.bundles_for(where, named)}')
        hint(f'build and send one where the network reaches: dotfiles bundle create --machine {named} --arch ARCH')
        raise typer.Exit(ExitCode.ISSUE)

    wanted = bundle_name or listed[0]
    if wanted not in listed:
        raise typer.BadParameter(f'--bundle: {wanted} is not on the remote. Newest is {listed[0]}')

    directory = transport.bundles_for(where, named)
    record = _fetched_record(where, directory, wanted)
    _describe(wanted, record, len(listed))
    if not _confirmed(wanted, yes=yes, no_input=no_input):
        error('nothing was downloaded')
        raise typer.Exit(ExitCode.ISSUE)

    destination = paths.ARCHIVE_DIR / wanted
    transport.pull(where, f'{directory}/{wanted}', destination)
    _verified(destination, record)

    success(f'downloaded {wanted} to {paths.under_home(destination)}')
    hint(f'stage it with: dotfiles bundle stage {destination}')
    raise typer.Exit(ExitCode.CONVERGED)


def _fetched_record(where: transport.Remote, directory: str, name: str) -> offline_bundle.Record:
    """The record beside an archive, or an empty one where the remote has none.

    Empty rather than refused: a bundle uploaded before records existed, or one
    whose record upload failed, is still installable. What that costs is the
    digest, and `_verified` says so rather than passing silently.
    """
    sidecar = f'{name}{offline_bundle.SIDECAR_SUFFIX}'
    with tempfile.TemporaryDirectory() as workspace:
        local = Path(workspace) / sidecar
        try:
            transport.pull(where, f'{directory}/{sidecar}', local)
            return offline_bundle.record_from(json.loads(local.read_text()))
        except (transport.RemoteError, OSError, ValueError):
            return offline_bundle.Record(name, 0, '')


def _describe(name: str, record: offline_bundle.Record, held: int) -> None:
    """The block a person decides from: what this is, when, and how big.

    Nudge density rather than browse density — identity, urgency and the command
    — per standards/cli-design.md § "A nudge is a different density from a browse
    view".
    """
    described = record.description
    err_console.print(f'[bold]{name}[/]')
    render_note(_age_of(name))
    if described.platform or described.machine:
        render_note(f'{described.platform or "platform unrecorded"} · for {described.machine or "an unrecorded machine"}')
    if described.sparse:
        measured = f', {len(described.current)} entry(s) measured current' if described.current else ''
        render_note(f'sparse, built against {described.built_from or "an unnamed status"}{measured}')
    if record.size:
        render_note(f'{record.size / (1024 * 1024):.1f} MB')
    if not record.sha256:
        render_note('no digest published for it, so nothing here can verify what arrives')
    render_note(f'{held} bundle(s) on the remote for this machine')


def _confirmed(name: str, *, yes: bool, no_input: bool) -> bool:
    """Whether to spend the transfer, asked the way every prompt here is asked.

    Not destructive by the test standards/cli-design.md § "Destructive operations
    require an explicit flag" applies — a download writes into a cache — so the
    default is no rather than the friction being higher. What it protects is the
    transfer itself, which on a restricted network is minutes.
    """
    if yes:
        return True
    if no_input or not sys.stdin.isatty():
        raise typer.BadParameter(f'--yes is required without a terminal to ask. Would have fetched {name}')
    return typer.confirm('Download this bundle?', default=False, err=True)


def _verified(archive: Path, record: offline_bundle.Record) -> None:
    """Refuse an archive whose digest does not match the record beside it.

    Deleted rather than left in the cache, because `newest` ranks by name and a
    corrupt archive would be the one every later run picks up — and it would win
    against the good bundle it was meant to replace.
    """
    if not record.sha256:
        return
    actual = github_release.sha256_of(archive)
    if not github_release.digests_match(record.sha256, actual):
        archive.unlink(missing_ok=True)
        raise BundleTransferError(
            f'{archive.name} does not match the digest its record publishes, so it did not arrive whole',
            code=ExitCode.ISSUE,
            advice='run it again: dotfiles bundle download',
        )
    render_note('digest matches the record on the remote')


@bundle_app.command('check')
def check(
    machine: str = typer.Option(None, '--machine', help='Machine manifest to resolve the plan from'),
    as_json: bool = JsonOption,
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Report which declared tools a staged bundle can and cannot install.

    The question `apply --offline` could not answer and had no business answering
    mid-run: an offline apply measures every installed tool against the bundle, so a
    bundle carrying nothing for a tool makes that tool unmeasurable — and eleven of
    those in a row read as a machine with nothing to say for itself. Asked here, the
    same fact is one line.

    Resolved against this machine's plan rather than against the whole declaration,
    so a tool this machine never subscribes to is not reported as a gap. That is the
    same narrowing `network check` makes, for the same reason: a miss has to name
    something this machine would really have failed to install.
    """
    verbosity(verbose, quiet)
    session = Session.resolve(machine, offline=True)

    staged = offline_bundle.describe()
    if not staged.readable:
        error(f'no readable bundle at {paths.under_home(staged.directory)}')
        hint('stage one with: dotfiles bundle stage PATH')
        raise typer.Exit(ExitCode.ISSUE)

    found = offline_bundle.coverage(staged, session.plan)
    if as_json:
        emit_json(
            {
                'bundle': str(staged.directory),
                'bundles': [path.name for path in staged.bundles],
                'built': staged.built,
                'sparse': staged.sparse,
                'covered': list(found.covered),
                'uncovered': list(found.uncovered),
                'measured': list(found.measured),
                'outside': found.outside,
            }
        )
        raise typer.Exit(ExitCode.DRIFT if found.uncovered else ExitCode.CONVERGED)

    reconcile.report_bundle(staged)
    for name in found.uncovered:
        render_row('uncovered', name, 'no staged bundle carries a file for it, so an offline run cannot measure or install it', 'yellow')
    for name in found.measured:
        # Not a gap and not covered. The bundle cannot install this one and does
        # not need to — and where the premise has since expired, because the tool
        # was reinstalled or downgraded, `plan --offline` reports it as drift
        # against this very version. That comparison is the report; a second one
        # here would be the same fact measured twice.
        render_row('measured', name, f'left out because this machine already had {staged.measured(name)}')
    bundlable = len(found.covered) + len(found.uncovered) + len(found.measured)
    console.print(f'{len(found.covered)} of {bundlable} bundlable item(s) staged  ·  {found.outside} installed by other means')
    if found.uncovered:
        # Both values real, so the line pastes. `ARCH` sat here and exited USAGE on
        # the very flag the hint was teaching. This runs on the machine that will
        # install, so its own CPU is the answer.
        hint(
            'build a newer bundle where the network reaches: '
            f'dotfiles bundle create --machine {session.machine_name} --arch {axes.detect_arch()}'
        )
    raise typer.Exit(ExitCode.DRIFT if found.uncovered else ExitCode.CONVERGED)


@bundle_app.command('show')
def show(as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption) -> None:
    """List what a staged bundle contains, by category.

    Sorted by category then name rather than in manifest order, because the manifest
    is written in the order the bundler downloaded things and a reader is looking for
    one tool.
    """
    verbosity(verbose, quiet)
    staged = offline_bundle.describe()
    if not staged.readable:
        error(f'no readable bundle at {paths.under_home(staged.directory)}')
        hint('stage one with: dotfiles bundle stage PATH')
        raise typer.Exit(ExitCode.ISSUE)

    if as_json:
        emit_json(
            {
                'bundle': str(staged.directory),
                'built': staged.built,
                'platform': staged.platform,
                'files': [dc.asdict(row) for row in staged.carried],
            }
        )
        raise typer.Exit(ExitCode.CONVERGED)

    reconcile.report_bundle(staged)
    for row in sorted(staged.carried, key=lambda one: (one.category, one.name)):
        render_row(row.category, row.name, f'{row.version}  {row.filename}')
    raise typer.Exit(ExitCode.CONVERGED)


@bundle_app.command('prune')
def prune(
    keep: int = typer.Option(0, '--keep', help='How many to retain (default: the remote.keep in config, or 5)'),
    remote_too: bool = typer.Option(False, '--remote', help="Also remove what is past the limit on the remote's shelf"),
    machine: str = typer.Option(None, '--machine', help='Whose remote shelf to sweep (default: this machine)'),
    yes: bool = typer.Option(False, '--yes', help='Skip the confirmation'),
    no_input: bool = typer.Option(False, '--no-input', help='Never prompt; fail naming the flag that would have answered'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Remove archives and staged bundles past the retention limit, oldest first.

    Local by default. `--remote` is separate and confirmed, because deleting from
    a server is the one thing here another machine can observe — and the machine
    running this is not always the one a bundle was built for.

    Archives and staged directories are swept together and to the same depth: a
    staged bundle whose archive is gone can still be installed from, and an
    archive whose staged directory is gone is one `bundle stage` away, so keeping
    the two in step is what makes the limit mean one thing.

    **The newest is never removed, whatever the limit.** A machine with nothing
    staged cannot converge offline at all, so a `--keep 0` that emptied the
    staging directory would take the machine's only way to install anything.
    """
    verbosity(verbose, quiet)
    retained = keep if keep else _configured_keep()
    swept = _prune_local(retained)
    for name in swept:
        render_row('removed', name, 'past the retention limit', 'yellow')

    if remote_too:
        _prune_remote(machine, retained, yes=yes, no_input=no_input)

    console.print(f'{len(swept)} removed locally, {retained} kept')
    raise typer.Exit(ExitCode.CONVERGED)


def _configured_keep() -> int:
    """The machine's own limit, or this tool's default where it declares none."""
    found = transport.read()
    return found.remote.keep if found.remote else transport.DEFAULT_KEEP


def _prune_local(keep: int) -> tuple[str, ...]:
    """Remove cached archives and staged bundles past the limit, and say which."""
    archives = tuple(sorted(path.name for path in paths.ARCHIVE_DIR.glob(offline_bundle.ARCHIVES))) if paths.ARCHIVE_DIR.is_dir() else ()
    staged = tuple(sorted(path.name for path in providers.staged_bundles()))

    removed = []
    for name in transport.superseded(archives, max(keep, 1)):
        (paths.ARCHIVE_DIR / name).unlink(missing_ok=True)
        (paths.ARCHIVE_DIR / f'{name}{offline_bundle.SIDECAR_SUFFIX}').unlink(missing_ok=True)
        removed.append(name)
    for name in transport.superseded(staged, max(keep, 1)):
        shutil.rmtree(paths.STAGING_DIR / name, ignore_errors=True)
        removed.append(name)
    return tuple(removed)


def _prune_remote(machine: str | None, keep: int, *, yes: bool, no_input: bool) -> None:
    """Remove what is past the limit on a machine's shelf, having said what first."""
    where = transport.require()
    named = machine or Session.resolve(None).machine_name
    directory = transport.bundles_for(where, named)
    superseded = transport.superseded(_remote_bundles(where, named), max(keep, 1))
    if not superseded:
        render_note(f'nothing on the remote for {named} is past the {keep} kept')
        return

    for name in superseded:
        render_row('superseded', name, _age_of(name), 'yellow')
    if not yes:
        if no_input or not sys.stdin.isatty():
            raise typer.BadParameter(f'--yes is required without a terminal to ask. Would have removed {len(superseded)} from {directory}')
        if not typer.confirm(f'Remove {len(superseded)} bundle(s) from {directory}?', default=False, err=True):
            error('nothing was removed from the remote')
            return

    for name in superseded:
        transport.remove(where, f'{directory}/{name}')
        # Best effort, and the asymmetry is deliberate: a record whose archive is
        # gone is a row `download` fails on, while an archive whose record is gone
        # is merely unverifiable. Refusing here would leave the first state behind.
        with contextlib.suppress(transport.RemoteError):
            transport.remove(where, f'{directory}/{name}{offline_bundle.SIDECAR_SUFFIX}')
    success(f'removed {len(superseded)} from {directory}')
