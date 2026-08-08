"""The only module in this package that says the word `sudo`.

Three rules, each a property the bash it replaces could not have:

**One module escalates.** Everything else takes an injected `Privilege` and calls
`run`. `tests/system/test_privilege.py` greps the package for the word, so a
provider reaching for a direct escalation fails a test rather than working.

**Privilege is declared, not discovered.** A `Change` knows before anything runs
whether repairing it needs root, so the whole list can be shown at the prompt —
and `check` can say which of its findings will need a password without asking for
one.

**One prompt, at the front, or none.** A twenty-minute install that stops for a
password at minute twelve, and a run that fails at minute twelve *for want of* a
password, are the same defect. `authorize` runs once, before the first write, and
`run` passes `-n` afterwards so a provider physically cannot open a second
interactive prompt in the middle of the run.

`DECLINED` and `UNAVAILABLE` are not fatal. A privileged action is refused and
reported, and the unprivileged rest of the run still lands — which is what lets
the Docker and LXC harnesses converge without a passwordless-sudo carve-out, and
what makes `dotfiles apply` usable on a box where you do not have root.
"""

from __future__ import annotations

import dataclasses as dc
import enum
import os
import shutil
import threading
from collections.abc import Sequence

from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import err_console


class Authorization(enum.StrEnum):
    """How this run stands with respect to root, decided once."""

    NOT_NEEDED = 'not-needed'
    """Nothing in the plan asked for it, so nothing prompted."""

    ALREADY_ROOT = 'already-root'
    GRANTED = 'granted'
    DECLINED = 'declined'

    UNAVAILABLE = 'unavailable'
    """No `sudo` on the machine at all — the LXC container and the test harnesses."""


@dc.dataclass(frozen=True, slots=True)
class Escalation:
    """One privileged action, named at the prompt before it runs."""

    reason: str


class PrivilegeUnavailable(RuntimeError):
    """A privileged action was reached without an authorization that permits it."""


KEEPALIVE_SECONDS = 60.0
"""`pacman -Syu` and a full `apt upgrade` both outlive sudo's default five-minute
timestamp, and the second half of an install prompting again is the thing this
whole module exists to stop."""


class Privilege:
    """The authorization for one run, and the only door to a privileged command."""

    def __init__(self) -> None:
        self._state: Authorization | None = None
        self._keepalive: threading.Timer | None = None

    @property
    def state(self) -> Authorization:
        if self._state is None:
            raise PrivilegeUnavailable('authorize() has not run, so nothing may escalate yet')
        return self._state

    @property
    def permitted(self) -> bool:
        """Whether a privileged command would run rather than be refused."""
        return self._state in (Authorization.ALREADY_ROOT, Authorization.GRANTED)

    def authorize(self, escalations: Sequence[Escalation]) -> Authorization:
        """Ask once, with the list. Called by the run, never by a provider."""
        if self._state is not None:
            return self._state

        if not escalations:
            self._state = Authorization.NOT_NEEDED
        elif os.geteuid() == 0:
            self._state = Authorization.ALREADY_ROOT
        elif shutil.which('sudo') is None:
            self._state = Authorization.UNAVAILABLE
        else:
            self._state = self._ask(escalations)
        return self._state

    def run(self, command: Sequence[str], *, reason: str, output: Output = Output.QUIET) -> Completed:
        """Run one command as root, or refuse having written nothing."""
        if self.state is Authorization.ALREADY_ROOT:
            return run(list(command), output=output)
        if not self.permitted:
            raise PrivilegeUnavailable(reason)
        # `-n` after `-v`: the timestamp is already valid, so this cannot become a
        # second password prompt somewhere in the middle of a long run.
        return run(['sudo', '-n', *command], output=output)

    def _ask(self, escalations: Sequence[Escalation]) -> Authorization:
        err_console.print(f'[bold]{len(escalations)} action(s) need root:[/]')
        for escalation in escalations:
            err_console.print(f'  {escalation.reason}')

        # Output.DATA inherits this process's streams, which is what makes the
        # password prompt reach the terminal at all: sudo reads from /dev/tty but
        # writes its prompt to stderr, and a captured stderr swallows it.
        granted = run(['sudo', '-v'], output=Output.DATA).ok
        if not granted:
            return Authorization.DECLINED
        self._start_keepalive()
        return Authorization.GRANTED

    def _start_keepalive(self) -> None:
        def refresh() -> None:
            run(['sudo', '-n', '-v'], output=Output.QUIET)
            self._start_keepalive()

        self._keepalive = threading.Timer(KEEPALIVE_SECONDS, refresh)
        self._keepalive.daemon = True
        self._keepalive.start()

    def stop(self) -> None:
        """Cancel the keepalive. A daemon thread would not hold the process open,
        but a timer still pending at exit refreshes a timestamp nobody will use."""
        if self._keepalive is not None:
            self._keepalive.cancel()
            self._keepalive = None


def refusal(state: Authorization) -> str:
    """Why a privileged action did not run, in the words the run should print."""
    if state is Authorization.UNAVAILABLE:
        return 'needs root and this machine has no sudo'
    if state is Authorization.DECLINED:
        return 'needs root and authorization was declined'
    return 'needs root, which this run never asked for'
