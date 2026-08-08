"""Deploying the repo into $HOME, and the two things that go with it.

This was `install/ops/symlinks.sh`, and the reason it is no longer a shell script
is the bootstrap: that file reached the symlink manager as `uv run symlinks`,
which resolves a project from the working directory. A machine that has just run
`install.sh` has the CLI installed as a tool and no synced virtualenv in the
checkout, so `uv run` there means "sync from the network" — which is exactly what
the offline path cannot do, on the one machine that needs it most.

There is one deployment verb. `link` was create-only, so a deleted source left a
broken link behind in `$HOME` and the caller had to know which kind of change they
had made; reconciling always prunes, so `relink` is the whole of it.
"""

from __future__ import annotations

from pathlib import Path

from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import err_console
from dotfiles.output import hint
from dotfiles.symlinks import core

IDENTITY_FILE = Path.home() / '.gitconfig'

IDENTITY_PLACEHOLDER = """\
# This machine's git identity. Not in the dotfiles repo: identity is per-machine,
# and the shared config sets user.useConfigOnly so a machine without one refuses
# to commit rather than guessing an author from the hostname.
#
# Read after ~/.config/git/config, so anything here wins.
"""


def _ensure_identity_file() -> None:
    """Give `git config --global` somewhere to write that is not this repo.

    Absent `~/.gitconfig`, git writes to `~/.config/git/config` — which this repo
    owns through a symlink, so following git's own "Please tell me who you are"
    hint on a fresh machine commits an identity into the checkout. An empty file
    redirects the write and deliberately carries no [user], so `useConfigOnly`
    still refuses to commit until someone sets one.
    """
    if IDENTITY_FILE.exists():
        return
    IDENTITY_FILE.write_text(IDENTITY_PLACEHOLDER)
    hint(f'created {IDENTITY_FILE} — set an identity with: git config --global user.email <address>')


def _sync_windows_shell(platform: str) -> None:
    """WSL only: copy the shell profile onto the Windows host beside it."""
    if platform != 'wsl':
        return
    run(['bash', str(paths.INSTALL_DIR / 'wsl' / 'sync-windows-shell.sh')], cwd=paths.REPO_ROOT)


def relink(platform: str) -> bool:
    """Remove every link and recreate it, which is what prunes the dangling ones.

    `link` is create-only, so a deleted source leaves a broken link behind in
    `$HOME`. Reconciling means the machine ends up matching the declaration, so
    this is what `symlinks apply` runs and `link` has no separate front door.
    """
    err_console.print('[bold blue]Relinking symlinks[/]')
    failed = core.relink(platform)
    _ensure_identity_file()
    _sync_windows_shell(platform)
    _reload_compositor(platform)
    return not failed


def unlink(platform: str) -> bool:
    """Remove every link this repo deployed, overlay first."""
    err_console.print('[bold blue]Removing symlinks[/]')
    for target in (platform, 'common'):
        source = paths.REPO_ROOT / 'configs' / target
        if source.is_dir():
            core.remove_symlinks(source, target)
    return True


def check() -> bool:
    """Report broken links without removing any. Reads only — `apply` is what writes."""
    broken = core.find_broken_symlinks()
    if not broken:
        err_console.print('[green]✓[/] No broken symlinks found')
        return True
    err_console.print(f'[yellow]Found {len(broken)} broken symlinks:[/]')
    for symlink in broken:
        err_console.print(f'  [red]✗[/] {symlink}')
    return False


def show() -> None:
    core.show_symlinks(None, 'all dotfiles')


def _reload_compositor(platform: str) -> None:
    """Hyprland reads the config files the pass above just deployed, so the reload
    belongs with the deployment rather than at the end of a run."""
    if platform == 'archlinux' and run(['hyprctl', 'reload'], output=Output.QUIET).ok:
        err_console.print('Hyprland configuration reloaded')
