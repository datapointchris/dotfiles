"""Offline bundles, and the Windows side of a WSL install.

Both exist for the same machine: a work box behind a firewall that cannot reach
GitHub. They are separate resources because they stage different things — one
carries this repo's installers, the other carries Windows executables that WSL
copies onto its own PATH.

`windows apply --offline` rather than a `stage` verb, because it *installs*:
staging would imply the machine is left untouched, and it is not.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
from pathlib import Path

import typer

from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import reconcile
from dotfiles import windows
from dotfiles import windows_bundle
from dotfiles.commands import QuietOption
from dotfiles.commands import VerboseOption
from dotfiles.commands import verbosity
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import render_row
from dotfiles.output import success
from dotfiles.session import NoMachine
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

bundle_app = typer.Typer(no_args_is_help=True, help='Offline bundles for a machine with no network')
windows_app = typer.Typer(no_args_is_help=True, help='The Windows half of a WSL install')

JsonOption = typer.Option(False, '--json', help='Emit machine-readable output on stdout')

PLATFORMS = ('linux-x86_64', 'linux-arm64', 'darwin-x86_64', 'darwin-arm64')


@bundle_app.command('create')
def create(
    platform: str = typer.Option('linux-x86_64', '--platform', help=f'Target: {", ".join(PLATFORMS)}'),
    print_path: bool = typer.Option(False, '--print-path', help='Print the archive path on stdout, for a pipeline'),
) -> None:
    """Download every installer this repo needs into one archive."""
    if platform not in PLATFORMS:
        raise typer.BadParameter(f'unknown platform {platform!r}. Valid: {", ".join(PLATFORMS)}')

    from dotfiles import create_bundle

    arguments = ['--platform', platform, *(('--print-path',) if print_path else ())]
    raise typer.Exit(create_bundle.main(arguments))


@bundle_app.command('stage')
def stage(archive: str = typer.Argument(None, help='Path to a bundle archive (default: the newest in ./ or ~/)')) -> None:
    """Unpack a bundle so an install can read it, without installing anything.

    Named only where the default is wrong. A machine has one bundle on it, its
    name carries a date nobody types, and the two directories searched are the
    two a tarball is ever copied to — which is the same discovery the bootstrap
    does, for the same reason.
    """
    found = Path(archive) if archive else offline_bundle.newest()
    if found is None:
        error(f'no bundle archive in {Path.cwd()} or {Path.home()}, and none named')
        hint('build one on a networked machine with: dotfiles bundle create')
        raise typer.Exit(ExitCode.ISSUE)

    try:
        staged = offline_bundle.stage(found)
    except offline_bundle.StagingError as unreadable:
        error(str(unreadable))
        raise typer.Exit(ExitCode.ISSUE) from unreadable

    success(f'staged {found.name} at {staged}')


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
    try:
        session = Session.resolve(machine, offline=True)
    except NoMachine as unnamed:
        error(str(unnamed))
        raise typer.Exit(ExitCode.USAGE) from unnamed

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
                'built': staged.built,
                'covered': list(found.covered),
                'uncovered': list(found.uncovered),
                'outside': found.outside,
            }
        )
        raise typer.Exit(ExitCode.DRIFT if found.uncovered else ExitCode.CONVERGED)

    reconcile.report_bundle(staged)
    for name in found.uncovered:
        render_row('uncovered', name, 'the bundle carries no file for it, so an offline run cannot measure or install it', 'yellow')
    bundlable = len(found.covered) + len(found.uncovered)
    console.print(f'{len(found.covered)} of {bundlable} bundlable item(s) staged  ·  {found.outside} installed by other means')
    if found.uncovered:
        hint('build a newer bundle where the network reaches: dotfiles bundle create --platform PLATFORM')
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
def prune() -> None:
    """Remove staged bundles."""
    error('bundle prune is not built, and may never need to be: staging moves to $XDG_RUNTIME_DIR, which empties on reboot')
    hint('a staged bundle today is under ~/installers and is removed by hand')
    raise typer.Exit(ExitCode.ISSUE)


@windows_app.command('check')
def windows_check(as_json: bool = JsonOption, verbose: int = VerboseOption, quiet: bool = QuietOption) -> None:
    """Report which Windows tools are missing from this WSL machine's PATH.

    A real checker as of the conversion, and cheap enough to be one: the question
    is which declared filenames exist in a single directory, so it needs neither
    winget nor a network — which is what stopped it existing while the answer lived
    inside a shell script that could only install.
    """
    verbosity(verbose, quiet)
    try:
        into = windows.destination()
    except windows.WindowsSideError as unreachable:
        error(str(unreachable))
        raise typer.Exit(ExitCode.ISSUE) from unreachable

    absent = windows.missing(into)
    for name in sorted(absent):
        render_row('missing', name, f'not in {into}', 'yellow')
    # Names on both sides. `windows.TOOLS` holds `Tool`, `windows.missing` returns
    # their names, so differencing the two removes nothing and then sorts a frozen
    # dataclass declared without `order=True` — a TypeError on every invocation.
    for name in sorted({tool.name for tool in windows.TOOLS} - set(absent)):
        render_row('matched', name, '', 'green')
    console.print(f'{len(windows.TOOLS) - len(absent)} of {len(windows.TOOLS)} Windows tools in {into}')
    raise typer.Exit(ExitCode.DRIFT if absent else ExitCode.CONVERGED)


@windows_app.command('apply')
def windows_apply(
    source: str = typer.Option(None, '--source', help='Bundle archive or directory to install from'),
    offline: bool = typer.Option(False, '--offline', help='Install from --source rather than winget'),
    verbose: int = VerboseOption,
    quiet: bool = QuietOption,
) -> None:
    """Install the Windows tools WSL copies onto its PATH.

    The shell tree is deliberately not synced here any more. `setup-windows.sh`
    ended by running `sync-windows-shell.sh`, which is now the `windows-shell`
    step — so `dotfiles apply` converges it, and doing it again here would be one
    act with two owners and no way to tell which had run.
    """
    verbosity(verbose, quiet)
    if offline and not source:
        raise typer.BadParameter('--offline needs --source naming the bundle to install from')

    try:
        into = windows.destination()
        unresolved = windows.install_from_bundle(Path(source), into) if offline else windows.install_via_winget(into)
    except windows.WindowsSideError as unreachable:
        error(str(unreachable))
        raise typer.Exit(ExitCode.ISSUE) from unreachable

    for name in sorted(unresolved):
        render_row('failed', name, f'did not land in {into}', 'red')
    console.print(f'{len(windows.TOOLS) - len(unresolved)} of {len(windows.TOOLS)} Windows tools in {into}')
    raise typer.Exit(ExitCode.ISSUE if unresolved else ExitCode.CONVERGED)


@windows_app.command('create')
def windows_create(archive: str = typer.Argument(None, help='Output archive (default: dated, in the repo root)')) -> None:
    """Download the Windows executables into an archive, from any machine.

    Its own verb rather than a `bundle create --platform windows`, because the
    two carry different things: `bundle create` packs this repo's installers for
    a Linux or macOS machine, and this packs Windows executables that WSL copies
    onto its PATH. Collapsing them would make `--platform` mean two things.

    There is deliberately no `windows sync`: the `windows-shell` step converges
    the Git Bash tree under `dotfiles apply`, so a separate verb would be the same
    act with one more way to forget it.

    Runs anywhere, unlike its siblings — it only downloads, so the machine
    building the bundle is deliberately not the machine that will install it.
    """
    default = paths.REPO_ROOT / f'dotfiles-windows-tools-v{dt.date.today():%Y%m%d}.tar.gz'
    try:
        built = windows_bundle.build(Path(archive) if archive else default)
    except windows_bundle.BundleError as unbuilt:
        error(str(unbuilt))
        raise typer.Exit(ExitCode.ISSUE) from unbuilt

    success(f'{built}')
    raise typer.Exit(ExitCode.CONVERGED)
