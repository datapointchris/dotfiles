"""One function per verb, each returning the exit code the process leaves with.

Nothing here parses arguments and nothing raises to a terminal: `cli` owns both
ends, so a verb is reachable from a test by calling it.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path

from rich.markup import escape

from dotfiles.worktree import BRIEF_PROMPT
from dotfiles.worktree import FZF_DELIMITER
from dotfiles.worktree import USAGE_ERROR
from dotfiles.worktree import Disposal
from dotfiles.worktree import Evidence
from dotfiles.worktree import Fault
from dotfiles.worktree import Kept
from dotfiles.worktree import Refused
from dotfiles.worktree import Registration
from dotfiles.worktree import Spawned
from dotfiles.worktree import Worktree
from dotfiles.worktree import require_tool
from dotfiles.worktree.operations import catch_up_checkout
from dotfiles.worktree.operations import create_worktree
from dotfiles.worktree.operations import dispose
from dotfiles.worktree.operations import keep_brief
from dotfiles.worktree.operations import require_checkout
from dotfiles.worktree.operations import require_clean
from dotfiles.worktree.operations import resolve_destination
from dotfiles.worktree.operations import unwind
from dotfiles.worktree.output import ERR
from dotfiles.worktree.output import OUT
from dotfiles.worktree.output import confirm
from dotfiles.worktree.output import git
from dotfiles.worktree.output import git_effect
from dotfiles.worktree.output import git_optional
from dotfiles.worktree.output import run
from dotfiles.worktree.output import say_error
from dotfiles.worktree.output import say_info
from dotfiles.worktree.output import say_ok
from dotfiles.worktree.output import say_warning
from dotfiles.worktree.panes import announce
from dotfiles.worktree.panes import await_registration
from dotfiles.worktree.panes import open_pane
from dotfiles.worktree.panes import require_caller_pane
from dotfiles.worktree.panes import stack_beside
from dotfiles.worktree.render import render_table
from dotfiles.worktree.render import section
from dotfiles.worktree.render import show_sessions
from dotfiles.worktree.repo import default_branch
from dotfiles.worktree.repo import display_path
from dotfiles.worktree.repo import fetch_checkouts
from dotfiles.worktree.repo import in_linked_worktree
from dotfiles.worktree.repo import landed
from dotfiles.worktree.repo import primary_checkout
from dotfiles.worktree.repo import published
from dotfiles.worktree.repo import remote_branches
from dotfiles.worktree.repo import worktree_root
from dotfiles.worktree.survey import describe
from dotfiles.worktree.survey import describe_all
from dotfiles.worktree.survey import discover
from dotfiles.worktree.survey import held_by
from dotfiles.worktree.survey import live_sessions
from dotfiles.worktree.survey import scan


def cmd_list(repo_filter: str | None, as_json: bool) -> int:
    worktrees = discover(repo_filter)

    if as_json:
        OUT.print(json.dumps([worktree.as_json() for worktree in worktrees], indent=2), markup=False, highlight=False)
        return 0

    if not worktrees:
        scope = f' for {repo_filter}' if repo_filter else ''
        say_info(f'No worktrees{scope} under {display_path(worktree_root())}')
        return 0

    for line in render_table(worktrees):
        OUT.print(line, markup=False, highlight=False)
    return 0


def resolve_worktree(argument: str | None) -> Worktree:
    """The worktree a `show` is about: the one named, or the one you are standing in."""
    path = Path(argument).expanduser().resolve() if argument else Path.cwd()
    if not path.is_dir():
        raise Refused(f'No such directory: {path}')
    checkout = primary_checkout(path)
    if checkout is None:
        raise Refused(f'Not a git worktree: {path}')
    top = Path(git(path, 'rev-parse', '--show-toplevel'))
    return describe(checkout.name, top, top == checkout, live_sessions())


def cmd_show(argument: str | None) -> int:
    worktree = resolve_worktree(argument)
    label = worktree.repo if worktree.checkout else f'{worktree.repo}/{worktree.path.name}'
    ahead = '?' if worktree.ahead is None else worktree.ahead
    behind = '?' if worktree.behind is None else worktree.behind

    OUT.print(f'[cyan]{escape(label)}[/]', highlight=False)
    OUT.print(display_path(worktree.path), markup=False, highlight=False)
    OUT.print(f'{worktree.branch} — {ahead} ahead, {behind} behind {worktree.base}, {worktree.state}', markup=False, highlight=False)

    section('changes', git(worktree.path, 'status', '--porcelain'))
    section('commits', git_optional(worktree.path, 'log', '--oneline', f'origin/{worktree.base}..HEAD'))
    show_sessions(worktree)
    return 0


def preview_command() -> str:
    """`show`, addressed to the fzf field carrying the path.

    `-m dotfiles.worktree` rather than a path, because a module inside a package
    is not runnable as a file. sys.executable is the interpreter this process is
    already running under, so the preview resolves the package from the same
    environment rather than going looking for one.

    `-q` because the pane is a rendered artifact rather than a session: the git
    reads behind a preview say nothing about the worktree it is previewing, and
    they would be redrawn on every keystroke that moves the cursor.
    """
    interpreter = shlex.quote(sys.executable)
    return f'FORCE_COLOR=1 {interpreter} -m dotfiles.worktree show -q {{1}}'


def cmd_choose(repo_filter: str | None) -> int:
    if shutil.which('fzf') is None:
        raise Refused("fzf is not installed — 'worktree list' is the read that needs no terminal")

    worktrees = discover(repo_filter)
    if not worktrees:
        scope = f' for {repo_filter}' if repo_filter else ''
        raise Refused(f'No worktrees{scope} under {display_path(worktree_root())}')

    header, *rendered = render_table(worktrees)
    rows = [f'{FZF_DELIMITER}{header}', *(f'{w.path}{FZF_DELIMITER}{line}' for w, line in zip(worktrees, rendered, strict=True))]

    picker = 'fzf-tmux' if os.environ.get('TMUX') and shutil.which('fzf-tmux') else 'fzf'
    result = run(
        [
            picker,
            '--delimiter',
            FZF_DELIMITER,
            '--with-nth',
            '2..',
            '--header-lines',
            '1',
            '--no-sort',
            '--ansi',
            '--border-label',
            ' worktrees ',
            '--prompt',
            '  ',
            '--bind',
            'tab:down,btab:up',
            '--preview-window',
            'down,65%,wrap,border-top',
            '--preview',
            preview_command(),
        ],
        input='\n'.join(rows),
    )

    chosen = result.stdout.strip()
    if result.returncode != 0 or not chosen:
        return 0
    OUT.print(chosen.split(FZF_DELIMITER, 1)[0], markup=False, highlight=False)
    return 0


def cmd_new(slug: str) -> int:
    cwd = Path.cwd()
    checkout = require_checkout(cwd)
    path = create_worktree(cwd, checkout, slug)

    say_ok(f'Isolated at {path}')
    OUT.print(str(path), markup=False, highlight=False)
    return 0


def cmd_spawn(slug: str | None, brief: str, *, below: bool, width: str, timeout: float, as_json: bool) -> int:
    """Start a Claude session in a pane of its own, and name it.

    Everything that can refuse is settled before anything is created, per
    `cli-design.md` § "Everything that can refuse runs before the first byte of data" —
    a missing tmux, an absent brief or an occupied worktree costs nothing to discover
    and would otherwise be found after a pane, a branch and a directory already exist.
    """
    caller = require_caller_pane()
    require_tool('claude', 'It is the session this starts')
    require_tool('claude-sessions', 'It is what names the session that lands in the pane')

    source = Path(brief).expanduser()
    if not source.is_file():
        raise Refused(
            f'No brief at {source}',
            'Write the brief to a file — a prompt long enough to be one does not survive quoting',
            fault=Fault.BRIEF_MISSING,
        )
    if not source.read_text().strip():
        raise Refused(f'{source} is empty', 'A session given nothing to read will ask what it is for', fault=Fault.BRIEF_EMPTY)

    cwd = Path.cwd()
    checkout = require_checkout(cwd)
    # Copied before the worktree is cut, so the one thing a later refusal can leave
    # behind is a file in a state directory rather than a branch and a checkout.
    kept = keep_brief(source, checkout.name, slug)
    where = resolve_destination(cwd, checkout, slug)

    # A split can still be refused after the worktree exists — tmux runs out of room in a
    # full window, which is the everyday case for a coordinator dispatching a fourth
    # agent. What it would leave is a branch and a provisioned checkout that `sweep` will
    # not collect, because nothing was ever pushed and it is held as UNPUBLISHED. So the
    # one thing this command created gets unwound before the refusal reaches the caller.
    try:
        pane = open_pane(caller, where.path, BRIEF_PROMPT.format(brief=kept), below=below)
    except Refused:
        if where.created:
            unwind(checkout, where)
        raise

    if not below:
        stack_beside(caller, width)

    spawned = Spawned(
        repo=checkout.name,
        path=where.path,
        branch=where.branch,
        worktree=where.worktree,
        pane=pane,
        brief=kept,
        arrival=await_registration(pane, timeout),
    )

    # The prose first, so a terminal interleaving the two streams reads in the order the
    # run happened rather than ending on the line it opened with.
    announce(spawned, timeout)

    if as_json:
        OUT.print(json.dumps(spawned.as_json(), indent=2), markup=False, highlight=False)
    elif spawned.arrival.session:
        OUT.print(spawned.arrival.session, markup=False, highlight=False)

    # Non-zero without a name, because the caller's next move is a message to it. A spawn
    # reported as success with nothing to address is the failure that reads as working.
    return 0 if spawned.arrival.registration is Registration.REGISTERED else 1


def cmd_land() -> int:
    cwd = Path.cwd()
    checkout = require_checkout(cwd)
    if not in_linked_worktree(cwd):
        raise Refused(
            "Not in a worktree — 'land' is what hands one back to the primary checkout",
            "Run 'worktree new <slug>' first, or commit directly if no other session is here",
        )
    require_clean(cwd)

    base = default_branch(cwd)
    branch = git(cwd, 'rev-parse', '--abbrev-ref', 'HEAD')
    path = Path(git(cwd, 'rev-parse', '--show-toplevel'))

    git_effect(cwd, 'fetch', '--quiet', 'origin')
    ahead = int(git(cwd, 'rev-list', '--count', f'origin/{base}..HEAD'))
    # Not `ahead == 0`, which a branch rewritten on its way onto the base branch never
    # reaches. The rebase below would replay patches whose content is already there,
    # and the push would put a second copy of merged work on the base branch.
    #
    # True refuses and both False and None proceed, which is the opposite of what the
    # other two callers do with None. They decide a deletion off the measurement; this
    # one does not. `dispose` runs after a push that returned zero, so what proves the
    # commits are elsewhere is the push rather than anything measured here. A landing
    # git could not read costs a rebase that finds nothing to replay.
    if landed(cwd, base) is True:
        raise Refused(f'Nothing to land: the work here is already on origin/{base}')

    # Never abort on our own initiative: a conflicted rebase holds the only copy of
    # the resolution in progress, and the standard resolves a conflict inside the
    # commit that caused it rather than by discarding and retrying.
    if git_effect(cwd, 'rebase', '--quiet', f'origin/{base}').returncode != 0:
        raise Refused(
            "Rebase stopped on a conflict — resolve it here, then run 'worktree land' again",
            'Repair everything the commit broke before `git rebase --continue`',
        )

    if git_effect(cwd, 'push', '--quiet', 'origin', f'HEAD:{base}').returncode != 0:
        raise Refused(f"Push rejected — origin/{base} moved again; run 'worktree land' to retry")

    say_ok(f'Landed {ahead} commit(s) on {base}')
    outcome, detail = dispose(checkout, path, branch, force=False)
    if outcome is Disposal.NOT_REMOVED:
        say_warning(f'{display_path(path)} is still here: {detail}')
    elif outcome is Disposal.BRANCH_KEPT:
        say_warning(f'Removed {display_path(path)}, but branch {branch} is still here: {detail}')

    catch_up_checkout(checkout, base)
    say_info(f'cd {checkout}')
    return 0


def cmd_drop(force: bool) -> int:
    cwd = Path.cwd()
    checkout = require_checkout(cwd)
    if not in_linked_worktree(cwd):
        raise Refused('Not in a worktree')

    base = default_branch(cwd)
    branch = git(cwd, 'rev-parse', '--abbrev-ref', 'HEAD')
    path = Path(git(cwd, 'rev-parse', '--show-toplevel'))

    if not force:
        require_clean(cwd)
        # The same question `sweep` asks, for the same reason: a count above zero is a
        # rewritten history as often as it is unlanded work, and the two need opposite
        # answers. This one runs on local refs alone, so a base branch nobody has
        # fetched since the merge reads as unlanded — which refuses, and refusing is
        # the half of this that costs nothing to be wrong about.
        elsewhere = landed(cwd, base)
        if elsewhere is None:
            raise Refused(
                f'Cannot tell whether the work here is already on origin/{base}',
                "Fetch and look; 'worktree drop --force' drops it either way",
            )
        if not elsewhere:
            unlanded = int(git(cwd, 'rev-list', '--count', f'origin/{base}..HEAD'))
            raise Refused(
                f'{unlanded} commit(s) here, and origin/{base} does not match them at the paths they touch',
                f"'git cherry origin/{base} HEAD' if they landed under new shas; "
                "'worktree land' to keep them, 'worktree drop --force' to lose them",
            )

    outcome, detail = dispose(checkout, path, branch, force=True)
    if outcome is Disposal.NOT_REMOVED:
        raise Refused(f'Could not drop {display_path(path)}: {detail}')
    if outcome is Disposal.BRANCH_KEPT:
        # The drop itself happened, so this is a warning rather than a refusal.
        say_warning(f'Branch {branch} is still here: {detail}')

    say_ok(f'Dropped {path}')
    say_info(f'cd {checkout}')
    return 0


def cmd_sweep(repo_filter: str | None, assume_yes: bool) -> int:
    """Dispose of every worktree whose work is finished, from wherever you are standing.

    `land` and `drop` both read Path.cwd() and refuse outside a linked worktree, so
    neither can reach one you are not in. Work that goes through a PR is merged on the
    forge and the remote branch deleted there, and nothing ever runs `drop` — so the
    directories accumulate, and every tool that reports branch state reports each one
    forever.
    """
    rows = scan(worktree_root(), repo_filter)
    unreached = fetch_checkouts(rows)
    worktrees = describe_all(rows, live_sessions())

    # Owner by path rather than by `repo`, which is a directory basename and so is not
    # unique across a machine: ~/code/thing and ~/tools/thing are two repos with one
    # name. This is the command that deletes, so it asks git which checkout owns each
    # tree rather than joining on a string that can collide.
    owners: dict[Path, Path] = {}
    remotes: dict[Path, frozenset[str] | None] = {}
    for worktree in worktrees:
        if worktree.checkout:
            continue
        owner = primary_checkout(worktree.path)
        if owner is None:
            continue
        owners[worktree.path] = owner
        if owner not in remotes:
            remotes[owner] = remote_branches(owner)

    finished: list[Worktree] = []
    kept: list[tuple[Worktree, Kept]] = []
    for worktree in worktrees:
        if worktree.checkout or worktree.path not in owners:
            continue
        owner = owners[worktree.path]
        evidence = Evidence(
            published=published(worktree.path, worktree.branch),
            fetched=owner not in unreached,
            remote=remotes[owner],
            landed=landed(worktree.path, worktree.base),
        )
        reason = held_by(worktree, evidence)
        if reason is None:
            finished.append(worktree)
        else:
            kept.append((worktree, reason))

    for worktree, reason in kept:
        say_info(f'{display_path(worktree.path)} — kept, {reason}')

    if not finished:
        scope = f' of {repo_filter}' if repo_filter else ''
        say_ok(f'Nothing to sweep: {len(kept)} worktree(s){scope} checked, none merged with its remote branch deleted')
        return 0

    ERR.print('')
    for worktree in finished:
        ERR.print(f'  [red]remove[/] {escape(display_path(worktree.path))}  [dim]{escape(worktree.branch)}[/]', highlight=False)
    ERR.print('')

    if not assume_yes:
        if not sys.stdin.isatty():
            # Usage, not failure: the remedy is an argument, and only that is worth
            # reinvoking with. Exit 1 here would be the code a half-finished removal
            # also returns, which a caller has to tell apart to know whether to retry.
            say_error(f'Refusing to remove {len(finished)} worktree(s) with no terminal to ask')
            say_info('Pass --yes to sweep unattended')
            return USAGE_ERROR
        if not confirm(f'Remove {len(finished)} worktree(s) and delete their branches?'):
            say_info('Nothing removed')
            return 0

    swept = 0
    for worktree in finished:
        # Re-read against the branch these changes actually merged into, immediately
        # before the write. Everything above was measured during the scan, and a session
        # that committed into the worktree since then would lose the only copy. Anything
        # other than a plain True holds the tree, so a read that failed cannot pass for
        # a branch with nothing left to lose — and it keeps its own reason here, as it
        # does on the scan path, because the two send a reader to different places.
        still_landed = landed(worktree.path, worktree.base)
        if still_landed is not True:
            reason = Kept.UNLANDED if still_landed is False else Kept.UNREADABLE_LANDING
            say_warning(f'{display_path(worktree.path)} — kept, {reason}')
            continue

        outcome, detail = dispose(owners[worktree.path], worktree.path, worktree.branch, force=False)
        if outcome is Disposal.NOT_REMOVED:
            say_warning(f'{display_path(worktree.path)} is still here: {detail}')
            continue
        if outcome is Disposal.BRANCH_KEPT:
            say_warning(f'Removed {display_path(worktree.path)}, but branch {worktree.branch} is still here: {detail}')
            continue
        swept += 1

    say_ok(f'Swept {swept} of {len(finished)} worktree(s)')
    return 0 if swept == len(finished) else 1
