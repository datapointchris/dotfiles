"""The four system-configuration types: what each one reads, and what it writes.

Every observation is unprivileged, which is the whole reason this subsystem can be
*checked* for the first time. `install/archlinux/system-config.sh` was already
written as check-then-act — `getent group docker`, `systemctl is-enabled`, `grep
-q autologin` — it simply had no way to show anyone its plan, and its reads were
interleaved with its writes so running it at all meant a password.

Nothing here says `sudo`. A privileged write takes an authorized `Privilege` and
refuses without one, so a machine with no root still converges everything else and
says what it could not do.

**Whether a repair escalates is the row's own declaration.** `needs_root` is read
once, in `apply`, and it picks the `Escalation` the repair runs through — so the
number `plan` prints and the write it is a promise about come from one field
rather than from a field and a habit.
"""

from __future__ import annotations

import dataclasses as dc
import grp
import os
import pwd
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from dotfiles import catalog
from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import refusal
from dotfiles.providers import Result
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

SYSTEMD_RUNTIME = Path('/run/systemd/system')
"""A running systemd, which `enable` does not need and `start` does.

`enable` and `is-enabled` only manage symlinks, so they answer correctly inside a
container. Anything about a unit *running* does not, and asserting it there would
report drift on every harness that has nothing wrong with it.
"""


@dc.dataclass(frozen=True, slots=True)
class State:
    """What one row turned out to be, and what a reader should be told about it."""

    verdict: Verdict
    detail: str = ''
    repair: Repair = Repair.AUTOMATIC


def current_user() -> str:
    """Whose account this is, from the uid rather than from `$USER`.

    `$USER` is unset in every context without a login shell — `docker exec`, a
    systemd unit, cron — where `chsh -s zsh ""` then fails with `user "" does not
    exist`, which is how this was found.
    """
    return pwd.getpwuid(os.getuid()).pw_name


class Escalation(Protocol):
    """How one row's repairs reach the machine: as root, or as whoever asked.

    Two operations rather than one, because a file is the case where the two
    answers are not the same command with `sudo` dropped — see `AsThisUser.write`.
    The four repairs below take one of these and none of them asks which it got:
    that question is settled where `needs_root` is read, so the count `plan`
    publishes and the write itself cannot disagree.
    """

    def run(self, command: Sequence[str], *, reason: str) -> Completed: ...

    def write(self, path: Path, content: str, mode: str) -> Result: ...


@dc.dataclass(frozen=True, slots=True)
class AsRoot:
    """The repairs of a row declaring it needs root, through one authorization."""

    privilege: Privilege

    def run(self, command: Sequence[str], *, reason: str) -> Completed:
        return self.privilege.run(list(command), reason=reason)

    def write(self, path: Path, content: str, mode: str) -> Result:
        """Staged as this user, then installed as root.

        `install -D` rather than `mkdir` plus a redirect: it creates the parent
        directory, copies the content and sets the mode in one privileged call, so
        there is no shell for the content to be quoted through and no window where
        the file exists with the wrong mode. The bash it replaces needed `sudo
        mkdir` and `sudo tee` and a heredoc whose backslashes had to survive two
        levels of expansion.
        """
        staged = Path(tempfile.mkstemp(prefix='dotfiles-managed-')[1])
        try:
            staged.write_text(content)
            installed = self.privilege.run(['install', '-D', '-m', mode, str(staged), str(path)], reason=f'write {path}')
        finally:
            staged.unlink(missing_ok=True)

        if not installed.ok:
            return Result(False, f'could not write {path}: {installed.transcript.strip()}')
        return Result(True, f'{path} written')


@dc.dataclass(frozen=True, slots=True)
class AsThisUser:
    """The repairs of a row declaring it needs none, run as the account that asked.

    `reason` names the password a privileged run would ask for, and is taken and
    dropped: nothing here asks anybody for anything.
    """

    def run(self, command: Sequence[str], *, reason: str) -> Completed:
        return run(list(command), output=Output.QUIET)

    def write(self, path: Path, content: str, mode: str) -> Result:
        """The file itself, with no `install` in between.

        `install -D` is there to carry content across the privilege boundary, and
        a row declaring `needs_root: false` has none to cross — so a subprocess
        would be one more thing to be absent, and one more transcript to report a
        failure through.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(int(mode, 8))
        except (OSError, ValueError) as problem:
            return Result(False, f'could not write {path}: {problem}')
        return Result(True, f'{path} written')


def observe(entry: catalog.SystemConfig) -> State:
    if isinstance(entry, catalog.GroupMembership):
        return _observe_group(entry)
    if isinstance(entry, catalog.SystemdUnit):
        return _observe_unit(entry)
    if isinstance(entry, catalog.ManagedFile):
        return _observe_file(entry)
    assert isinstance(entry, catalog.LoginShell)
    return _observe_login_shell(entry)


def apply(entry: catalog.SystemConfig, privilege: Privilege) -> Result:
    """Repair one row, escalating where and only where the row declares it must.

    `needs_root` is read on both sides of a run or on neither. `plan` counts it to
    say how many writes will stop for a password, so a repair that escalated
    regardless made that promise false: a row declaring `false` was planned as
    costing nothing and then refused outright on a machine that will not give root.
    """
    escalation: Escalation = AsRoot(privilege) if entry.needs_root else AsThisUser()
    try:
        if isinstance(entry, catalog.GroupMembership):
            return _apply_group(entry, escalation)
        if isinstance(entry, catalog.SystemdUnit):
            return _apply_unit(entry, escalation)
        if isinstance(entry, catalog.ManagedFile):
            return _apply_file(entry, escalation)
        assert isinstance(entry, catalog.LoginShell)
        return _apply_login_shell(entry, escalation)
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state))


# ─────────────────────────────────────────────────────────────────────────────
# Group membership
# ─────────────────────────────────────────────────────────────────────────────


def _observe_group(entry: catalog.GroupMembership) -> State:
    """The group database, not `id -nG`.

    `id` reports the groups of the *running session*, which do not change until
    the next login — so the bash this replaces re-ran `usermod` on every install
    after the first, and a check built on it would have reported drift forever on
    a machine that was already correct.
    """
    user = current_user()
    try:
        group = grp.getgrnam(entry.name)
    except KeyError:
        if entry.create_group:
            return State(Verdict.MISSING, f'no {entry.name} group on this machine')
        return State(Verdict.MISSING, f'no {entry.name} group, and nothing here creates one', repair=Repair.NONE)

    if user in group.gr_mem or pwd.getpwnam(user).pw_gid == group.gr_gid:
        return State(Verdict.MATCHED)
    return State(Verdict.STALE, f'{user} is not in {entry.name}')


def _apply_group(entry: catalog.GroupMembership, escalation: Escalation) -> Result:
    user = current_user()
    try:
        grp.getgrnam(entry.name)
    except KeyError:
        if not entry.create_group:
            return Result(False, f'no {entry.name} group, and this entry does not create one')
        created = escalation.run(['groupadd', entry.name], reason=f'create the {entry.name} group')
        if not created.ok:
            return Result(False, f'groupadd {entry.name} failed: {created.transcript.strip()}')

    added = escalation.run(['usermod', '-aG', entry.name, user], reason=f'add {user} to the {entry.name} group')
    if not added.ok:
        return Result(False, f'usermod failed: {added.transcript.strip()}')
    return Result(True, f'{user} added to {entry.name} (effective at next login)')


# ─────────────────────────────────────────────────────────────────────────────
# systemd units
# ─────────────────────────────────────────────────────────────────────────────


def _observe_unit(entry: catalog.SystemdUnit) -> State:
    if shutil.which('systemctl') is None:
        return State(Verdict.UNKNOWN, 'no systemctl on this machine', repair=Repair.NONE)

    enabled = run(['systemctl', 'is-enabled', entry.name], output=Output.QUIET).ok
    if enabled is not entry.enabled:
        wanted = 'enabled' if entry.enabled else 'disabled'
        return State(Verdict.STALE, f'{entry.name} should be {wanted}')

    if not (entry.enabled and entry.active):
        return State(Verdict.MATCHED)
    if not SYSTEMD_RUNTIME.is_dir():
        return State(Verdict.MATCHED, f'{entry.name} is enabled; whether it is running is unmeasurable without a running systemd')
    if run(['systemctl', 'is-active', entry.name], output=Output.QUIET).ok:
        return State(Verdict.MATCHED)
    return State(Verdict.STALE, f'{entry.name} is enabled but not running')


def _apply_unit(entry: catalog.SystemdUnit, escalation: Escalation) -> Result:
    verb = 'enable' if entry.enabled else 'disable'
    changed = escalation.run(['systemctl', verb, entry.name], reason=f'{verb} {entry.name}')
    if not changed.ok:
        return Result(False, f'systemctl {verb} {entry.name} failed: {changed.transcript.strip()}')

    if not (entry.enabled and entry.active and SYSTEMD_RUNTIME.is_dir()):
        return Result(True, f'{entry.name} {verb}d')

    started = escalation.run(['systemctl', 'start', entry.name], reason=f'start {entry.name}')
    if not started.ok:
        return Result(False, f'systemctl start {entry.name} failed: {started.transcript.strip()}')
    return Result(True, f'{entry.name} enabled and started')


# ─────────────────────────────────────────────────────────────────────────────
# Managed files
# ─────────────────────────────────────────────────────────────────────────────


def target_path(entry: catalog.ManagedFile) -> Path:
    """Where this file goes on *this* machine. See `ManagedFile.alternate_path`."""
    alternate = Path(entry.alternate_path) if entry.alternate_path else None
    if alternate is not None and alternate.parent.is_dir():
        return alternate
    return Path(entry.path)


def rendered(entry: catalog.ManagedFile) -> str:
    """The content with the one placeholder filled in.

    `str.replace`, not `str.format`: a unit file is full of `%I` and `$TERM` and
    would grow braces the day one of these manages a JSON or systemd drop-in that
    has them, at which point `format` raises on content nobody meant as a
    template.
    """
    return entry.content.replace('{user}', current_user())


def _observe_file(entry: catalog.ManagedFile) -> State:
    path = target_path(entry)
    if not path.is_file():
        return State(Verdict.MISSING, f'{path} does not exist')

    try:
        present = path.read_text()
    except OSError as unreadable:
        return State(Verdict.UNKNOWN, f'{path} cannot be read: {unreadable.strerror}', repair=Repair.NONE)

    if entry.append_line:
        if entry.append_line in present.splitlines():
            return State(Verdict.MATCHED)
        return State(Verdict.STALE, f'{path} does not carry {entry.append_line}')

    if present == rendered(entry):
        return State(Verdict.MATCHED)
    return State(Verdict.STALE, f'{path} differs from what this repo declares')


def _apply_file(entry: catalog.ManagedFile, escalation: Escalation) -> Result:
    """The declared content at the declared path, however this row is written.

    Which of the two ways is the escalation's, not this function's: a root-owned
    file is staged and installed, and one this account owns is simply written.
    """
    path = target_path(entry)
    return escalation.write(path, _wanted_content(entry, path), entry.mode)


def _wanted_content(entry: catalog.ManagedFile, path: Path) -> str:
    if not entry.append_line:
        return rendered(entry)
    existing = path.read_text() if path.is_file() else ''
    if existing and not existing.endswith('\n'):
        existing += '\n'
    return f'{existing}{entry.append_line}\n'


# ─────────────────────────────────────────────────────────────────────────────
# Login shell
# ─────────────────────────────────────────────────────────────────────────────


def _observe_login_shell(entry: catalog.LoginShell) -> State:
    """Which shell the passwd entry names, and nothing about whether it exists yet.

    Deliberately not asked here. zsh is a system package at `SYSTEM` and this row
    is decided at `SYSTEM_CONFIG` of the same run, so "not installed" measured at
    plan time is a fact about the machine before the run — and answering it as a
    verdict makes the login shell unrepairable on every fresh machine. Whether
    the shell has arrived is the repair's question, asked when the answer is
    final.
    """
    current = pwd.getpwuid(os.getuid()).pw_shell
    if Path(current).name == entry.name:
        return State(Verdict.MATCHED)
    return State(Verdict.STALE, f'login shell is {current or "unset"}')


def _apply_login_shell(entry: catalog.LoginShell, escalation: Escalation) -> Result:
    shell = shutil.which(entry.name)
    if shell is None:
        return Result(False, f'{entry.name} is not installed, and the stage that supplies it has not', refused=True)

    changed = escalation.run(['chsh', '-s', shell, current_user()], reason=f'make {shell} the login shell')
    if not changed.ok:
        return Result(False, f'chsh failed: {changed.transcript.strip()}')
    return Result(True, f'login shell changed to {shell} (effective at next login)')
