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
import shutil
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

YAZI_PLUGIN_DIR = Path('.config/yazi/plugins')
"""Where yazi looks, with a `.yazi` suffix on each directory it appends itself.
Same reasoning as above: one place, so it is not a per-entry field."""


@dc.dataclass(frozen=True, slots=True)
class Observed:
    present: frozenset[str]
    """Addresses whose checkout is on disk."""

    @property
    def summary(self) -> str:
        """Says *cloned* deliberately. TPM and lazy.nvim each own a plugin list
        this repo does not declare — tmux's is in `tmux.conf`, Neovim's is in lua
        — so there is nothing here to compare them against, and claiming to have
        checked them would be worse than not checking."""
        return f'all {len(self.present)} cloned plugins are present (tmux and nvim sync on apply)'


def destination(item: DesiredItem, home: Path) -> Path:
    """Where this plugin's checkout belongs.

    `tmux_plugins` declares its own `install_dir` because TPM is told the path and
    has to agree with it; the other two have no such contract and take the one
    directory their program reads.
    """
    if isinstance(item.entry, catalog.TmuxPlugin):
        return Path(item.entry.install_dir.replace('~', str(home), 1))
    if isinstance(item.entry, catalog.YaziPlugin):
        return home / YAZI_PLUGIN_DIR / f'{item.name}.yazi'
    return home / SHELL_PLUGIN_DIR / item.name


def repository(item: DesiredItem) -> str:
    return getattr(item.entry, 'repo', '')


def subdirectory(item: DesiredItem) -> str:
    return getattr(item.entry, 'subdirectory', '')


class PluginsResource:
    name = NAME
    help = 'shell, tmux and yazi plugins cloned from git'

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
        if inner := subdirectory(item):
            return _clone_subdirectory(change, repository(item), inner, target)

        result = run(['git', 'clone', '--quiet', repository(item), str(target)], output=Output.STREAM)
        if not result.ok:
            return Outcome(change, OutcomeStatus.FAILED, result.transcript.strip() or f'git clone exited {result.returncode}')
        return Outcome(change, OutcomeStatus.DONE, f'cloned into {target}')


def _clone_subdirectory(change: Change, repo: str, inner: str, target: Path) -> Outcome:
    """Take one plugin out of a repository carrying two dozen of them.

    Copied out rather than moved, and with symlinks resolved: `yazi-rs/plugins`
    gives each plugin a `LICENSE` symlink to the one at the repo root, and a move
    leaves that pointing at a path *outside* the plugin — dangling, and aimed at
    the shared plugins directory where something else could later satisfy it.
    `ya pkg add` materialises the file, so this does too.

    `ignore_dangling_symlinks` is deliberately **not** set, despite looking like
    the tolerant choice: `copytree` tests the raw link target against the process
    working directory rather than against the symlink's own, so `../LICENSE`
    reads as dangling wherever the command happens to run and the flag drops a
    link that resolves perfectly. Left off, a link that genuinely dangles raises
    and is reported instead of vanishing.

    The clone is shallow here, unlike every other plugin: nothing sources this
    checkout or pulls it, because what survives is the copy.
    """
    staging = target.with_name(f'.{target.name}.staging')
    shutil.rmtree(staging, ignore_errors=True)

    try:
        result = run(['git', 'clone', '--quiet', '--depth', '1', repo, str(staging)], output=Output.STREAM)
        if not result.ok:
            return Outcome(change, OutcomeStatus.FAILED, result.transcript.strip() or f'git clone exited {result.returncode}')

        source = staging / inner
        if not source.is_dir():
            return Outcome(change, OutcomeStatus.FAILED, f'{repo} has no {inner}; the plugin moved or was renamed upstream')

        shutil.copytree(source, target)
    except (OSError, shutil.Error) as problem:
        shutil.rmtree(target, ignore_errors=True)
        return Outcome(change, OutcomeStatus.FAILED, f'copying {inner} out of {repo}: {problem}')
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return Outcome(change, OutcomeStatus.DONE, f'cloned {inner} from {repo} into {target}')


def clone(session: Session, stage: Stage) -> bool:
    """Clone every missing plugin at one stage, reporting whether all succeeded.

    By stage, because they live on opposite sides of the symlink deployment: the
    zsh plugins can land any time, while TPM has to be there before the pass that
    reads the tmux config it was deployed alongside, and the yazi plugins go
    after that pass so nothing writes into `~/.config/yazi` before the repo's own
    files are there.
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
