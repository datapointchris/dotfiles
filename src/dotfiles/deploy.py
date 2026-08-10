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

GIT_CONFIG_ENTRY = Path.home() / '.config' / 'git' / 'config'
HOME_GITCONFIG = Path.home() / '.gitconfig'

PERSONAL_IDENTITY = Path.home() / '.config' / 'git' / 'personal.gitconfig'
"""The identity the repo ships, included unconditionally on a fleet machine."""

LOCAL_IDENTITY = Path.home() / '.config' / 'git' / 'local.gitconfig'
"""The identity the repo declares and never holds, on a machine whose default is
not the personal one.

Named for what it is to this repo — machine-local, like `~/.local/shell/local.sh`
beside it — rather than for whose address it happens to carry. It was
`employer.gitconfig`, which reads as a category the repo is entitled to know and
is wrong on the first machine that keeps a second identity for any other reason.
"""

GIT_CONFIG_STUB = """\
# This machine's git entry point, and the only file in this directory the repo
# does not own. Both of its jobs need it to be a real file rather than a symlink.
#
# It includes the shared config, which git no longer reads by itself now that the
# repo's copy is named common.gitconfig. And it is where `git config --global`
# writes, which is the reason it must not be a link: git follows one when writing,
# so an entry point linked into the checkout takes an identity with it.
#
# It carries no [user] of its own. Identity arrives through the trust include, and
# useConfigOnly refuses a commit while nothing has set one.
[include]
path = ~/.config/git/common.gitconfig
"""


def _identity_in(path: Path) -> str:
    """What git reads out of one file, rather than this guessing at config syntax."""
    result = run(['git', 'config', '--file', str(path), '--get', 'user.email'], output=Output.QUIET)
    return result.stdout.strip() if result.ok else ''


def _ensure_git_config_entry(coordinates: axes.Coordinates) -> None:
    """Give `git config --global` somewhere to write that is not this repo.

    git writes to `~/.config/git/config` only while `~/.gitconfig` is absent, and
    it follows a symlink when writing, so the entry point has to exist, be real,
    and be the only one. Left as a link into the repo, following git's own "Please
    tell me who you are" hint on a fresh machine commits an identity into the
    checkout.

    A link here is unlinked rather than adopted. After the rename to
    common.gitconfig the old entry point is an orphan the symlink stage prunes
    first, but a machine reaching this out of order would otherwise write through
    it into the repo, which is the one outcome this exists to prevent.
    """
    if GIT_CONFIG_ENTRY.is_symlink():
        GIT_CONFIG_ENTRY.unlink()
    if not GIT_CONFIG_ENTRY.exists():
        GIT_CONFIG_ENTRY.parent.mkdir(parents=True, exist_ok=True)
        GIT_CONFIG_ENTRY.write_text(GIT_CONFIG_STUB)
        hint(f'created {GIT_CONFIG_ENTRY}')
    _retire_home_gitconfig(coordinates)


def _retire_home_gitconfig(coordinates: axes.Coordinates) -> None:
    """Remove the `~/.gitconfig` this used to create, now that the entry point is XDG.

    git prefers it over `~/.config/git/config` for reads and writes both, so one
    left behind silently out-ranks the entire include chain — the identity a trust
    overlay supplies would resolve, and then lose to whatever is in here.

    An identity in it is never deleted, but where it should go depends on the
    machine. Off the fleet it is the only copy of an address the repo
    deliberately does not hold, so it moves to the machine-local identity file.
    On a fleet machine the repo already ships that address in
    personal.gitconfig, so there is nothing to preserve and the file is simply
    in the way — advising a rescue file there sent one Mac looking for a
    destination its trust overlay never includes.
    """
    if not HOME_GITCONFIG.exists():
        # `exists()` follows a link, so a dangling one reads as absent here and
        # still has to be unlinked: left behind it is the write target git picks.
        if HOME_GITCONFIG.is_symlink():
            HOME_GITCONFIG.unlink()
        return
    if identity := _identity_in(HOME_GITCONFIG):
        err_console.print(f'  [red]✗[/] ~/.gitconfig holds {identity} and out-ranks ~/.config/git/config')
        if coordinates.network_trust is axes.NetworkTrust.FLEET:
            hint(f'this machine already has that identity from {PERSONAL_IDENTITY.name}, so delete ~/.gitconfig')
        else:
            hint(f'move it into {LOCAL_IDENTITY}, then delete ~/.gitconfig')
        return
    HOME_GITCONFIG.unlink()
    hint(f'removed {HOME_GITCONFIG} — the entry point is now {GIT_CONFIG_ENTRY}')


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
    _ensure_git_config_entry(session.machine.coordinates)
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
