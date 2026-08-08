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

from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import err_console
from dotfiles.output import hint
from dotfiles.output import warn
from dotfiles.resources import Repair
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


def _sync_windows_shell(platform: str) -> None:
    """WSL only: copy the shell profile onto the Windows host beside it."""
    if platform != 'wsl':
        return
    run(['bash', str(paths.INSTALL_DIR / 'wsl' / 'sync-windows-shell.sh')], cwd=paths.REPO_ROOT)


def deploy(session: Session) -> bool:
    """Bring every declared link into line, then run the three jobs that follow it.

    Only what differs is written: the resource decides per link, where the pass
    this replaced recreated all of them and could not say which had been missing.

    Nothing is unlinked first, and that must not be reinstated. A remove-everything
    pass left the target tree unlinked for the length of the create pass, and a
    daemon watching its own config in there reloads inside that window, finds
    nothing, and writes itself a default — which the create pass then refuses as a
    target it did not create. Hyprland does exactly this, every run, on an
    established machine. Replacing each link in place has no such window.
    """
    err_console.print('[bold blue]Deploying symlinks[/]')

    changes = symlinks.RESOURCE.diff(session.plan, symlinks.RESOURCE.observe(session, session.plan))
    outcomes = [symlinks.RESOURCE.perform(session, change) for change in changes if change.actionable]

    for outcome in outcomes:
        if not outcome.ok:
            warn(f'{outcome.change.item}: {outcome.message}')

    refused = [change for change in changes if change.drifted and change.repair is Repair.BY_HAND]
    if refused:
        warn(f'refused {len(refused)} target(s) this manager did not create:')
        for change in refused:
            err_console.print(f'    {change.detail}')
        hint('re-run with --force to replace them')

    err_console.print(f'{sum(1 for outcome in outcomes if outcome.ok)} of {len(changes)} link(s) updated')

    _ensure_identity_file()
    _sync_windows_shell(session.machine.platform_label)
    _reload_compositor(session.machine.platform_label)
    return not refused and all(outcome.ok for outcome in outcomes)


def unlink(platform: str) -> bool:
    """Remove every link this repo deployed, overlay first."""
    err_console.print('[bold blue]Removing symlinks[/]')
    for target in (platform, 'common'):
        source = paths.REPO_ROOT / 'configs' / target
        if source.is_dir():
            core.remove_symlinks(source, target)
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


def _reload_compositor(platform: str) -> None:
    """Hyprland reads the config files the pass above just deployed, so the reload
    belongs with the deployment rather than at the end of a run."""
    if platform == 'archlinux' and run(['hyprctl', 'reload'], output=Output.QUIET).ok:
        err_console.print('Hyprland configuration reloaded')
