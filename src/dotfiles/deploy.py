"""Deploying the repo into $HOME, and the three jobs that follow it.

The deciding is `resources/symlinks.py`. What lives here is the epilogue, which
belongs with the deployment rather than at the end of a run: git needs somewhere
to write that is not this repo, WSL needs the shell profile copied onto the
Windows host beside it, and Hyprland has to reload the files the pass just
deployed.

There is one deployment verb, because reconciling always prunes. A create-only
pass leaves a broken link behind whenever a source is deleted, and asks the
caller to know which kind of change they just made.
"""

from __future__ import annotations

from pathlib import Path

from dotfiles import coordinates as axes
from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import err_console
from dotfiles.output import hint
from dotfiles.resources import symlinks
from dotfiles.session import Session
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

    A dangling link has to go first: `exists()` follows it and so reads as absent,
    while `write_text()` follows it and creates its target. Every machine that
    predates this file had `~/.gitconfig` linked into `configs/<platform>/`, so
    the link left behind by that source's removal aims the write at the one place
    the placeholder exists to stay out of.
    """
    if IDENTITY_FILE.is_symlink() and not IDENTITY_FILE.exists():
        IDENTITY_FILE.unlink()
    if IDENTITY_FILE.exists():
        return
    IDENTITY_FILE.write_text(IDENTITY_PLACEHOLDER)
    hint(f'created {IDENTITY_FILE} — set an identity with: git config --global user.email <address>')


def _sync_windows_shell(coordinates: axes.Coordinates) -> None:
    """Copy the shell profile onto the Windows host beside this one.

    Keyed on the host rather than on `wsl` the platform: there is a Windows side
    to copy to whenever WSL is the host, whatever distro is running inside it.
    """
    if coordinates.host is not axes.Host.WSL:
        return
    run(['bash', str(paths.INSTALL_DIR / 'wsl' / 'sync-windows-shell.sh')], cwd=paths.REPO_ROOT)


def epilogue(session: Session) -> None:
    """The three jobs that follow a deployment, and belong with it rather than at
    the end of a run.

    git needs somewhere to write that is not this repo, WSL needs the shell profile
    copied onto the Windows host beside it, and Hyprland has to reload the files the
    pass just deployed.

    The deploying itself is the engine's now. This used to carry its own
    observe/diff/perform loop beside the resource's, which is one of the reasons
    there were thirteen of them; what is left here is genuinely not the walk.
    """
    _ensure_identity_file()
    _sync_windows_shell(session.machine.coordinates)
    _reload_compositor(session.machine.coordinates)


def unlink(session: Session) -> bool:
    """Remove every link this repo deployed, overlay first.

    Driven by the same `layers()` the deployment is, so a tree gaining an overlay
    cannot leave a layer that only one of the two halves knows about.
    """
    err_console.print('[bold blue]Removing symlinks[/]')
    triples = list(symlinks.layers(session.repo, session.machine.coordinates, session.home.resolve()))
    for source, _, layer in reversed(triples):
        if source.is_dir():
            core.remove_symlinks(source, layer)
    return True


def show(session: Session) -> None:
    """Every declared link and where it currently stands.

    Declared rather than discovered, so a link that was never deployed appears
    here too — the previous version walked `$HOME` and could only list what
    already existed.
    """
    observed = symlinks.RESOURCE.observe(session, session.plan)
    verdicts = {change.item: change for change in symlinks.RESOURCE.diff(session.plan, observed)}

    for link in observed.links:
        change = verdicts.get(link.address)
        mark = '[green]→[/]' if change is None else '[yellow]✗[/]'
        note = '' if change is None else f'  ({change.verdict})'
        err_console.print(f'  {mark} {link.address} → {link.target}{note}')

    for path in observed.orphans:
        err_console.print(f'  [red]✗[/] {path} (source gone)')

    err_console.print(f'\n{len(observed.links)} declared, {len(verdicts)} not deployed as declared')


def _reload_compositor(coordinates: axes.Coordinates) -> None:
    """Hyprland reads the config files the pass above just deployed, so the reload
    belongs with the deployment rather than at the end of a run.

    Keyed on the display stack, which is what put those files in the plan: the
    compositor is a fact about Wayland, not about Arch.
    """
    if coordinates.display_stack is axes.DisplayStack.WAYLAND and run(['hyprctl', 'reload'], output=Output.QUIET).ok:
        err_console.print('Hyprland configuration reloaded')
