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
from dotfiles import machine as machines
from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import providers
from dotfiles import publishing
from dotfiles import reconcile
from dotfiles import remote as transport
from dotfiles import status as status_document
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
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
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

bundle_app = typer.Typer(no_args_is_help=True, help='Offline bundles for a machine with no network')


class BundleTransferError(Refusal):
    """A bundle that could not be moved, carrying the reason a person needs."""


JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')

KeepOption = typer.Option(
    None,
    '--keep',
    help=f'How many to retain per machine (default: remote.keep_bundles in config, or {transport.DEFAULT_KEEP})',
)
"""Interpolated rather than typed, so changing the default cannot leave the help wrong.

standards/help.md § "Never write a sentence a later release will make false" — a
copied constant is a sentence with nothing checking it."""

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
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
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

    verbosity(verbose, quiet)
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

    **A remote holding no status for that machine builds a full bundle, and says
    so.** `latest` means "whatever the remote has", and nothing is a legitimate
    answer to that — it is the state of every machine before its first status is
    published, which is exactly when somebody is running this for the first time.
    Refusing there costs them a second command to learn that the loop has to be
    primed.

    What makes the fallback safe is that it is announced *and* the artefact says
    it for itself: the archive is not named `-sparse` and its `bundle.json` reads
    `completeness: full`. The failure this feature exists to avoid is a bundle
    that carries everything while reporting itself sparse, and nothing about this
    path can produce one.

    **A transport that will not answer still refuses**, and `reachable` is what
    tells the two apart. Falling back there would build a full bundle on a run
    where a perfectly good status was sitting on a server nobody could reach —
    quietly turning a network blip into half an hour of downloads. The probe is
    retried before that conclusion is drawn, because one dropped packet is not an
    outage.

    Past this point the distinction stops being worth drawing. The shelf directory
    missing and the shelf being empty both mean "nothing has been published for
    this machine", and both build a full bundle — which is what every build did
    before any of this existed.
    """
    if named is None:
        return None
    if named != LATEST:
        found = Path(named)
        if not found.is_file():
            raise typer.BadParameter(f'--against: {found} is not a file. Fetch one with: dotfiles status download --machine {machine}')
        return found

    where = transport.reachable()
    listed = status_document.on_remote(where, machine)
    if not listed:
        warn(f'the remote holds no status for {machine}, so this builds a full bundle')
        hint(f'publish one from that machine to make the next build sparse: dotfiles status upload --machine {machine}')
        return None
    # Which box wrote it, not just which manifest. Two machines legitimately share
    # one — `macos-personal-workstation` is both Macs — and that is exactly why a
    # status filename carries a digest of the hostname. Nothing here can tell
    # which of them a bundle is for, so picking the most recent would diff one
    # Mac's plan against the other's installed set and report the result as
    # measured.
    published = {publishing.wrote(name) for name in listed}
    if len(published) > 1:
        # Every candidate with the box that wrote it, rather than the newest
        # pre-filled. Pasting one made the refusal's own remedy the route into the
        # ambiguity it had just declined to resolve — `help.md` § "An example says
        # what it is for, not just what to type".
        newest_per_box = {publishing.wrote(name): name for name in reversed(listed)}
        offered = '\n'.join(f'  {box or "an unrecognised box"}: --status {name}' for box, name in sorted(newest_per_box.items()))
        raise typer.BadParameter(
            f'--against latest: {len(published)} machines share the {machine} manifest and have published, '
            f'so "latest" does not name one. Fetch the one you mean:\n'
            f'  dotfiles status download --machine {machine} --status NAME --print-path\n{offered}'
        )

    destination = paths.status_cache() / listed[0]
    transport.pull(where, f'{transport.statuses_for(where, machine)}/{listed[0]}', destination)
    return destination


@bundle_app.command('stage')
def stage(
    archive: str = typer.Argument(None, help='Path to a bundle archive (default: the newest one found)'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Unpack a bundle so an install can read it, without installing anything.

    Named only where the default is wrong. A bundle's name carries a stamp nobody
    types, and the three directories searched are the ones a tarball is ever found
    in — the download cache, beside the checkout, and `$HOME`. That is the same
    discovery the bootstrap does, for the same reason.
    """
    verbosity(verbose, quiet)
    # Filtered to this machine, because a peer's archive downloaded to look at
    # would otherwise sort newest, be picked here, and be refused a line later.
    found = Path(archive) if archive else offline_bundle.newest(machine=offline_bundle.target())
    if found is None:
        error(f'no bundle archive in {paths.archive_dir()}, {Path.cwd()} or {Path.home()}, and none named')
        hint('fetch one with: dotfiles bundle download')
        raise typer.Exit(ExitCode.ISSUE)

    # A named path that is not there is the caller's mistake, which is USAGE. It
    # reached `stage` and came back as ISSUE, so a typo read to a caller as a
    # machine fault. `upload` above answers the same question the same way.
    if archive and not found.is_file():
        raise typer.BadParameter(f'{found} is not a file', param_hint='ARCHIVE')

    staged = offline_bundle.stage(found, offline_bundle.target())

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
    where = transport.reachable()
    found = Path(archive) if archive else offline_bundle.newest()
    if found is None:
        error(f'no bundle archive in {paths.archive_dir()}, {Path.cwd()} or {Path.home()}, and none named')
        hint('build one with: dotfiles bundle create --machine NAME --arch ARCH')
        raise typer.Exit(ExitCode.ISSUE)

    # Before `described_record`, which stats it. A named path that is not there is
    # the caller's mistake and exits USAGE; an unhandled `FileNotFoundError` here
    # would land on 1, and 1 is DRIFT — a verdict rather than a failure.
    if not found.is_file():
        raise typer.BadParameter(f'{found} is not a file', param_hint='ARCHIVE')

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
    _report_retention(where, machine)
    raise typer.Exit(ExitCode.CONVERGED)


def _report_retention(where: transport.Remote, machine: str) -> None:
    """Say what has accumulated, and never remove it.

    Reported rather than swept, so nothing this tool does as a side effect of an
    upload deletes bytes from a server. `bundle prune` is where that happens, and
    it is typed.

    **Nothing here may change the verb's exit code.** The archive and its record
    have already landed by the time this runs and `success` has already printed, so
    a `RemoteError` from the listing reported a completed upload as a failure and
    invited a caller to send it again. `_prune_remote` suppresses the same class
    for the same reason.

    Counted through `on_remote` and `retention`, which is what `prune --remote`
    will use, so the number named here is the number that command acts on.
    """
    with contextlib.suppress(transport.RemoteError):
        sweep = offline_bundle.retention(offline_bundle.on_remote(where, machine), where.keep_bundles)
        if sweep.superseded:
            render_note(f'{len(sweep.superseded)} bundle(s) past the {where.keep_bundles} kept: oldest is {sweep.superseded[0]}')
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
    where = transport.reachable()
    named = machine or Session.resolve(None).machine_name
    listed = offline_bundle.on_remote(where, named)
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

    Clamped at zero first. `timedelta` normalises a negative by borrowing, so five
    minutes in the future is `days=-1, seconds=86100` and reads as 23 hours ago.
    The builder stamps the name and the offline box renders this, so a few minutes
    of skew between two machines is ordinary — and freshness is the whole content
    of the `bundle download` confirmation, misreported in the direction that
    argues against downloading.
    """
    since = max(since, dt.timedelta(0))
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
    where = transport.reachable()
    named = machine or Session.resolve(None).machine_name
    listed = offline_bundle.on_remote(where, named)
    if not listed:
        error(f'the remote holds no bundle for {named} at {transport.bundles_for(where, named)}')
        # This runs on the machine that will install, so its own CPU is the
        # target's. `ARCH` here exits USAGE on the very flag it is teaching.
        hint(f'build and send one where the network reaches: dotfiles bundle create --machine {named} --arch {axes.detect_arch()}')
        raise typer.Exit(ExitCode.ISSUE)

    wanted = bundle_name or listed[0]
    if wanted not in listed:
        raise typer.BadParameter(f'--bundle: {wanted} is not on the remote. Newest is {listed[0]}')

    directory = transport.bundles_for(where, named)
    record = offline_bundle.record_on_remote(where, directory, wanted)
    _describe(wanted, record, len(listed))
    if not _confirmed('Download this bundle?', f'fetched {wanted}', yes=yes, no_input=no_input):
        error('nothing was downloaded')
        raise typer.Exit(ExitCode.ISSUE)

    destination = offline_bundle.fetch(where, named, wanted, record)
    if record.sha256:
        render_note('digest matches the record on the remote')

    success(f'downloaded {wanted} to {paths.under_home(destination)}')
    hint(f'stage it with: dotfiles bundle stage {destination}')
    raise typer.Exit(ExitCode.CONVERGED)


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


def _confirmed(question: str, would_have: str, *, yes: bool, no_input: bool) -> bool:
    """Whether to go ahead, asked the way every prompt here is asked.

    **One helper for all three prompts, because three copies had already
    diverged**: declining a download printed a sentence and exited ISSUE,
    declining a local sweep printed a different sentence and exited ISSUE, and
    declining a remote sweep printed nothing and exited ISSUE — so somebody who
    answered `n` got a non-zero status with no reason on screen. The caller still
    owns what happens next; what is shared is how the question is put and what a
    machine without a terminal is told instead.

    Default no everywhere. Two of the three are destructive by the test
    standards/cli-design.md § "Destructive operations require an explicit flag"
    applies, and the third protects a transfer that is minutes on the network this
    exists for.
    """
    if yes:
        return True
    if no_input or not sys.stdin.isatty():
        raise typer.BadParameter(f'--yes is required without a terminal to ask. Would have {would_have}')
    return typer.confirm(question, default=False, err=True)


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
                'base': staged.base.name if staged.base else None,
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
    # Here rather than in `report_bundle`, which the apply gate and the `--offline`
    # rehearsals of `plan` and `check` all share — a per-bundle listing in four
    # places is browse density inside a nudge. Rendered without colour, matching
    # the `measured` rows below: a pin is a fact rather than a warning.
    for path, described in zip(staged.bundles, staged.descriptions, strict=True):
        pin = ', pinned — the sparse bundles above it read through it' if path == staged.base else ''
        render_row('staged', path.name, f'{"sparse" if described.sparse else "full"}{pin}')
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
        # Both values real, so the line pastes. This runs on the machine that will
        # install, so its own CPU is the answer — a literal `ARCH` here would exit
        # USAGE on the very flag the hint is teaching.
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
    keep: int | None = KeepOption,
    remote_too: bool = typer.Option(False, '--remote', help="Also remove what is past the limit on the remote's shelf"),
    machine: str = typer.Option(None, '--machine', help='Whose bundles to sweep (default: every machine in the cache)'),
    yes: bool = typer.Option(False, '--yes', help='Skip the confirmation'),
    no_input: bool = typer.Option(False, '--no-input', help='Never prompt; fail naming the flag that would have answered'),
    as_json: bool = JsonOption,
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

    **The newest full bundle per machine is pinned, whatever the limit.** A sparse
    bundle carries only a difference and falls through to the full one beneath it
    for everything else, so sweeping that base makes every tool the sparse bundle
    deliberately omitted unrecoverable — on the box that cannot fetch another. A
    name sorts as its stamp does and the base is always the oldest, so it was
    always the first thing taken; at the default limit that lands after five
    sparse builds rather than only at `--keep 1`. A newer full build unpins the
    older, which bounds the stack at the limit plus one.

    **The limit counts per machine, not across the cache.** `bundle download
    --machine X` writes another box's archive beside this one's, so a sweep that
    counted them together would let five downloads for a peer age out the only
    bundle on a box that cannot re-fetch it.

    **The newest is never removed, whatever the limit.** A machine with nothing
    staged cannot converge offline at all, so a `--keep 0` that emptied the
    staging directory would take the machine's only way to install anything.
    """
    verbosity(verbose, quiet)
    # `is not None`, because 0 is a number somebody types meaning it. Treated as a
    # sentinel for "read the config" it becomes five, which is the one answer the
    # caller did not ask for.
    if keep is not None and keep < 1:
        raise typer.BadParameter(
            f'--keep {keep}: a machine with nothing staged cannot converge offline at all, so the floor is 1',
            param_hint='--keep',
        )
    retained = keep if keep is not None else max(_configured_keep(), 1)
    sweep = _superseded_locally(retained, machine)
    superseded = sweep.superseded

    if superseded or sweep.pinned:
        for name in superseded:
            render_row('superseded', name, _age_of(name), 'yellow')
        for name in sweep.pinned:
            render_row('pinned', name, 'the newest full bundle, which the sparse bundles above it read through')
        # Asked only where something goes. A run whose only candidate was the base
        # has nothing to confirm, and the pinned row above already said why.
        if superseded and not _confirmed(
            f'Remove {len(superseded)} local bundle(s)?', f'removed {len(superseded)} locally', yes=yes, no_input=no_input
        ):
            error('nothing was removed locally')
            raise typer.Exit(ExitCode.ISSUE)

    swept = _prune_local(superseded)
    for name in swept:
        render_row('removed', name, 'past the retention limit', 'yellow')

    remotely = _prune_remote(machine, retained, yes=yes, no_input=no_input) if remote_too else ()

    if as_json:
        emit_json(
            {
                'machine': machine or '',
                'kept': retained,
                'removed': list(swept),
                'pinned': list(sweep.pinned),
                'removed_remotely': list(remotely),
            }
        )
        raise typer.Exit(ExitCode.CONVERGED)

    held = f', plus {len(sweep.pinned)} pinned as a full base' if sweep.pinned else ''
    console.print(f'{len(swept)} removed locally, {retained} kept per machine{held}')
    raise typer.Exit(ExitCode.CONVERGED)


def _configured_keep() -> int:
    """The machine's own limit, or this tool's default where it declares none."""
    found = transport.read()
    return found.remote.keep_bundles if found.remote else transport.DEFAULT_KEEP


def _superseded_locally(keep: int, machine: str | None) -> offline_bundle.Sweep:
    """What a local sweep would remove, counted per machine and named, removing nothing.

    Separate from the removal so the confirmation has something to show. A prompt
    that could not name what it is about to delete is one people answer yes to
    without reading.
    """
    # By stem, so one bundle is one row. An archive carries `.tar.gz` and the
    # directory it unpacks into does not, so counting the two as they are names a
    # single bundle twice and offers to remove it twice.
    archives = (
        (offline_bundle.stem(path) for path in paths.archive_dir().glob(offline_bundle.ARCHIVES)) if paths.archive_dir().is_dir() else ()
    )
    staged = (path.name for path in providers.staged_bundles())
    grouped = offline_bundle.by_machine(tuple({*archives, *staged}))
    narrowed = {machine: grouped.get(machine, ())} if machine else grouped
    return offline_bundle.swept(narrowed, keep)


def _prune_local(superseded: tuple[str, ...]) -> tuple[str, ...]:
    """Remove what `_superseded_locally` named, by stem, and say what went.

    All three shapes are removed for every stem — the archive, its record, and the
    directory it unpacked into — because a stem names one bundle however many of
    them happen to be on disk. Each removal is idempotent, so asking first would
    cost a stat to decide nothing.
    """
    removed = []
    for stem in superseded:
        archive = paths.archive_dir() / f'{stem}.tar.gz'
        staged = paths.staging_dir() / stem
        if archive.exists() or staged.is_dir():
            archive.unlink(missing_ok=True)
            (paths.archive_dir() / f'{stem}.tar.gz{offline_bundle.SIDECAR_SUFFIX}').unlink(missing_ok=True)
            shutil.rmtree(staged, ignore_errors=True)
            removed.append(stem)
    return tuple(removed)


def _prune_remote(machine: str | None, keep: int, *, yes: bool, no_input: bool) -> tuple[str, ...]:
    """Remove what is past the limit on a machine's shelf, having said what first.

    Answers what it removed, so the caller's `--json` reports the remote half
    rather than describing a run that was only half measured.

    A shelf holds one machine's bundles, so this names one where the local sweep
    covers every machine in the cache. That asymmetry is the shelf's, not the
    flag's.
    """
    where = transport.reachable()
    named = machine or Session.resolve(None).machine_name
    directory = transport.bundles_for(where, named)
    sweep = offline_bundle.retention(offline_bundle.on_remote(where, named), keep)
    superseded = sweep.superseded
    # Rendered before the guard below, or a sweep whose only candidate was the
    # base returns saying nothing is past the limit — which is false. Something
    # was, and it was deliberately held back.
    for name in sweep.pinned:
        render_row('pinned', name, 'the newest full bundle, which the sparse bundles above it read through')

    if not superseded:
        render_note(f'nothing on the remote for {named} is past the {keep} kept')
        return ()

    for name in superseded:
        render_row('superseded', name, _age_of(name), 'yellow')
    question = f'Remove {len(superseded)} bundle(s) from {directory}?'
    if not _confirmed(question, f'removed {len(superseded)} from {directory}', yes=yes, no_input=no_input):
        error(f'nothing was removed from {directory}')
        raise typer.Exit(ExitCode.ISSUE)

    for name in superseded:
        transport.remove(where, f'{directory}/{name}')
        # Best effort, and the asymmetry is deliberate: a record whose archive is
        # gone is a row `download` fails on, while an archive whose record is gone
        # is merely unverifiable. Refusing here would leave the first state behind.
        with contextlib.suppress(transport.RemoteError):
            transport.remove(where, f'{directory}/{name}{offline_bundle.SIDECAR_SUFFIX}')
    success(f'removed {len(superseded)} from {directory}')
    return superseded
