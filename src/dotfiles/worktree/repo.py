"""What git and the filesystem say about one path, and nothing about sessions.

Every read here is answerable from a checkout alone. `landed` and `published` are
the two that decide whether a worktree may be deleted, which is why they are
measured here rather than inferred from a commit count by the caller.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from dotfiles.worktree.output import git
from dotfiles.worktree.output import git_effect
from dotfiles.worktree.output import git_optional


def worktree_root() -> Path:
    """Where every worktree this tool makes lives, and the only index of them."""
    return Path(os.environ.get('WORKTREE_ROOT') or Path.home() / '.worktrees')


def briefs_dir() -> Path:
    """Where a spawned session's brief is kept, per standards/data.md § "Every path a
    tool writes is an XDG base directory".

    State rather than cache or data: nothing recomputes a brief, no human authored it,
    and deleting one changes what a session was told rather than costing a rebuild. Not
    a synced store either — a brief is about one spawn on one machine, and replicating
    it to every box would put another machine's instructions in this one's directory.
    """
    state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
    return state / 'worktree' / 'briefs'


def display_path(path: Path) -> str:
    """`~`-relative, which is how a path reads in a table."""
    home = Path.home()
    return f'~/{path.relative_to(home)}' if path.is_relative_to(home) else str(path)


def primary_checkout(path: Path) -> Path | None:
    """The checkout that owns .git, which `git worktree list` prints first by
    definition. None when `path` is not inside a git repository at all."""
    listing = git_optional(path, 'worktree', 'list', '--porcelain')
    if not listing or not listing.startswith('worktree '):
        return None
    return Path(listing.splitlines()[0].removeprefix('worktree '))


def default_branch(path: Path) -> str:
    """origin's own idea of its default branch, so a repo that never adopted `main`
    still lands where it should.

    The remote HEAD is absent on a clone made with --no-tags, or on one whose ref
    was never set, hence the fallback.
    """
    ref = git_optional(path, 'symbolic-ref', '--quiet', 'refs/remotes/origin/HEAD')
    return ref.rsplit('/', 1)[-1] if ref else 'main'


def in_linked_worktree(path: Path) -> bool:
    return git(path, 'rev-parse', '--git-dir') != git(path, 'rev-parse', '--git-common-dir')


def divergence(path: Path, base: str) -> tuple[int | None, int | None]:
    """Commits behind and ahead of origin/<base>.

    (None, None) where that ref does not exist: a clone that has never fetched has
    no answer, and reporting zero would read as up to date.
    """
    counts = git_optional(path, 'rev-list', '--left-right', '--count', f'origin/{base}...HEAD')
    if counts is None:
        return None, None
    behind, ahead = counts.split()
    return int(behind), int(ahead)


def fetch_checkouts(rows: Sequence[tuple[str, bool, Path]]) -> set[Path]:
    """Update every checkout with --prune, returning the ones git could not reach.

    The failures are the return value because they are load-bearing. Every remote
    fact below is read out of refs/remotes/origin, which outlives a branch deleted
    on the remote until a prune, so a checkout whose fetch failed can only produce
    a verdict about the remote it never reached.
    """
    failed = set()
    for _, checkout, path in rows:
        if checkout and git_effect(path, 'fetch', '--prune', '--quiet', 'origin').returncode != 0:
            failed.add(path)
    return failed


def remote_branches(checkout: Path) -> frozenset[str] | None:
    """Every branch origin still carries, or None when git could not be asked.

    One read per repo rather than a probe per worktree: the answer is the same for
    every worktree cut from the same checkout. lstrip=3 drops `refs/remotes/origin`
    and leaves the branch, slashes in its name included.
    """
    listing = git_optional(checkout, 'for-each-ref', '--format=%(refname:lstrip=3)', 'refs/remotes/origin/')
    if listing is None:
        return None
    return frozenset(listing.splitlines())


def published(path: Path, branch: str) -> bool:
    """Whether the branch was ever pushed under its own name.

    `new` cuts the branch from origin/<base>, and git's branch.autoSetupMerge points
    it at origin/<base> rather than at itself. `git push -u origin HEAD` is what moves
    the upstream onto the branch's own ref. So a branch still tracking the base never
    left this machine, and its remote branch cannot have been deleted because it never
    existed.
    """
    merge = git_optional(path, 'config', '--get', f'branch.{branch}.merge')
    return merge == f'refs/heads/{branch}'


def landed(path: Path, base: str) -> bool | None:
    """Whether this branch's work is already on origin/<base>, by ancestry or by content.

    Ancestry is asked first and is the whole answer whenever it holds: a tip reachable
    from origin/<base> is the same history, so nothing here is anywhere else. That is
    the ordinary merge, and it is the case the commit count was already right about.

    A history rewritten on its way onto the base branch is the case it was wrong about.
    A squash collapses the branch into one commit. GitHub's "update branch with rebase"
    replays it onto a newer base, server-side, where nothing can move the local ref.
    Either way the landed work carries new shas and this ref still points at the
    originals. `origin/<base>..HEAD` then counts those originals for as long as the
    branch exists, so work merged months ago cannot be told apart from work that never
    left the machine.

    Content is what tells them apart. The paths come from the merge base, so work the
    base branch gained elsewhere is not counted against this branch, and the comparison
    is against origin/<base> as it stands, so a path the base has since moved on from
    reads as unlanded. Both of those err toward keeping the worktree, which is the
    direction a deletion has to err in.

    `--no-renames` for the same reason. A detected rename is reported as the new path
    alone, and the old one then never enters the comparison — so a base branch that
    took the addition without the deletion reads as having the whole change. Turning
    detection off lists both halves and asks about both.

    The listing is read `-z` and split on NUL, because git's default output is not the
    names. It C-quotes any path holding a non-ASCII byte, a quote, a backslash or a
    control character, so a name carrying an accent comes back wrapped in quotes with
    that character spelled as two backslash escapes. A leading or trailing space is lost
    separately, to the strip that reads a normal git answer. A name that no longer
    selects its own file selects nothing, the comparison finds no difference, and the
    worktree is deleted holding the only copy of the work.

    `:(literal)` on each path so a name is never read as a pattern. Nothing measured
    turns on it: a `*` or a `[` in a filename widens the pathspec rather than missing
    the file, and widening errs toward keeping. It is here because the pathspec is data
    and the default is to interpret it, not because a case was found.

    A branch whose commits net out to no change has nothing to lose, so it has landed.
    The commits go with the directory and what they carried is nothing. None wherever
    git could not be asked, which is a third answer rather than a false one: both
    `--is-ancestor` and `--quiet` exit 1 for *no* and above that for a failure, and
    reading a failure as a *no* would keep a worktree on a question nobody answered —
    while reading it as a *yes* would delete one on the same.
    """
    ancestry = git_effect(path, 'merge-base', '--is-ancestor', 'HEAD', f'origin/{base}')
    if ancestry.returncode == 0:
        return True
    if ancestry.returncode > 1:
        return None

    fork = git_optional(path, 'merge-base', f'origin/{base}', 'HEAD')
    if fork is None:
        return None
    listing = git_effect(path, 'diff', '-z', '--no-renames', '--name-only', fork, 'HEAD')
    if listing.returncode != 0:
        return None
    paths = [name for name in listing.stdout.split('\0') if name]
    if not paths:
        return True
    comparison = git_effect(path, 'diff', '--quiet', f'origin/{base}', 'HEAD', '--', *(f':(literal){name}' for name in paths))
    if comparison.returncode > 1:
        return None
    return comparison.returncode == 0
