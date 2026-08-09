"""The only module in this package that says the word `sudo`.

**One module escalates.** Everything else takes an injected `Privilege` and calls
`run`. `tests/system/test_privilege.py` greps the package for the word, so a
provider reaching for a direct escalation fails a test rather than working.

**Privilege is declared, not discovered.** A `Change` knows before anything runs
whether repairing it needs root, so `plan` can say how many of its findings will
need a password without asking for one. That half is worth keeping and costs
nothing.

**Asked for when a write needs it, and not before.** This reverses the rule the
module was built on — "one prompt, at the front, or none" — on evidence: **keeping
a sudo timestamp alive does not work on macOS.** The front prompt was buying a
property the platform will not give, and paying for it with a password prompt on
machines that turned out to need nothing. The model is brew's, and every other
installer's. `authorize()`, `Escalation` and the self-re-arming keepalive timer
went with the rule.

The cost is honest and stated at the prompt: a long run can stop for a password
part-way through. `plan` says in advance how many writes will need one.

`DECLINED` and `UNAVAILABLE` are not fatal, and that has not changed. A privileged
action is refused and reported, and the unprivileged rest of the run still lands —
which is what lets the Docker and LXC harnesses converge without a
passwordless-sudo carve-out, and what makes `dotfiles apply` usable on a box where
you do not have root. Once declined, it stays declined for the run: a machine
without a password is not going to grow one between two writes, and asking again
per item is how a refusal becomes a wall of prompts.
"""

from __future__ import annotations

import enum
import os
import shutil

from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.output import err_console


class Authorization(enum.StrEnum):
    """How this run stands with respect to root."""

    NOT_NEEDED = 'not-needed'
    """Nothing has asked for it yet, so nothing has prompted."""

    ALREADY_ROOT = 'already-root'
    GRANTED = 'granted'
    DECLINED = 'declined'

    UNAVAILABLE = 'unavailable'
    """No `sudo` on the machine at all — the LXC container and the test harnesses."""


class PrivilegeUnavailable(RuntimeError):
    """A privileged action was reached and root could not be obtained."""


class Privilege:
    """The authorization for one run, and the only door to a privileged command."""

    def __init__(self, *, offer: bool = True) -> None:
        self._state = Authorization.NOT_NEEDED
        self._offer = offer
        """Whether this run may prompt at all. False is how a caller that knows it
        must not block — a scheduled check, a resource with nothing privileged —
        says so without the module having to guess."""

    @property
    def state(self) -> Authorization:
        return self._state

    @property
    def permitted(self) -> bool:
        """Whether a privileged command would run rather than be refused.

        Reads what has been settled so far and never prompts, so a caller can ask
        without side effects.
        """
        return self._state in (Authorization.ALREADY_ROOT, Authorization.GRANTED)

    def acquire(self, reason: str) -> Authorization:
        """Obtain root if this run has not already settled the question.

        Prompts at most once. A machine that answered UNAVAILABLE or DECLINED keeps
        that answer for the rest of the run rather than asking again per item.
        """
        if self._state is not Authorization.NOT_NEEDED:
            return self._state

        if os.geteuid() == 0:
            self._state = Authorization.ALREADY_ROOT
        elif shutil.which('sudo') is None:
            self._state = Authorization.UNAVAILABLE
        elif not self._offer:
            self._state = Authorization.DECLINED
        else:
            self._state = self._ask(reason)
        return self._state

    def run(self, command: list[str] | tuple[str, ...], *, reason: str, output: Output = Output.QUIET) -> Completed:
        """Run one command as root, or refuse having written nothing."""
        if self.acquire(reason) is Authorization.ALREADY_ROOT:
            return run(list(command), output=output)
        if not self.permitted:
            raise PrivilegeUnavailable(reason)
        return run(['sudo', *command], output=output)

    def _ask(self, reason: str) -> Authorization:
        """Name what the password is for. A bare prompt in the middle of a long run
        is indistinguishable from something having gone wrong."""
        err_console.print(f'[bold]needs root:[/] {reason}')

        # Output.DATA inherits this process's streams, which is what makes the
        # password prompt reach the terminal at all: sudo reads from /dev/tty but
        # writes its prompt to stderr, and a captured stderr swallows it.
        return Authorization.GRANTED if run(['sudo', '-v'], output=Output.DATA).ok else Authorization.DECLINED


def refusal(state: Authorization) -> str:
    """Why a privileged action did not run, in the words the run should print."""
    if state is Authorization.UNAVAILABLE:
        return 'needs root and this machine has no sudo'
    if state is Authorization.DECLINED:
        return 'needs root and authorization was declined'
    return 'needs root, which this run never asked for'
