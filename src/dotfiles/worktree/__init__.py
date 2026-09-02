"""Give a session its own index, and land it on main without a PR.

    worktree new <slug>    isolate before touching a repo another session is in
    worktree spawn [slug]  start a Claude session in a pane; a slug gives it a worktree
    worktree land          rebase, push onto the default branch, then clean up
    worktree sweep         dispose of every worktree whose work already merged
    worktree list          every worktree on this machine, or one repo's
    worktree show          what one worktree carries, and who is in it
    worktree choose        pick one with fzf; prints the path it chose

A working tree is shared state. Every session standing in one shares its index,
its untracked files, and the tree pre-commit assembles to run hooks against — so
a second session commits the first one's staged work, and whole-repo hooks lint a
tree that neither session ever had. See standards/git-workflow.md § "Concurrent
sessions isolate with a worktree".

The branch `new` creates is not a proposal. `land` pushes it straight onto main
as a fast-forward, so a single commit stays a single commit and the resulting
history is identical to having committed on main directly. A PR is still there
for work that grew into a large feature — push the branch and open one — which is
why the landing decision is made at the end rather than guessed at the start.

A worktree that went the PR route is finished somewhere this tool never sees: the
merge happens on the forge and the branch is deleted there, so `land` never runs
and nothing disposes of the directory. `sweep` is what collects them, from wherever
you are standing, and it removes one only when the tree is clean, no session is in
it, its changes are already on the base branch, and the remote branch it was pushed
to is gone. `drop` remains the verb for work you are abandoning rather than
finishing.

`list`, `show` and `choose` read every repo on the machine rather than the one you
happen to be standing in: the worktrees exist because several sessions are running
at once, and the one you want is as often in another repo as in this one.
$WORKTREE_ROOT is the whole index — a repo has a directory there exactly when it
has a worktree — and each one's checkout is read back out of git. No registry of
repos is consulted, because this app is deployed to machines that have none.

`spawn` is `new` with a session in it. The dozen steps between deciding a repo
needs an agent and having one — cut the worktree, open a pane, launch `claude`
against a written brief, wait for the registry to name it — are one command, so
a caller's next move is a message to the name it returns. A slug is the branch,
so `spawn <slug>` is a worker with a worktree and `spawn` with no slug is a
session standing in the primary checkout with no branch at all. That second form
is what a reviewer needs: it reads a pull request from any checkout, and a
session inside a worktree is refused any `git -C` that leaves it.

An occupied worktree refuses and an occupied checkout warns. A worktree exists to
hold one session; a checkout holding others is the normal condition of every repo
anyone is working in, so refusing there would make a review impossible whenever
the repo is busy. What makes sharing one tolerable is that the no-slug session
gets no branch, and has nothing of its own to commit.

It never merges and never starts anything that merges. The chain it enables ends
at a pull request that is ready. Merging is a separate act, and green checks are
not permission for it.

stdout carries what a command produced: the table, the JSON, the path `choose`
picked, the path `new` created, the session name `spawn` started. Everything
written for a human to read goes to stderr, so `cd "$(worktree choose)"` cannot
pick up a warning instead of a path.

Every subprocess is echoed to stderr before it runs, indented and green, exactly
as it could be re-typed. A fetch, a rebase and a push onto the default branch are
what `land` is, and a tool that moves branches on your behalf should say which
ones it moved. `-q` on any command hides them; the verdict keeps its channel.

Python rather than shell because the work stopped being control flow: measuring
columns, matching sessions to worktrees by path, and emitting one set of rows as
both a table and JSON. The shell version padded columns in awk and passed records
on the ASCII unit separator to stop `read` from eating empty fields.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

CHECK = '✓'
CROSS = '✗'
WARNING = '▲'
INFO = '●'

COLUMNS = ('LOCATION', 'BRANCH', 'AHEAD', 'STATE', 'SESSION')

# What a caller retries with different arguments, as against a run that failed on its own terms.
# argparse already exits 2 for a flag it cannot parse; a refusal whose remedy is a flag is the
# same answer reached later, and collapsing it into 1 loses the only distinction that matters.
USAGE_ERROR = 2

# fzf splits the row it is given, hands back the whole row, and searches only the
# fields it displays. The path rides in front as the handle, the rendered line
# behind it as the thing a human reads and types against.
FZF_DELIMITER = '\t'

BRIEF_PROMPT = 'Read {brief} and carry out the work it describes. It names the session to report to.'
"""What the spawned pane runs `claude` with.

A brief is pages long and does not survive being quoted into a command line, so the
prompt is a pointer and the file carries the work. The second sentence is what makes
the session look for its reporting address rather than finishing in silence.
"""

REGISTRATION_TIMEOUT = 60.0
"""How long a spawn waits to be told the name of the session it just started.

Registration is not instant — measured at about sixteen seconds — and the name is the
whole reason a caller runs this rather than `tmux split-window` itself.
"""

POLL_SECONDS = 1.0

MAIN_PANE_WIDTH = '66%'
"""The caller's share of the window once panes are stacked beside it.

A percentage rather than a column count, because tmux resolves it against whatever
window the caller is in and holds it across a resize. Two thirds because the caller's
pane is being read continuously and the spawned ones are being watched — so the larger
share goes to the one carrying prose. tmux's own default is 80 columns, which is the
value that made this worth setting.
"""


class State(StrEnum):
    CLEAN = 'clean'
    DIRTY = 'dirty'


class Kept(StrEnum):
    """Why a sweep left a worktree standing.

    Every member names something that could still be lost, or something that could
    not be measured. `held_by` ends in a bare "remove", so an unanswerable check
    resolving to a falsy value is a deletion authorised by a question nobody asked.
    Five members exist only to stop that: SESSIONS_UNREADABLE, UNFETCHED_REMOTE,
    UNFETCHED_BASE, UNREADABLE_LANDING and REMOTE_UNREADABLE.
    """

    DIRTY = 'uncommitted changes'
    SESSION = 'a session is standing in it'
    SESSIONS_UNREADABLE = 'claude-sessions could not say whether anyone is in it'
    DETACHED = 'a detached HEAD, so it has no branch to have merged'
    UNFETCHED_REMOTE = 'its origin could not be reached, so nothing about the remote is known'
    UNFETCHED_BASE = 'its base branch has never been fetched, so nothing can be counted'
    UNREADABLE_LANDING = 'git could not say whether its changes are on the base branch'
    UNLANDED = 'the base branch does not match it at the paths it touched'
    UNPUBLISHED = 'never pushed under its own name'
    REMOTE_LIVE = 'its remote branch still exists'
    REMOTE_UNREADABLE = "git could not list origin's branches"


class Pane(StrEnum):
    """What tmux says about a pane a spawn is waiting on.

    DEAD and GONE are the same event seen with and without a corpse. `spawn` turns
    `remain-on-exit` on for the pane it made, so a command that fails to start leaves
    its exit status behind to be read; a pane destroyed before that option lands has
    nothing left to say. Collapsing them would throw away the only diagnosis available
    for the failure that is otherwise invisible.
    """

    RUNNING = 'running'
    DEAD = 'dead'
    GONE = 'gone'


class Registration(StrEnum):
    """How the wait for a spawned session ended.

    Only REGISTERED produces a name, and a name is the whole product of the command.
    The rest are apart because they need different things done about them: a dead pane is
    a launch that failed, a timeout is a session that may yet appear, an unreadable
    registry is a question that was never answered, and a registry that answered without
    a pid is a sibling app whose output changed shape.

    That last one would otherwise present as a timeout blaming `claude`, since the pane is
    healthy and the wait simply never resolves. The producer is `claude-sessions`, and
    nothing here can make it emit a field — but the report can at least name it.
    """

    REGISTERED = 'registered'
    PANE_DIED = 'pane_died'
    TIMED_OUT = 'timed_out'
    REGISTRY_UNREADABLE = 'registry_unreadable'
    NO_PID_IN_REGISTRY = 'no_pid_in_registry'


class Fault(StrEnum):
    """What a refusal *is*, apart from the sentence describing it.

    A caller branching on a refusal, and a test asserting one, otherwise have only the
    prose — so rewording an error changes what they match. The sentence is written for a
    person and is free to change; the member is what anything else compares against.
    """

    NO_TMUX = 'no_tmux'
    TOOL_MISSING = 'tool_missing'
    BRIEF_MISSING = 'brief_missing'
    BRIEF_EMPTY = 'brief_empty'
    WORKTREE_OCCUPIED = 'worktree_occupied'
    SESSIONS_UNREADABLE = 'sessions_unreadable'
    NOT_A_WORKTREE = 'not_a_worktree'
    SPLIT_REFUSED = 'split_refused'


class Refused(Exception):
    """A refusal a human has to read: the reason, then anything that unblocks it.

    `fault` is absent on the refusals that predate it, which is why it is optional rather
    than required — a verb adopting it is a change to that verb.
    """

    def __init__(self, reason: str, *hints: str, fault: Fault | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.hints = hints
        self.fault = fault


@dataclass(frozen=True)
class Session:
    """A live Claude Code session, as claude-sessions reports it."""

    name: str
    status: str
    waiting: str | None
    cwd: Path
    tmux: str | None
    # The process the registry is keyed on. Optional because only `spawn` reads it, and a
    # row is worth having in a listing whether or not it carried one.
    pid: int | None = None


@dataclass(frozen=True)
class Worktree:
    """One working tree, either a checkout or something cut from it."""

    repo: str
    path: Path
    checkout: bool
    branch: str
    base: str
    ahead: int | None
    behind: int | None
    state: State
    # None when claude-sessions could not be asked, () when it answered and nobody is here.
    # A reader that gates on this needs the two apart; `ahead` carries the same split.
    sessions: tuple[Session, ...] | None
    # A detached HEAD has no branch, so nothing can be asked about where its commits are.
    detached: bool = False

    def as_json(self) -> dict[str, Any]:
        return {
            'repo': self.repo,
            'path': str(self.path),
            'checkout': self.checkout,
            'branch': self.branch,
            'base': self.base,
            'ahead': self.ahead,
            'behind': self.behind,
            'state': str(self.state),
            'detached': self.detached,
            'sessions': None
            if self.sessions is None
            else [
                {
                    'name': session.name,
                    'status': session.status,
                    'waiting': session.waiting,
                    'cwd': str(session.cwd),
                    'tmux': session.tmux,
                    'pid': session.pid,
                }
                for session in self.sessions
            ],
        }


@dataclass(frozen=True)
class Destination:
    """Where a spawned session stands, and what it may commit on.

    `created` separates a worktree this run cut from one it attached to, which is the
    only thing that decides whether a later failure may take it away again.
    """

    path: Path
    branch: str | None
    worktree: bool
    created: bool = False


@dataclass(frozen=True)
class Arrival:
    """How the wait for a session ended, and whatever the pane said if it died.

    Not `Landing`, which would put a second subject on `land` in the one file where that
    verb already means pushing a branch onto the default branch.

    `status` and `output` are only ever set on PANE_DIED, and either can still be absent
    there — a pane destroyed before `remain-on-exit` took hold leaves neither.
    """

    registration: Registration
    session: str | None = None
    status: int | None = None
    output: str = ''


@dataclass(frozen=True)
class Spawned:
    """One session this command started, and everything a caller needs to reach it."""

    repo: str
    path: Path
    branch: str | None
    worktree: bool
    pane: str
    brief: Path
    arrival: Arrival

    def as_json(self) -> dict[str, Any]:
        return {
            'repo': self.repo,
            'path': str(self.path),
            'branch': self.branch,
            'worktree': self.worktree,
            'pane': self.pane,
            'brief': str(self.brief),
            'session': self.arrival.session,
            # Why a null `session` is null, for a caller that has to say something about it.
            # No `registered` boolean beside it: `session` already carries whether there is
            # one, and a second field saying the same thing is one more that can disagree.
            'registration': str(self.arrival.registration),
            'exit_status': self.arrival.status,
        }


@dataclass(frozen=True)
class Evidence:
    """Everything read from git or the machine before a sweep decides anything.

    Gathering it up here is what makes `held_by` a function of its arguments: the
    decision to delete a directory is then reachable in a test that has no repository
    behind it, and every branch of it can be reached on purpose rather than by
    building the state that happens to produce it.
    """

    published: bool
    fetched: bool
    remote: frozenset[str] | None
    landed: bool | None


class Disposal(StrEnum):
    """Which half of a disposal happened, so a caller can say the true sentence.

    The directory and the ref go separately, and after BRANCH_KEPT the directory is
    already gone. A single failure value cannot express that, and both callers then
    report a worktree still standing when what survived was the branch.
    """

    DONE = 'done'
    NOT_REMOVED = 'not_removed'
    BRANCH_KEPT = 'branch_kept'


def require_tool(name: str, why: str) -> None:
    if shutil.which(name) is None:
        raise Refused(f'{name} is not installed', why, fault=Fault.TOOL_MISSING)
