"""Plugins: the ones this repo clones, and the two managers that clone their own.

The clones are the zsh plugins, tmux's plugin manager and yazi's. All three are
the same shape — a repo, a directory, and the question of whether the directory is
there — which is what makes them a resource rather than three scripts that each
re-read `packages.yml` through an interpreter of their own.

The yazi plugins are here rather than in the yazi install because they are
plugins, not part of a binary. Running `ya pkg add` inside the release installer
puts it six stages before the symlink pass, writing yazi's own state file to a
path this repo deploys a file to — two writers on one path, and every fresh
install fails the symlink phase. Splitting the plugins out is what makes that a
question about plugins; moving the whole yazi install after the symlinks would
only have reordered the collision.

**The other kind is a manager handed a list this repo does not declare.** TPM
installs what `tmux.conf` names and lazy.nvim installs what its lua names, so
there is no per-item declaration for the resolver to plan and each is one
synthetic row. They were `tmux-plugins.sh` and `nvim-plugins.sh` — two scripts a
phase ran unconditionally, reporting whatever they printed — and what changed in
converting them is that the row is now measured first. What each can honestly be
asked, and why the two answers differ, is `providers/pluginsync.py`.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles import registry
from dotfiles.privilege import Privilege
from dotfiles.providers import clone
from dotfiles.registry import PluginSyncProvider
from dotfiles.registry import Provider
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'plugins'


@dc.dataclass(frozen=True, slots=True)
class Observed:
    present: frozenset[str]
    """Addresses whose checkout is on disk."""

    behind: frozenset[str] = frozenset()
    """Addresses whose checkout is behind the branch it tracks.

    Empty on a run that did not ask to spend the network, which is not the same as
    "none are behind" — measuring it costs a `git fetch` per plugin, so `check`
    declines and the row says only what it looked at.
    """

    managers: tuple[tuple[str, str], ...] = ()
    """The plugin managers this run examined, each as (address, name).

    Both, because the two readers want different halves. The summary sentence
    names them the way anybody talks about them — lazy, tpm — while a row has to
    be keyed the way `diff` keys one, or a manager with something outstanding and
    one without would appear under two different spellings in the same section.
    """

    unsynced: tuple[tuple[str, str], ...] = ()
    """The managers with something outstanding, each with what was measured."""

    unmanaged: dict[str, str] = dc.field(default_factory=dict)
    """Address → the directory it has, for a plugin declared as a clone with no `.git`.

    Present, working, and outside this repo's reach: `clone.behind` needs a
    checkout to fetch, so it answers None and the plugin reads as current forever.
    Measured on the Arch box, where `~/.config/yazi/plugins/what-size.yazi` holds
    three read-only files and no repository — the shape `ya pkg add` leaves — while
    `packages.yml` declares it a plain clone of `pirafrank/what-size.yazi`.

    Distinct from a subdirectory plugin, which also has no `.git` and is not a
    fault: `clone.py` copies one out of a shallow checkout it then deletes, so
    there was never going to be one. `clone.tracked` answers None for both, which
    is why the two are told apart here rather than there.
    """

    origins: dict[str, str] = dc.field(default_factory=dict)
    """Address → where its directory came from, in the words that are true of it.

    Measured rather than read off the declaration. Saying `cloned` because the
    entry declares a clone is restating an intention as a finding, which is the
    error this whole row exists to correct.
    """

    @property
    def summary(self) -> str:
        """Says *declared* rather than *cloned*, and counts the managers separately.

        The two are different questions with different confidence. These were
        declared here and looked at one by one; the managers' lists are theirs, and
        only TPM's could be read — `pluginsync` explains why lazy's could not be.
        That distinction is what the sentence is for, and `cloned` was the wrong
        word to carry it: a subdirectory plugin is copied out of a checkout that is
        then deleted, so two of the nine never were clones.
        """
        present = f'all {len(self.present)} declared plugins are present'
        if not self.managers:
            return present
        named = sorted(name for _, name in self.managers)
        return f'{present}, and {" and ".join(named)} have nothing pending'

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """Each plugin with where it came from, then the managers with nothing outstanding.

        A checkout that is behind is left out, because `diff` already gives it a
        row of its own — and `behind` is only ever populated by a run that spent
        the network, so on a `check` this is every present plugin.
        """
        pending = {address for address, _ in self.unsynced}
        found = tuple(Examined(address, self.origins.get(address, '')) for address in sorted(self.present - self.behind))
        managers = tuple(Examined(address, 'nothing pending') for address, _ in sorted(self.managers) if address not in pending)
        return found + managers


class PluginsResource:
    name = NAME
    help = 'shell, tmux and yazi plugins, and the managers that own their own lists'

    def observe(self, session: Session, plan: Plan) -> Observed:
        clones = tuple(item for item, provider in _units(plan) if not isinstance(provider, PluginSyncProvider))
        syncs = tuple((item, provider) for item, provider in _units(plan) if isinstance(provider, PluginSyncProvider))

        present = frozenset(item.address for item in clones if clone.destination(item, session.home).is_dir())
        unmanaged = {
            item.address: str(clone.destination(item, session.home))
            for item in clones
            if item.address in present and not clone.subdirectory(item) and clone.tracked(item, session.home) is None
        }
        return Observed(
            present=present,
            behind=frozenset(item.address for item in clones if item.address in present and clone.behind(item, session.home))
            if session.refresh
            else frozenset(),
            managers=tuple((item.address, item.name) for item, _ in syncs),
            unsynced=tuple((item.address, pending) for item, provider in syncs if (pending := provider.pending(session))),
            unmanaged=unmanaged,
            origins={item.address: _origin(item, item.address in unmanaged) for item in clones},
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        """One row per item that differs, in the plan's order.

        Which is stage order, and therefore repair order: TPM has to be cloned
        before the sync that runs it, and the two are adjacent rows of one resource
        rather than two phases someone sequenced by hand.
        """
        pending = dict(observed.unsynced)
        changes = []
        for item, provider in _units(plan):
            if isinstance(provider, PluginSyncProvider):
                if outstanding := pending.get(item.address, ''):
                    changes.append(_change(item, Verdict.MISSING, outstanding))
            elif item.address not in observed.present:
                changes.append(_change(item, Verdict.MISSING, f'not cloned from {_short(clone.repository(item))}'))
            elif directory := observed.unmanaged.get(item.address, ''):
                changes.append(_unmanaged(item, directory))
            elif item.address in observed.behind:
                changes.append(_change(item, Verdict.STALE, f'behind {_short(clone.repository(item))}'))
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Whichever provider planned it clones it or syncs it, or says why it cannot."""
        return registry.install(session, change, privilege)


def _origin(item: DesiredItem, unmanaged: bool) -> str:
    """Where this plugin's directory came from, said the way it actually happened.

    A subdirectory plugin is not a clone and must not claim to be. `clone.py`
    shallow-clones the repo, copies one directory out and deletes the rest, so
    there is no `.git` to pull and `clone.tracked` returns None — which is the
    same fact this sentence carries to a reader.
    """
    repository = _short(clone.repository(item))
    if subdirectory := clone.subdirectory(item):
        return f'copied from {repository}/{subdirectory}'
    return f'no checkout, so {repository} cannot be pulled' if unmanaged else f'cloned from {repository}'


def _short(repo: str) -> str:
    """`wfxr/forgit`, from the URL the declaration carries.

    The host is the same on every entry and costs nineteen characters a row in the
    column that has to align. Stripped by prefix rather than by taking the last two
    segments, so a repo somewhere other than GitHub keeps the part that says where
    it is.
    """
    return repo.removeprefix('https://github.com/').removesuffix('.git')


def _unmanaged(item: DesiredItem, directory: str) -> Change:
    """A declared plugin that is there and is not a checkout of what declares it.

    `BY_HAND`, because the repair is a deletion. `clone.install` runs `git clone`
    into the path, which fails against a directory that already exists, and doing
    it properly means removing whatever is there — which on a plugin somebody
    installed by another route may be the only copy of a local edit. Same
    judgement `symlinks` makes about a foreign target, for the same reason.

    Reported rather than tolerated because the alternative is silence: without a
    checkout `clone.behind` cannot fetch, so it answers None, and the plugin reads
    as current on every run for as long as it exists.
    """
    return Change(
        NAME,
        item.stage,
        item.address,
        Verdict.STALE,
        detail='present, but not a git checkout, so nothing here can update it',
        repair=Repair.BY_HAND,
        advice=f'remove {directory} and re-run to clone it, or drop the entry if another tool owns this plugin',
        desired=item,
    )


def _change(item: DesiredItem, verdict: Verdict, detail: str) -> Change:
    return Change(NAME, item.stage, item.address, verdict, detail=detail, desired=item)


def _units(plan: Plan) -> tuple[tuple[DesiredItem, Provider], ...]:
    """Every planned item with the provider that planned it, in plan order.

    Paired here rather than sorted into two lists by name, because which kind an
    item is is a fact about its provider's class and not about a table this file
    would have to keep in step with the registry.
    """
    pairs = ((item, registry.named(item.provider)) for item in plan.for_resource(NAME))
    return tuple((item, provider) for item, provider in pairs if provider is not None)


RESOURCE = PluginsResource()
