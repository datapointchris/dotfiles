"""Everything that writes: cutting a worktree, provisioning it, taking it away.

The refusals live here beside the writes they guard, because each one exists to
run *before* the write it precedes — `cli-design.md` § "Everything that can refuse
runs before the first byte of data". `dispose` reports how far it got rather than
succeeding or failing, since the directory and the branch go separately.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
from pathlib import Path

from dotfiles.worktree import Destination
from dotfiles.worktree import Disposal
from dotfiles.worktree import Fault
from dotfiles.worktree import Refused
from dotfiles.worktree.output import git
from dotfiles.worktree.output import git_effect
from dotfiles.worktree.output import run
from dotfiles.worktree.output import say_info
from dotfiles.worktree.output import say_ok
from dotfiles.worktree.output import say_warning
from dotfiles.worktree.repo import briefs_dir
from dotfiles.worktree.repo import default_branch
from dotfiles.worktree.repo import display_path
from dotfiles.worktree.repo import primary_checkout
from dotfiles.worktree.repo import worktree_root
from dotfiles.worktree.survey import live_sessions
from dotfiles.worktree.survey import sessions_at


def require_checkout(cwd: Path) -> Path:
    checkout = primary_checkout(cwd)
    if checkout is None:
        raise Refused('Not inside a git repository')
    return checkout


def require_clean(cwd: Path) -> None:
    dirty = git(cwd, 'status', '--porcelain')
    if not dirty:
        return
    raise Refused(
        f'This worktree has uncommitted changes\n{dirty}',
        "Commit them (git commit -m ... -- <paths>) or 'worktree drop --force'",
    )


def prune_repo_dir(path: Path) -> None:
    """`git worktree remove` takes the leaf and leaves the repo directory behind, so
    $WORKTREE_ROOT silently accumulates empty shells of repos carrying nothing."""
    parent = path.parent
    if parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()


def dispose(checkout: Path, path: Path, branch: str, *, force: bool) -> tuple[Disposal, str]:
    """Remove a worktree and delete its branch. The member says how far it got.

    Neither result is discarded. A removal that fails silently is how a worktree
    outlives the landing that announced success — the commits reach the base branch,
    the directory stays, and $WORKTREE_ROOT grows a tree whose work is already
    elsewhere.

    `force` removes a tree carrying changes, which only a caller that has offered to
    lose them may ask for.

    -D rather than -d, in every caller, and the evidence is the caller's rather than
    git's. `branch -d` asks whether the branch is merged into the *checkout's* HEAD,
    and the checkout is a different tree whose local base branch is only as current as
    its last pull. It refuses a branch that merged on the remote hours ago, and it
    accepts one merged into a base that has since been rewritten. Every caller here
    proves the branch's changes are already on `origin/<base>` — the branch they were
    actually merged into — immediately before calling.
    """
    removal = git_effect(checkout, 'worktree', 'remove', *(['--force'] if force else []), str(path))
    if removal.returncode != 0:
        return Disposal.NOT_REMOVED, removal.stderr.strip() or 'git refused to remove the worktree'

    prune_repo_dir(path)
    deletion = git_effect(checkout, 'branch', '--quiet', '-D', branch)
    if deletion.returncode != 0:
        return Disposal.BRANCH_KEPT, deletion.stderr.strip() or f'git refused to delete {branch}'
    return Disposal.DONE, ''


def declares_setup(path: Path) -> bool:
    """Whether the repo declares a `setup` target to make a checkout runnable.

    Asked of the tree rather than of a registry, because the target is the
    declaration — a repo opts in by having one and there is nothing else to keep
    in step. Every way of not having one answers False: no `task` installed, no
    Taskfile, a Taskfile that does not declare it.
    """
    if shutil.which('task') is None:
        return False
    listed = run(['task', '--list-all', '--json'], cwd=path)
    if listed.returncode != 0:
        return False
    try:
        tasks = json.loads(listed.stdout).get('tasks', [])
    except json.JSONDecodeError:
        return False
    return any(task.get('name') == 'setup' for task in tasks)


def provision(path: Path) -> None:
    """Run the repo's own `task setup` in a new worktree.

    A worktree is a clean checkout, so everything gitignored is absent — the
    virtualenv, node_modules, and whatever else has no manifest. What that means
    is the repo's to say; this only decides when to ask.

    It blocks, and on a large front end it blocks for a minute. That is the
    right trade: the alternative is handing back a path that looks ready and
    fails at the first command the session runs in it.

    A failure is reported rather than raised. The worktree exists either way,
    and destroying it would lose the isolation that was the point.
    """
    if not declares_setup(path):
        return
    say_info('Provisioning — running `task setup`')
    if run(['task', 'setup'], cwd=path).returncode != 0:
        say_warning('task setup failed; the worktree exists but is not provisioned')


def create_worktree(cwd: Path, checkout: Path, slug: str) -> Path:
    """Cut a worktree off origin's default branch, provision it, and return its path.

    Shared by `new` and `spawn` so the two cannot drift: a session started by `spawn`
    would otherwise be the one landing in a tree that `task setup` never ran in, and
    nothing about that failure would name the branch they took differently.
    """
    path = worktree_root() / checkout.name / slug

    if path.exists():
        raise Refused(f'Already exists: {path}')

    base = default_branch(cwd)
    git_effect(cwd, 'fetch', '--quiet', 'origin')
    created = git_effect(cwd, 'worktree', 'add', '--quiet', str(path), '-b', slug, f'origin/{base}')
    if created.returncode != 0:
        raise Refused(created.stderr.strip() or f'git could not create {path}')

    provision(path)
    return path


def require_unoccupied(path: Path) -> None:
    """Refuse to put a second session into a worktree that already holds one.

    An unreadable registry refuses too. *Nobody is here* and *nobody could be asked* are
    the same empty list, and reading the second as the first is what authorises the
    collision — the same split `held_by` keeps for its four unanswerable members.
    """
    sessions = sessions_at(live_sessions(), path)
    if sessions is None:
        raise Refused(
            f'Cannot tell whether a session is already in {display_path(path)}',
            'claude-sessions is what answers that, and two sessions in one worktree is the collision this tool exists to prevent',
            fault=Fault.SESSIONS_UNREADABLE,
        )
    if sessions:
        raise Refused(
            f'{display_path(path)} already holds {", ".join(session.name for session in sessions)}',
            'Spawn under a different slug, or send that session a message instead of a second session',
            fault=Fault.WORKTREE_OCCUPIED,
        )


def resolve_destination(cwd: Path, checkout: Path, slug: str | None) -> Destination:
    """Where the session will stand: a worktree of its own, or the checkout itself.

    The absent slug is `cli-design.md` § "Scope is structural: the argument's presence
    selects it, never a flag".

    An existing worktree is attached to rather than refused, and its branch is read back
    out of git rather than assumed to be the slug: a session standing there may have
    moved it.
    """
    if slug is None:
        occupants = sessions_at(live_sessions(), checkout)
        if occupants:
            names = ', '.join(session.name for session in occupants)
            say_warning(f'{display_path(checkout)} already holds {names}, and this session will share its index')
            say_info('Give it a slug if it will commit; with none it gets no branch, which is what makes sharing a checkout safe')
        return Destination(checkout, None, worktree=False)

    path = worktree_root() / checkout.name / slug
    if not path.exists():
        return Destination(create_worktree(cwd, checkout, slug), slug, worktree=True, created=True)

    if primary_checkout(path) is None:
        raise Refused(
            f'{display_path(path)} exists but is not a worktree', 'Remove it, or spawn under a different slug', fault=Fault.NOT_A_WORKTREE
        )
    require_unoccupied(path)
    return Destination(path, git(path, 'rev-parse', '--abbrev-ref', 'HEAD'), worktree=True)


def unwind(checkout: Path, where: Destination) -> None:
    """Take back a worktree this run cut, after something later refused.

    Only ever called for one this run created, and never for one it attached to: the
    second holds work somebody else is doing. `dispose` is the same removal `land` and
    `drop` use, and its result is reported rather than raised — the caller is already
    raising the refusal that brought us here, and a failed cleanup must not replace it.
    """
    if where.branch is None:
        return
    outcome, detail = dispose(checkout, where.path, where.branch, force=True)
    if outcome is Disposal.DONE:
        say_info(f'Removed {display_path(where.path)}, which this run had just created')
        return
    say_warning(f'{display_path(where.path)} was created by this run and is still here: {detail}')


def keep_brief(source: Path, repo: str, slug: str | None) -> Path:
    """Copy the brief somewhere it outlives its author, and return the copy.

    The session reads its brief once, at launch, so the file has to survive only until
    then — but the caller writing it has no way to know when that is, and a coordinator
    writing briefs into its own scratch directory would be racing its agents' startup.

    Kept rather than deleted afterwards because it is the only record of what a session
    was told, which is what a later reader needs to tell a wrong agent from a wrong brief.

    `mkstemp` mints the name rather than a timestamp, because two spawns in one second
    have no distinguishing part left — and that is not a rare case. A coordinator
    dispatches several reviewers at once, none of them carries a slug, and they all name
    the same repo. The loser's brief is overwritten and the winner's session is launched
    against instructions written for somebody else.
    """
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    briefs_dir().mkdir(parents=True, exist_ok=True)
    handle, minted = tempfile.mkstemp(dir=briefs_dir(), prefix=f'{repo}-{slug or "checkout"}-{stamp}-', suffix='.md')
    os.close(handle)

    destination = Path(minted)
    destination.write_text(source.read_text())
    return destination


def catch_up_checkout(checkout: Path, base: str) -> None:
    """The checkout is now behind, and in dotfiles a checkout is deployed machine
    state — so leaving it stale is not cosmetic.

    Fast-forward it only when it is clean and on the branch we landed on: another
    session may be working there, and its tree is not ours to move.
    """
    head = git(checkout, 'rev-parse', '--abbrev-ref', 'HEAD')
    if head != base:
        say_warning(f'{checkout} is on {head}, not {base} — catch it up yourself')
        return
    if git(checkout, 'status', '--porcelain'):
        say_warning(f'{checkout} has local changes — run `git fetch origin && git rebase origin/{base}` there when free')
        return

    git_effect(checkout, 'fetch', '--quiet', 'origin')
    git_effect(checkout, 'rebase', '--quiet', f'origin/{base}')
    say_ok(f'Caught up {checkout}')
