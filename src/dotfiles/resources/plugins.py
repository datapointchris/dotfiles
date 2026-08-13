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
from dotfiles.resources import Outcome
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

    managers: frozenset[str] = frozenset()
    """The plugin managers this run examined, by name."""

    unsynced: tuple[tuple[str, str], ...] = ()
    """The managers with something outstanding, each with what was measured."""

    @property
    def summary(self) -> str:
        """Says *cloned* deliberately, and counts the managers separately.

        The two are different questions with different confidence. The checkouts
        are declared here and were looked at one by one; the managers' lists are
        theirs, and only TPM's could be read — `pluginsync` explains why lazy's
        could not be.
        """
        cloned = f'all {len(self.present)} cloned plugins are present'
        if not self.managers:
            return cloned
        return f'{cloned}, and {" and ".join(sorted(self.managers))} have nothing pending'


class PluginsResource:
    name = NAME
    help = 'shell, tmux and yazi plugins, and the managers that own their own lists'

    def observe(self, session: Session, plan: Plan) -> Observed:
        clones = tuple(item for item, provider in _units(plan) if not isinstance(provider, PluginSyncProvider))
        syncs = tuple((item, provider) for item, provider in _units(plan) if isinstance(provider, PluginSyncProvider))

        present = frozenset(item.address for item in clones if clone.destination(item, session.home).is_dir())
        return Observed(
            present=present,
            behind=frozenset(item.address for item in clones if item.address in present and clone.behind(item, session.home))
            if session.refresh
            else frozenset(),
            managers=frozenset(item.name for item, _ in syncs),
            unsynced=tuple((item.address, pending) for item, provider in syncs if (pending := provider.pending(session))),
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
                changes.append(_change(item, Verdict.MISSING, f'not cloned from {clone.repository(item)}'))
            elif item.address in observed.behind:
                changes.append(_change(item, Verdict.STALE, f'behind {clone.repository(item)}'))
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Whichever provider planned it clones it or syncs it, or says why it cannot."""
        return registry.install(session, change, privilege)


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
