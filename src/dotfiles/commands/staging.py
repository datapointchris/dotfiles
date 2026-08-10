"""Offline bundles, and the Windows side of a WSL install.

Both exist for the same machine: a work box behind a firewall that cannot reach
GitHub. They are separate resources because they stage different things — one
carries this repo's installers, the other carries Windows executables that WSL
copies onto its own PATH.

`windows apply --offline` rather than a `stage` verb, because it *installs*:
staging would imply the machine is left untouched, and it is not.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import typer

from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import windows
from dotfiles import windows_bundle
from dotfiles.output import console
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.output import success
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
def check() -> None:
    """Report whether a usable bundle is staged."""
    error('bundle check is not built: it diffs a staged bundle against the plan the resolver produces')
    hint('the resolver it was waiting on has landed; what it reads is the document `dotfiles plan --json` emits')
    raise typer.Exit(ExitCode.ISSUE)


@bundle_app.command('show')
def show() -> None:
    """List what a staged bundle contains."""
    error('bundle show is not built: it renders the rows `providers.bundle` already reads')
    raise typer.Exit(ExitCode.ISSUE)


@bundle_app.command('prune')
def prune() -> None:
    """Remove staged bundles."""
    error('bundle prune is not built, and may never need to be: staging moves to $XDG_RUNTIME_DIR, which empties on reboot')
    hint('a staged bundle today is under ~/installers and is removed by hand')
    raise typer.Exit(ExitCode.ISSUE)


@windows_app.command('check')
def windows_check(as_json: bool = JsonOption) -> None:
    """Report which Windows tools are missing from this WSL machine's PATH.

    A real checker as of the conversion, and cheap enough to be one: the question
    is which declared filenames exist in a single directory, so it needs neither
    winget nor a network — which is what stopped it existing while the answer lived
    inside a shell script that could only install.
    """
    try:
        into = windows.destination()
    except windows.WindowsSideError as unreachable:
        error(str(unreachable))
        raise typer.Exit(ExitCode.ISSUE) from unreachable

    absent = windows.missing(into)
    for name in absent:
        console.print(f'[red]missing[/red]  {name}')
    console.print(f'{len(windows.TOOLS) - len(absent)} of {len(windows.TOOLS)} Windows tools in {into}')
    raise typer.Exit(ExitCode.DRIFT if absent else ExitCode.CONVERGED)


@windows_app.command('apply')
def windows_apply(
    source: str = typer.Option(None, '--source', help='Bundle archive or directory to install from'),
    offline: bool = typer.Option(False, '--offline', help='Install from --source rather than winget'),
) -> None:
    """Install the Windows tools WSL copies onto its PATH.

    The shell tree is deliberately not synced here any more. `setup-windows.sh`
    ended by running `sync-windows-shell.sh`, which is now the `windows-shell`
    step — so `dotfiles apply` converges it, and doing it again here would be one
    act with two owners and no way to tell which had run.
    """
    if offline and not source:
        raise typer.BadParameter('--offline needs --source naming the bundle to install from')

    try:
        into = windows.destination()
        unresolved = windows.install_from_bundle(Path(source), into) if offline else windows.install_via_winget(into)
    except windows.WindowsSideError as unreachable:
        error(str(unreachable))
        raise typer.Exit(ExitCode.ISSUE) from unreachable

    for name in unresolved:
        error(f'{name} did not land in {into}')
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
