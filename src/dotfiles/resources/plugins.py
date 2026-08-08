"""Plugins cloned from git: the zsh plugins, and tmux's plugin manager.

Both are the same shape — a repo, a directory, and the question of whether the
directory is there — which is what makes them a resource rather than two scripts
that each re-read `packages.yml` through an interpreter of their own.

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
from pathlib import Path

from dotfiles import catalog
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import success
from dotfiles.output import warn
from dotfiles.privilege import Privilege
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'plugins'

SHELL_PLUGIN_DIR = Path('.config/zsh/plugins')
"""Where `.zshrc` sources them from. Not declared per entry in `packages.yml`,
because every shell plugin lands in the same place and a field repeating that on
five entries is five chances to disagree."""


@dc.dataclass(frozen=True, slots=True)
class Observed:
    present: frozenset[str]
    """Addresses whose checkout is on disk."""


def destination(item: DesiredItem, home: Path) -> Path:
    """Where this plugin's checkout belongs.

    `tmux_plugins` declares its own `install_dir` because TPM is told the path and
    has to agree with it; a shell plugin has no such contract and takes the one
    directory `.zshrc` reads.
    """
    if isinstance(item.entry, catalog.TmuxPlugin):
        return Path(item.entry.install_dir.replace('~', str(home), 1))
    return home / SHELL_PLUGIN_DIR / item.name


def repository(item: DesiredItem) -> str:
    return getattr(item.entry, 'repo', '')


class PluginsResource:
    name = NAME
    help = 'shell and tmux plugins cloned from git'

    def observe(self, session: Session, plan: Plan) -> Observed:
        return Observed(
            present=frozenset(item.address for item in _planned(plan) if destination(item, session.home).is_dir()),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        return tuple(
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.MISSING,
                detail=f'not cloned from {repository(item)}',
                desired=item,
            )
            for item in _planned(plan)
            if item.address not in observed.present
        )

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Clone one plugin.

        A shallow clone is deliberately *not* used: `zsh-vi-mode` and `forgit` are
        sourced from their checkout and updated in place by `git pull`, which a
        shallow clone makes slower rather than faster.
        """
        item = change.desired
        if item is None:
            return Outcome(change, OutcomeStatus.REFUSED, 'nothing declares this plugin any more')

        target = destination(item, session.home)
        if target.is_dir():
            return Outcome(change, OutcomeStatus.SKIPPED, f'{target} appeared since the check')

        target.parent.mkdir(parents=True, exist_ok=True)
        result = run(['git', 'clone', '--quiet', repository(item), str(target)], output=Output.STREAM)
        if not result.ok:
            return Outcome(change, OutcomeStatus.FAILED, result.transcript.strip() or f'git clone exited {result.returncode}')
        return Outcome(change, OutcomeStatus.DONE, f'cloned into {target}')


def clone(session: Session, stage: Stage) -> bool:
    """Clone every missing plugin at one stage, reporting whether all succeeded.

    By stage, because the two live on opposite sides of the symlink deployment:
    the zsh plugins can land any time, and TPM has to be there before the pass
    that reads the tmux config it was deployed alongside.
    """
    changes = [
        change
        for change in RESOURCE.diff(session.plan, RESOURCE.observe(session, session.plan))
        if change.actionable and change.stage is stage
    ]
    # Nothing here escalates — a plugin is a clone into $HOME — so the privilege
    # is constructed and never authorized, which is the state that refuses.
    outcomes = [RESOURCE.perform(session, change, Privilege()) for change in changes]

    for outcome in outcomes:
        if outcome.ok:
            success(f'{outcome.change.item}: {outcome.message}')
        else:
            warn(f'{outcome.change.item}: {outcome.message}')

    return all(outcome.ok for outcome in outcomes)


def _planned(plan: Plan) -> tuple[DesiredItem, ...]:
    return plan.for_resource(NAME)


RESOURCE = PluginsResource()
