"""Read the world: every worktree on the machine, and who is standing in it.

`held_by` sits here rather than beside the disposal it gates, because it is the
pure half — a function of a `Worktree` and the `Evidence` gathered around it, with
no repository behind it. That is what lets every branch of a deletion decision be
reached on purpose in a test.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from dotfiles.worktree import Evidence
from dotfiles.worktree import Kept
from dotfiles.worktree import Session
from dotfiles.worktree import State
from dotfiles.worktree import Worktree
from dotfiles.worktree.output import git
from dotfiles.worktree.output import run
from dotfiles.worktree.output import say_warning
from dotfiles.worktree.repo import default_branch
from dotfiles.worktree.repo import display_path
from dotfiles.worktree.repo import divergence
from dotfiles.worktree.repo import primary_checkout
from dotfiles.worktree.repo import worktree_root


def live_sessions() -> tuple[Session, ...] | None:
    """Live Claude Code sessions, from the tool that owns the registry, or None when
    the question could not be asked at all.

    claude-sessions does the pid liveness test, and does it on the box where a pid
    means something.

    None rather than an empty tuple, which is the same split `ahead` makes and for a
    heavier reason. `list` only annotates rows with this, so an unanswerable read
    costs it a column. `sweep` gates a removal on it, and an empty tuple there reads
    as *nobody is in this worktree* — which is exactly the sentence that is not known.
    """
    if shutil.which('claude-sessions') is None:
        return None
    result = run(['claude-sessions', '--json'])
    if result.returncode != 0:
        say_warning('claude-sessions failed; the sessions in each worktree are unknown')
        return None
    return tuple(
        Session(
            name=row['name'],
            status=row['status'],
            waiting=row.get('waiting'),
            cwd=Path(row['cwd']),
            tmux=row.get('tmux'),
            pid=row.get('pid'),
        )
        for row in json.loads(result.stdout)
    )


def sessions_at(sessions: Sequence[Session] | None, path: Path) -> tuple[Session, ...] | None:
    """The sessions standing in one worktree, or None when nobody could be asked.

    A session's cwd descends below the directory it started in, so a worktree
    claims everything at or under its own path.
    """
    if sessions is None:
        return None
    return tuple(session for session in sessions if session.cwd == path or path in session.cwd.parents)


def scan(root: Path, repo_filter: str | None) -> list[tuple[str, bool, Path]]:
    """Every worktree on the machine, as (repo, is_checkout, path).

    Ordered by repo, with each checkout ahead of the worktrees cut from it. The
    checkout is read back out of git rather than guessed from the path, because
    $WORKTREE_ROOT names the repo and nothing else — where that repo is cloned is
    a fact only git holds.
    """
    checkouts: dict[Path, str] = {}
    linked: list[tuple[str, Path]] = []

    for candidate in sorted(root.glob('*/*')):
        if not (candidate / '.git').exists():
            continue
        checkout = primary_checkout(candidate)
        if checkout is None:
            continue
        repo = checkout.name
        if repo_filter and repo != repo_filter:
            continue
        checkouts[checkout] = repo
        linked.append((repo, candidate))

    rows = [(repo, True, checkout) for checkout, repo in checkouts.items()]
    rows += [(repo, False, path) for repo, path in linked]
    return sorted(rows, key=lambda row: (row[0], not row[1], str(row[2])))


def describe(repo: str, path: Path, checkout: bool, sessions: Sequence[Session] | None) -> Worktree:
    base = default_branch(path)
    behind, ahead = divergence(path, base)
    branch = git(path, 'rev-parse', '--abbrev-ref', 'HEAD')
    return Worktree(
        repo=repo,
        path=path,
        checkout=checkout,
        branch=branch,
        base=base,
        ahead=ahead,
        behind=behind,
        state=State.DIRTY if git(path, 'status', '--porcelain') else State.CLEAN,
        sessions=sessions_at(sessions, path),
        # What --abbrev-ref answers for a HEAD pointing at a commit rather than a ref. There is no
        # branch behind it, so `published` and the ahead count are answers about nothing.
        detached=branch == 'HEAD',
    )


def describe_all(rows: Sequence[tuple[str, bool, Path]], sessions: Sequence[Session] | None) -> list[Worktree]:
    """Every scanned row as a Worktree, skipping any git refuses to speak about."""
    found = []
    for repo, checkout, path in rows:
        try:
            found.append(describe(repo, path, checkout, sessions))
        except subprocess.CalledProcessError as error:
            say_warning(f'skipping {display_path(path)}: git refused ({error.stderr.strip() or error})')
    return found


def discover(repo_filter: str | None) -> list[Worktree]:
    """Read the world once: every worktree, with what it carries and who is in it.

    Local reads only. `sweep` fetches before it describes, and does it in the open
    rather than behind a flag here, because the failures of that fetch decide
    whether its verdicts mean anything.
    """
    return describe_all(scan(worktree_root(), repo_filter), live_sessions())


def held_by(worktree: Worktree, evidence: Evidence) -> Kept | None:
    """Why this worktree survives a sweep, or None when every check clears it.

    Pure. Ordered so the reason a reader is given is the one they would have named
    themselves: what is in the tree, then who is in it, then what is in the branch.

    Every check that can be unanswerable is tested for that first, and separately from
    being false. The two are one value in git's own vocabulary — an empty session list,
    a missing remote ref — and collapsing them here means an unreachable origin reads
    as a deleted branch, which is the reading that authorises the removal.

    What is in the branch is asked as *are its changes on the base branch*, never as
    *are its commits*. The commit count answers the second and is right about it; a
    branch rewritten on its way onto the base branch keeps a count above zero for the
    rest of its life, and no later check can undo a keep the count already decided.
    """
    if worktree.state is State.DIRTY:
        return Kept.DIRTY
    if worktree.sessions is None:
        return Kept.SESSIONS_UNREADABLE
    if worktree.sessions:
        return Kept.SESSION
    if worktree.detached:
        return Kept.DETACHED
    if not evidence.fetched:
        return Kept.UNFETCHED_REMOTE
    if worktree.ahead is None:
        return Kept.UNFETCHED_BASE
    if evidence.landed is None:
        return Kept.UNREADABLE_LANDING
    if not evidence.landed:
        return Kept.UNLANDED
    if not evidence.published:
        return Kept.UNPUBLISHED
    if evidence.remote is None:
        return Kept.REMOTE_UNREADABLE
    if worktree.branch in evidence.remote:
        return Kept.REMOTE_LIVE
    return None
