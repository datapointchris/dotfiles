"""Where this checkout stands against the upstream branch it tracks.

The fleet's update notice compares an installed version against a published
release, and this repo has neither. It publishes nothing, and `uv tool install
--editable` points the installed tool at the working tree — so what an update
moves is the checkout, and the honest equivalent of a notice is the checkout's
own position.

`.git` already knows it, which is why nothing here reaches the network: the
answer is correct on a machine that has been offline for a week, provided it
says how old it is. Only `update` fetches, and only when asked.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
from pathlib import Path

from dotfiles import paths
from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import warn


@dc.dataclass(frozen=True, slots=True)
class Position:
    """How far this checkout has diverged from its upstream, and when that was measured.

    `fetched` is `None` on a checkout nothing has fetched into since the clone —
    `git clone` writes no `FETCH_HEAD` — and that is reported rather than
    smoothed over, because a position with no measurement date is the one case
    where "up to date" means "never asked".
    """

    upstream: str
    ahead: int
    behind: int
    fetched: dt.datetime | None

    def describe(self, now: dt.datetime) -> str:
        """The one line a reader acts on: where the checkout sits, and how stale that is.

        The two halves are separate because either can be the interesting one. A
        machine that is level with a week-old fetch knows nothing useful, and a
        machine with unpushed work has something to say whether or not it has
        ever fetched.
        """
        line = f'{self._standing()} {self._measured(now)}'
        return f'{line} — run: dotfiles update' if self.behind else line

    def _standing(self) -> str:
        if self.ahead and self.behind:
            return f'{_commits(self.ahead)} ahead of and {_commits(self.behind)} behind {self.upstream}'
        if self.behind:
            return f'{_commits(self.behind)} behind {self.upstream}'
        if self.ahead:
            return f'{_commits(self.ahead)} ahead of {self.upstream}, unpushed'
        return f'up to date with {self.upstream}'

    def _measured(self, now: dt.datetime) -> str:
        if self.fetched is None:
            return '(nothing has fetched since the clone)'
        return f'(fetched {_ago((now - self.fetched).total_seconds())})'


def read(repo: Path = paths.REPO_ROOT) -> Position | None:
    """The position, or `None` when there is nothing to compare against.

    A detached HEAD and a branch tracking no remote both answer `None`, and both
    are legitimate states rather than faults — a machine mid-bisect has no
    upstream to be behind. Saying nothing is what keeps this out of the way of
    someone who is deliberately somewhere else.
    """
    upstream = _git(repo, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
    if not upstream.ok:
        return None

    # Three dots, not two: `--left-right --count HEAD...<upstream>` counts each
    # side of the merge base separately, which is the only spelling that can
    # report ahead and behind at once. `HEAD..<upstream>` collapses to one number
    # and reads a diverged branch as merely behind.
    counts = _git(repo, 'rev-list', '--left-right', '--count', 'HEAD...@{upstream}')
    if not counts.ok:
        return None

    ahead, behind = (int(count) for count in counts.stdout.split())
    return Position(upstream.stdout.strip(), ahead, behind, _last_fetch(repo))


DEPLOYMENT_BRANCH = 'main'
"""The branch this machine is deployed from. Feature work belongs in a worktree."""


def stray_branch(repo: Path = paths.REPO_ROOT) -> str | None:
    """The checked-out branch, when it is not the one the machine deploys from.

    Worth saying out loud before a write because in this repo the branch *is*
    machine state, which is true of almost no other checkout: `configs/`, `shell/`
    and `apps/` are symlinked live into `$HOME`, and the CLI is installed editable
    against `src/`, so switching branches changes both the deployed config and the
    tool that deploys it.

    A detached HEAD answers `None` rather than its sha. Someone mid-bisect knows
    where they are, and `read` already treats that state as deliberate.
    """
    branch = _git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
    if not branch.ok:
        return None
    name = branch.stdout.strip()
    return None if name in {DEPLOYMENT_BRANCH, 'HEAD'} else name


def report_stray_branch() -> None:
    """Say when the deployed config is coming from somewhere other than `main`.

    The branch name is already inside `position.describe` as part of the upstream,
    where it reads as incidental. It is not: this checkout is what `$HOME` links
    into, so the branch decides what the machine is running.

    Deliberately a warning and not a refusal. Checking out a branch here is a
    legitimate thing to do on purpose, and the failure it guards against is not
    knowing — which a line of output fixes and a blocked command does not.

    Beside `stray_branch` rather than in the command layer, because both write
    verbs announce it and neither is a command: `reconcile` would otherwise reach
    upward into the CLI that calls it, which is an import only a deferred one can
    satisfy.
    """
    if stray := stray_branch():
        warn(f'deploying from branch {stray}, not {DEPLOYMENT_BRANCH} — this checkout is what $HOME links into')


def fetch(repo: Path = paths.REPO_ROOT) -> bool:
    """Refresh what `read` measures against. The only function here that uses the network."""
    return _git(repo, 'fetch', '--quiet', output=Output.STREAM).ok


def _git(repo: Path, *args: str, output: Output = Output.QUIET) -> Completed:
    return run(['git', '-C', str(repo), *args], output=output)


def _last_fetch(repo: Path) -> dt.datetime | None:
    """When something last fetched, taken from `FETCH_HEAD`'s mtime.

    Git records no fetch timestamp of its own, and the remote-tracking refs are
    no substitute: a fetch that brought nothing new leaves them untouched, so
    their mtime dates the last *change* rather than the last *look*. `FETCH_HEAD`
    is rewritten by every fetch and pull whether or not anything moved.
    """
    located = _git(repo, 'rev-parse', '--git-dir')
    if not located.ok:
        return None

    marker = repo / located.stdout.strip() / 'FETCH_HEAD'
    try:
        return dt.datetime.fromtimestamp(marker.stat().st_mtime, dt.UTC)
    except OSError:
        return None


def _commits(count: int) -> str:
    return f'{count} commit{"s" * (count != 1)}'


def _ago(seconds: float) -> str:
    for size, unit in ((86400, 'day'), (3600, 'hour'), (60, 'minute')):
        if seconds >= size:
            count = int(seconds // size)
            return f'{count} {unit}{"s" * (count != 1)} ago'
    return 'moments ago'
