"""The only module in this package that says the word `sudo`.

**One module escalates.** Everything else takes an injected `Escalates` and calls
`run`. `tests/resources/test_privilege.py` greps the package for the word, so a
provider reaching for a direct escalation fails a test rather than working.

`Escalates` is the capability and `Privilege` is the one implementation of it that
holds a sudo. Nothing outside this module names the class, so a caller cannot
reach `acquire` and a test can hand over a stand-in that spends no password.

**Privilege is declared, not discovered.** A `Change` knows before anything runs
whether repairing it needs root, so `plan` can say how many of its findings will
need a password without asking for one. That half is worth keeping and costs
nothing.

**Asked for when a write needs it, and not before.** *Rejected: one prompt at the
front, or none.* **Keeping a sudo timestamp alive does not work on macOS**, so a
front prompt buys a property the platform will not give and pays for it with a
password prompt on machines that turn out to need nothing. The model is brew's,
and every other installer's.

The cost is honest and stated at the prompt: a long run can stop for a password
part-way through. `plan` says in advance how many writes will need one.

**Passwordless is not the same question as prompting, and asking the wrong one
declined root on every headless machine.** `acquire` checks `sudo -n true` before
it considers prompting, because a box with `NOPASSWD` needs no terminal and no
password. `_already_granted` carries what that probe has to get right.

`DECLINED` and `UNAVAILABLE` are not fatal. A privileged
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
import re
import shutil
from collections.abc import Sequence
from typing import Protocol

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


class Escalates(Protocol):
    """What a caller needs from an authorization: run a command, read the answer.

    The whole surface. `acquire`, `permitted` and `_ask` belong to the one module
    that escalates, and nothing outside it reads them — so a parameter annotated
    `Privilege` is asking for more than it uses, and a recording stand-in that
    spends no sudo cannot satisfy it.

    Named for the capability rather than for the class, because the two are not
    the same thing: `Privilege` is where the sudo lives, and this is what a
    provider is handed.
    """

    @property
    def state(self) -> Authorization: ...

    def run(self, command: list[str] | tuple[str, ...], *, reason: str, output: Output = Output.QUIET) -> Completed: ...


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
        elif _already_granted():
            self._state = Authorization.GRANTED
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


def _already_granted() -> bool:
    """Whether sudo would run right now without asking anyone anything.

    **`sudo -n true`, and never `sudo -v`.** The two look interchangeable and are
    not: `-v` means *validate*, which authenticates and therefore wants a
    terminal, so it fails with "sudo: A terminal is required to authenticate" on a
    box with `NOPASSWD: ALL` where sudo plainly works. Every headless caller is
    that box — `docker exec` without `-t`, a systemd timer, cron, an SSH command,
    CI — and because the answer is cached for the run, one wrong probe declined
    root for *everything* after it.

    One wrong probe therefore refuses the system packages, the Go toolchain, every
    `go install` behind it at exit 127, and the zdotdir file — all reported as
    "authorization was declined" while `sudo -n true` exits 0 beside them.

    Asked before `offer` rather than after, deliberately: a caller that must not
    block still gets root where taking it blocks nobody. A live sudo timestamp
    answers yes here too, which is the same property and equally welcome.
    """
    return run(['sudo', '-n', 'true'], output=Output.QUIET).ok


def passwordless(command: Sequence[str]) -> bool:
    """Whether sudo would run exactly `command` as root for this account, asking nobody.

    Read from `sudo -n -l`, never from the rule files. /etc/sudoers.d is 0750 on
    Arch, so an unprivileged read cannot even see the file names. Asking sudo
    also answers for every rule at once: a container template's `NOPASSWD: ALL`
    grants the command as surely as a drop-in naming it.

    sudo lists without a password once any of the account's rules is NOPASSWD,
    and refuses to list otherwise. A refusal is therefore already the answer no.
    """
    listed = run(['sudo', '-n', '-l'], output=Output.QUIET)
    return listed.ok and last_rule_waives_password(listed.stdout, ' '.join(command))


RULES_HEADING = 'may run the following commands'
TAG = re.compile(r'^([A-Z_]+):\s*')


def last_rule_waives_password(listing: str, command: str) -> bool:
    """Whether the last rule in a `sudo -l` listing matching `command` as root is NOPASSWD.

    The last match decides because that is how sudoers resolves a command that
    several rules match. Arch's stock `%wheel ALL=(ALL:ALL) ALL` lists above every
    drop-in, and a drop-in naming the command NOPASSWD below it wins.

    A tag carries to the commands after it on the same line, as it does in the
    rule. A command listed without arguments matches any, so the bare program is
    a match too. A negated command that matches denies outright.
    """
    lines = listing.splitlines()
    start = next((i + 1 for i, line in enumerate(lines) if RULES_HEADING in line), len(lines))
    program = command.split()[0]
    waived = False
    for line in lines[start:]:
        runas, closed, spec = line.strip().removeprefix('(').partition(')')
        if not closed or not {'root', 'ALL'} & {user.strip() for user in runas.split(':')[0].split(',')}:
            continue
        nopasswd = False
        for entry in spec.split(','):
            entry = entry.strip()
            while tag := TAG.match(entry):
                nopasswd = {'NOPASSWD': True, 'PASSWD': False}.get(tag[1], nopasswd)
                entry = entry[tag.end() :]
            negated = entry.startswith('!')
            if entry.lstrip('!').strip() in ('ALL', command, program):
                waived = nopasswd and not negated
    return waived


def refusal(state: Authorization) -> str:
    """Why a privileged action did not run, in the words the run should print."""
    if state is Authorization.UNAVAILABLE:
        return 'needs root and this machine has no sudo'
    if state is Authorization.DECLINED:
        return 'needs root and authorization was declined'
    return 'needs root, which this run never asked for'
