"""Plugins cloned from git: the zsh plugins, tmux's plugin manager, and yazi's.

All three are the same shape — a repo, a directory, and the question of whether
the directory is there — which is what makes them a resource rather than three
scripts that each re-read `packages.yml` through an interpreter of their own.

The yazi plugins are here rather than in the yazi install because they are
plugins, not part of a binary. `ya pkg add` used to run inside the release
installer, six stages before the symlink pass, and wrote yazi's own state file to
a path this repo deployed a file to — two writers on one path, and every fresh
install failed the symlink phase. Splitting the plugins out is what makes that a
question about plugins; moving the whole yazi install after the symlinks would
only have reordered the collision.

**Two plugin steps are deliberately not here**, because they are a different kind
of work. `install/common/plugins/tmux-plugins.sh` runs TPM and
`nvim-plugins.sh` runs `Lazy! sync`: each hands a plugin list to an external
manager that owns the installing, and neither list is in `packages.yml` — tmux's
is in `tmux.conf` and Neovim's is in lua. There is no per-item declaration for
the resolver to plan, so `check` here reports on the clones and says so rather
than implying it has asked those two anything.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles import registry
from dotfiles.privilege import Privilege
from dotfiles.providers import clone
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

    @property
    def summary(self) -> str:
        """Says *cloned* deliberately. TPM and lazy.nvim each own a plugin list
        this repo does not declare — tmux's is in `tmux.conf`, Neovim's is in lua
        — so there is nothing here to compare them against, and claiming to have
        checked them would be worse than not checking."""
        return f'all {len(self.present)} cloned plugins are present (tmux and nvim sync on apply)'


class PluginsResource:
    name = NAME
    help = 'shell, tmux and yazi plugins cloned from git'

    def observe(self, session: Session, plan: Plan) -> Observed:
        present = frozenset(item.address for item in _planned(plan) if clone.destination(item, session.home).is_dir())
        return Observed(
            present=present,
            behind=frozenset(item.address for item in _planned(plan) if item.address in present and clone.behind(item, session.home))
            if session.refresh
            else frozenset(),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        missing = tuple(
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.MISSING,
                detail=f'not cloned from {clone.repository(item)}',
                desired=item,
            )
            for item in _planned(plan)
            if item.address not in observed.present
        )
        stale = tuple(
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.STALE,
                detail=f'behind {clone.repository(item)}',
                desired=item,
            )
            for item in _planned(plan)
            if item.address in observed.behind
        )
        return missing + stale

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Whichever provider planned it clones it, or says why it cannot."""
        return registry.install(session, change, privilege)


def _planned(plan: Plan) -> tuple[DesiredItem, ...]:
    return plan.for_resource(NAME)


RESOURCE = PluginsResource()
