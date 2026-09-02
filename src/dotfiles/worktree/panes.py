"""tmux: where a spawned session goes, and how the wait for it ends.

Every question about a pane is asked of tmux rather than of the process table,
and each one names the command that can actually answer it — `list-panes` for
whether a pane exists, `display-message` for its pid, `capture-pane` for what it
printed. The comments on each say which reading was wrong before.
"""

from __future__ import annotations

import os
import shlex
import shutil
import time
from collections.abc import Sequence
from pathlib import Path

from rich.markup import escape

from dotfiles.worktree import POLL_SECONDS
from dotfiles.worktree import Arrival
from dotfiles.worktree import Fault
from dotfiles.worktree import Pane
from dotfiles.worktree import Refused
from dotfiles.worktree import Registration
from dotfiles.worktree import Session
from dotfiles.worktree import Spawned
from dotfiles.worktree import output
from dotfiles.worktree import require_tool
from dotfiles.worktree.output import ERR
from dotfiles.worktree.output import run
from dotfiles.worktree.output import say_error
from dotfiles.worktree.output import say_info
from dotfiles.worktree.output import say_ok
from dotfiles.worktree.output import say_warning
from dotfiles.worktree.repo import display_path
from dotfiles.worktree.survey import live_sessions


def capture_pane(pane: str) -> str | None:
    """What is on a session's screen, colour included, or None if tmux cannot say."""
    if shutil.which('tmux') is None:
        return None
    result = run(['tmux', 'capture-pane', '-ep', '-t', pane])
    return result.stdout.rstrip() if result.returncode == 0 else None


def require_caller_pane() -> str:
    """The pane a spawn splits, which is the caller's own.

    tmux exports $TMUX_PANE into everything it starts, so a session's shell already
    carries the address of the pane that session is in and nothing has to be passed.
    Outside tmux there is no pane to split, and a session started anyway would be a
    process nobody can see — which is the failure this refuses rather than produces.
    """
    require_tool('tmux', 'A spawned session is a tmux pane, and there is nowhere else to put one')
    pane = os.environ.get('TMUX_PANE')
    if not os.environ.get('TMUX') or not pane:
        raise Refused(
            'Not inside tmux, so there is no pane to split',
            'Run this from a session that is itself in a tmux pane',
            fault=Fault.NO_TMUX,
        )
    return pane


def open_pane(caller: str, workdir: Path, prompt: str, *, below: bool) -> str:
    """Split the caller's pane, start a session in it, and return the new pane's id.

    -d leaves the focus where it was. The caller is mid-turn when it runs this, and a
    spawn that moves the cursor interrupts whoever is reading that pane.

    -P -F is tmux's own answer for which pane it just made, so nothing has to be matched
    back afterwards by comparing pane lists before and against after.

    `remain-on-exit` is turned on immediately after, and it is what makes a failed
    launch diagnosable: without it a command that cannot start destroys its pane in
    milliseconds, leaving no error text, no exit status and no pane — so the only
    symptom is a session that never registers. Setting it can itself lose that race,
    which is why `pane_state` still has a GONE to report.
    """
    created = run(
        [
            'tmux',
            'split-window',
            '-d',
            '-v' if below else '-h',
            '-P',
            '-F',
            '#{pane_id}',
            '-t',
            caller,
            '-c',
            str(workdir),
            f'claude {shlex.quote(prompt)}',
        ]
    )
    if created.returncode != 0:
        raise Refused(created.stderr.strip() or 'tmux refused to split the pane', fault=Fault.SPLIT_REFUSED)

    pane = created.stdout.strip()
    run(['tmux', 'set-option', '-p', '-t', pane, 'remain-on-exit', 'on'])
    return pane


def stack_beside(caller: str, width: str) -> None:
    """Put the caller in the large left pane, with everything spawned stacked right.

    tmux halves the pane it splits, so a coordinator that dispatched four agents would
    be reading its own work in a sixteenth of the window. `main-vertical` collapses that
    into one stack, and the width says how much of the window the reading pane keeps —
    without it tmux uses its own `main-pane-width` default of 80 columns, which puts the
    narrow pane on the side that carries prose.

    `main-vertical` assigns the main pane **by index**, so the caller is swapped into the
    window's first slot beforehand or the large pane goes to whichever pane happens to
    lead the window. That is not an edge case: a session is rarely the first pane of the
    window it is in. The swap is no more intrusive than the layout it precedes, which
    re-tiles every pane in the window either way.

    Only ever called for a split beside. A split below is a reviewer deliberately placed
    under its author, and this layout would lift it into the right-hand stack.

    A failure here is reported and not raised. The session is already running by this
    point, and losing it over a cosmetic call would be the worse outcome.
    """
    window = run(['tmux', 'display-message', '-p', '-t', caller, '#{window_id}'])
    if window.returncode != 0:
        say_warning('tmux could not name the window, so the layout is left as it is')
        return

    target = window.stdout.strip()
    leader = run(['tmux', 'list-panes', '-t', target, '-F', '#{pane_id}'])
    first = leader.stdout.splitlines()[0] if leader.returncode == 0 and leader.stdout.strip() else caller
    if first != caller:
        run(['tmux', 'swap-pane', '-s', caller, '-t', first])

    run(['tmux', 'set-window-option', '-t', target, 'main-pane-width', width])
    if run(['tmux', 'select-layout', '-t', target, 'main-vertical']).returncode != 0:
        say_warning('tmux refused the layout, so the panes are left as the split arranged them')
        return

    report_width(caller, width)


def usable_width(value: str) -> bool:
    """Whether tmux will actually honour this as a pane width: columns, or a percentage.

    The test is what it honours rather than what it parses, because those are different
    sets and only the first is useful. `abc`, `-5`, `0` and `999%` are each answered with
    exit 0 and then resolve to the 80-column default — the value `--width` exists to
    replace — so an unusable argument produces exactly the layout the flag was passed to
    avoid. No return code anywhere in the sequence carries the failure, which makes this
    the only place it can be caught.
    """
    number = value.removesuffix('%')
    if not number.isdigit() or int(number) < 1:
        return False
    return int(number) <= 100 if value.endswith('%') else True


def report_width(caller: str, width: str) -> None:
    """Say so when the caller did not end up with the share it asked for.

    Every tmux call above returns 0 whatever it was handed, `main-pane-width` included —
    so the only evidence that the layout did what it was told is the geometry afterwards.
    Without this the three ways it can go wrong all produce the outcome it exists to
    prevent, silently: the caller in the narrow pane and the run exiting 0.
    """
    measured = run(['tmux', 'display-message', '-p', '-t', caller, '#{pane_width} #{window_width}'])
    if measured.returncode != 0 or len(measured.stdout.split()) != 2:
        return

    got, window = (int(part) for part in measured.stdout.split())
    wanted = window * int(width.rstrip('%')) // 100 if width.endswith('%') else int(width)
    if abs(got - wanted) > max(2, wanted // 10):
        say_warning(f'This pane is {got} columns of {window}, not the {wanted} that --width asked for')


def pane_state(pane: str) -> tuple[Pane, int | None]:
    """Whether a pane is running, dead with a status to read, or gone entirely.

    `display-message` cannot answer the first question: it exits 0 and prints an empty
    line for a pane that no longer exists, so a check built on it reads every dead pane
    as healthy. `list-panes` refuses, and that refusal is the existence test.

    It answers for the whole window the pane is in rather than for the pane, so the row
    has to be found by id — a window's other panes are the caller's own and say nothing
    about this one.
    """
    listed = run(['tmux', 'list-panes', '-t', pane, '-F', '#{pane_id} #{pane_dead} #{pane_dead_status}'])
    if listed.returncode != 0:
        return Pane.GONE, None

    for row in listed.stdout.splitlines():
        pane_id, _, rest = row.partition(' ')
        if pane_id != pane:
            continue
        dead, _, status = rest.partition(' ')
        if dead != '1':
            return Pane.RUNNING, None
        return Pane.DEAD, int(status) if status.strip().isdigit() else None
    return Pane.GONE, None


def last_words(pane: str) -> str:
    """What a dead pane printed before it died, scrollback included.

    Without `-S -` the capture starts at the top of the visible pane, and a command that
    wrote one line and exited leaves that line above the window — so the capture comes
    back as blank lines and tmux's own "Pane is dead" notice, which says nothing the
    exit status has not already said.
    """
    captured = run(['tmux', 'capture-pane', '-p', '-S', '-', '-E', '-', '-t', pane])
    if captured.returncode != 0:
        return ''
    return '\n'.join(line for line in captured.stdout.splitlines() if line.strip())


def pane_process(pane: str) -> int | None:
    """The pid of the process tmux started in a pane, or None where it cannot be read.

    For a pane this command made, that pid is the `claude` process itself, which is what
    the session registry is keyed on. tmux runs a pane command through `sh -c`, and a
    simple command is exec'd rather than forked, so the pid survives the shell.

    It is not the session's pid for a pane someone typed `claude` into — there it is the
    shell, and the session is its child. That is exactly why this is only ever asked about
    a pane this command just created, and never used to identify a session in general.
    """
    found = run(['tmux', 'display-message', '-p', '-t', pane, '#{pane_pid}'])
    process = found.stdout.strip()
    return int(process) if found.returncode == 0 and process.isdigit() else None


def claimants(sessions: Sequence[Session], pane: str) -> list[Session]:
    """Every registered session claiming one pane, by the only part of the address that
    survives the pane being moved.

    The registry spells a pane as `<tmux session>:@<window>.%<pane>`, and only the last
    field is compared. The other two rot when the pane moves. `tmux break-pane` gives it a
    new window and `tmux join-pane` can give it a new tmux session, while the registry
    keeps the address it recorded at startup — so the address as a whole names a place the
    pane has left.

    A tmux session name may itself contain a dot, so the split has to come from the right.
    """
    return [session for session in sessions if session.tmux and session.tmux.rsplit('.', 1)[-1] == pane]


def session_in_pane(sessions: Sequence[Session], pane: str, pane_pid: int | None) -> str | None:
    """The registered session running in one pane.

    Not matched on the working directory, which is ambiguous by design here. A session
    with no slug stands in the primary checkout on purpose, and that is the one directory
    several sessions share — so a directory match returns whichever of them the registry
    lists first. Handing a caller the wrong name sends a real instruction to a session that
    never asked for it.

    A pane id does not identify a session on its own. Two things break it. A `claude`
    started from inside another session's pane inherits that pane's $TMUX_PANE and
    registers against it, so one pane can carry a second row for as long as that child
    lives. And ids are numbered per tmux server rather than per machine, so a row left by
    a session whose server is gone resolves to a live pane on another server belonging to
    someone else.

    The pid separates them wherever tmux will give one up, and it is compared rather than
    used as a tiebreak — a claimant that registers before the real session would otherwise
    be answered with, and the caller's next act is to send that name an instruction.

    Where `pane_pid` could not be read the pane alone decides, which is the fallback and
    not the rule. It is reached when tmux will not report a pid for the pane, which almost
    always means the pane is already gone — and the wait has a pane check of its own for
    exactly that.
    """
    for session in claimants(sessions, pane):
        if pane_pid is None or session.pid == pane_pid:
            return session.name
    return None


def await_registration(pane: str, timeout: float) -> Arrival:
    """Wait for the new session to appear in the registry, and name it.

    The name is the product of the whole command: a caller's next move is a message
    addressed to it, and there is nothing to address until the session has registered.

    The pane is watched alongside, because a launch that failed to start leaves no
    session to wait for — and without this the whole timeout is spent to report nothing
    but that the timeout elapsed. The corpse is read for its exit status and then killed,
    since `remain-on-exit` would otherwise leave a dead pane in the window forever.

    The command echo is off for the loop. It is one `claude-sessions` per second, and a
    reader watching for a name does not need sixty copies of the same line.
    """
    say_info('Waiting for the session to register')
    deadline = time.monotonic() + timeout
    echoing = output.ECHO
    output.set_echo(False)
    try:
        # Read once, before anything has had time to move: the pane's process does not
        # change for its lifetime, and it is what tells the session apart from any other
        # row claiming the same pane.
        pane_pid = pane_process(pane)
        while time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)

            sessions = live_sessions()
            if sessions is None:
                return Arrival(Registration.REGISTRY_UNREADABLE)
            name = session_in_pane(sessions, pane, pane_pid)
            if name:
                return Arrival(Registration.REGISTERED, session=name)

            # A row claiming this pane and carrying no pid at all is the producer's output
            # having changed shape, not a session still starting. Waiting it out would
            # spend the whole timeout and then blame `claude` for a pane that is healthy.
            if pane_pid is not None and any(claimant.pid is None for claimant in claimants(sessions, pane)):
                return Arrival(Registration.NO_PID_IN_REGISTRY)

            state, status = pane_state(pane)
            if state is Pane.RUNNING:
                continue
            printed = last_words(pane) if state is Pane.DEAD else ''
            run(['tmux', 'kill-pane', '-t', pane])
            return Arrival(Registration.PANE_DIED, status=status, output=printed)
    finally:
        output.set_echo(echoing)

    return Arrival(Registration.TIMED_OUT)


def announce(spawned: Spawned, timeout: float) -> None:
    """Everything a human reads about a spawn, on stderr beside the rest of it."""
    say_ok(f'Spawned in pane {spawned.pane}, {display_path(spawned.path)}')
    if spawned.branch:
        say_info(f'branch {spawned.branch}')
    say_info(f'brief {display_path(spawned.brief)}')

    arrival = spawned.arrival
    match arrival.registration:
        case Registration.REGISTERED:
            say_ok(f'Session {arrival.session}')
        case Registration.PANE_DIED:
            status = 'an unreadable status' if arrival.status is None else f'status {arrival.status}'
            say_error(f'`claude` exited with {status} before a session registered')
            if arrival.output:
                say_info('what the pane printed:')
                ERR.print(escape(arrival.output), highlight=False)
        case Registration.TIMED_OUT:
            say_error(f'No session registered in {spawned.pane} within {timeout:g}s')
            say_info('The pane is still running; `claude-sessions` will name it if it registers late')
        case Registration.REGISTRY_UNREADABLE:
            say_error('claude-sessions stopped answering, so the session in that pane cannot be named')
        case Registration.NO_PID_IN_REGISTRY:
            say_error('claude-sessions reported a session in that pane with no pid, so it cannot be told from a nested one')
            say_info('The pane is running; the field this needs is `pid` in claude-sessions --json')
