"""Offline bundles, and the Windows side of a WSL install.

Both exist for the same machine: a work box behind a firewall that cannot reach
GitHub. They are separate resources because they stage different things — one
carries this repo's installers, the other carries Windows executables that WSL
copies onto its own PATH.

`windows apply --offline` rather than a `stage` verb, because it *installs*:
staging would imply the machine is left untouched, and it is not.
"""

from __future__ import annotations

import typer

from dotfiles import bridge
from dotfiles.output import error
from dotfiles.output import hint
from dotfiles.vocabulary import ExitCode

bundle_app = typer.Typer(no_args_is_help=True, help='Offline bundles for a machine with no network')
windows_app = typer.Typer(no_args_is_help=True, help='The Windows half of a WSL install')

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
def stage(archive: str = typer.Argument(..., help='Path to a bundle archive')) -> None:
    """Unpack a bundle so an install can read it, without installing anything."""
    error('staging a bundle separately is not wired up yet')
    hint(f"today's equivalent installs in the same step: dotfiles apply --offline (finds {archive} itself)")
    raise typer.Exit(ExitCode.ISSUE)


@bundle_app.command('check')
def check() -> None:
    """Report whether a usable bundle is staged."""
    error('bundle check arrives with the resolver, which is what knows the plan a bundle must satisfy')
    raise typer.Exit(ExitCode.ISSUE)


@bundle_app.command('show')
def show() -> None:
    """List what a staged bundle contains."""
    error('bundle show arrives with the resolver')
    raise typer.Exit(ExitCode.ISSUE)


@bundle_app.command('prune')
def prune() -> None:
    """Remove staged bundles."""
    error('bundle prune arrives with the resolver')
    raise typer.Exit(ExitCode.ISSUE)


@windows_app.command('check')
def windows_check() -> None:
    """Report which Windows tools are missing from this WSL machine's PATH."""
    error('windows check has no checker yet — windows apply is idempotent in the meantime')
    raise typer.Exit(ExitCode.ISSUE)


@windows_app.command('apply')
def windows_apply(
    source: str = typer.Option(None, '--source', help='Bundle archive or directory to install from'),
    offline: bool = typer.Option(False, '--offline', help='Install from --source rather than winget'),
) -> None:
    """Install the Windows tools WSL copies onto its PATH."""
    if offline and not source:
        raise typer.BadParameter('--offline needs --source naming the bundle to install from')

    completed = bridge.wsl_script('setup-windows.sh', *(('--offline', source) if offline else ()))
    raise typer.Exit(completed.returncode)


@windows_app.command('create')
def windows_create(archive: str = typer.Argument(None, help='Output archive (default: dated, in the repo root)')) -> None:
    """Download the Windows executables into an archive, from any machine.

    Its own verb rather than a `bundle create --platform windows`, because the
    two carry different things: `bundle create` packs this repo's installers for
    a Linux or macOS machine, and this packs Windows executables that WSL copies
    onto its PATH. Collapsing them would make `--platform` mean two things.

    There is deliberately no `windows sync`: deploying on WSL already runs
    `sync-windows-shell.sh`, so a separate verb would be the same act with one
    more way to forget it.
    """
    completed = bridge.wsl_script('setup-windows.sh', '--bundle', *((archive,) if archive else ()))
    raise typer.Exit(completed.returncode)
