"""The system-configuration types: what each one observes, and what it writes.

The reads are the point. Arch's `system-config.sh` already asked these questions —
`getent group docker`, `systemctl is-enabled`, `grep -q autologin` — and could not
answer them to anyone, because each read was followed immediately by the `sudo`
that acted on it. Here every read is a function call and every write goes through
a `Privilege` a test can decline.

`systemctl` and `install` are found on `PATH`, so those seams are real ones. The
group and passwd databases have no such seam — `grp` and `pwd` read the machine's
own — so they are the two places a test patches the standard library rather than
asserting whatever account happens to be running it.
"""

from __future__ import annotations

import grp
import os
import pwd
import stat
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles.privilege import Privilege
from dotfiles.providers import Kind
from dotfiles.providers import sysconfig
from dotfiles.resources import Repair
from dotfiles.resources import Verdict


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


@pytest.fixture
def declined(fake_bin: Path) -> Privilege:
    executable(fake_bin, 'sudo', '#!/bin/sh\nexit 1\n')
    privilege = Privilege()
    return privilege


def managed_file(**fields: object) -> catalog.ManagedFile:
    return catalog.ManagedFile.from_mapping({'name': 'probe', **fields})


# ─────────────────────────────────────────────────────────────────────────────
# Managed files
# ─────────────────────────────────────────────────────────────────────────────


def test_a_file_that_does_not_exist_is_missing(tmp_path: Path) -> None:
    entry = managed_file(path=str(tmp_path / 'zshenv'), append_line='export ZDOTDIR="$HOME/.config/zsh"')

    assert sysconfig.observe(entry).verdict is Verdict.MISSING


def test_a_file_already_carrying_the_line_matches(tmp_path: Path) -> None:
    target = tmp_path / 'zshenv'
    target.write_text('# system zshenv\nexport ZDOTDIR="$HOME/.config/zsh"\n')
    entry = managed_file(path=str(target), append_line='export ZDOTDIR="$HOME/.config/zsh"')

    assert sysconfig.observe(entry).verdict is Verdict.MATCHED


def test_a_file_missing_the_line_is_stale_rather_than_missing(tmp_path: Path) -> None:
    """The distinction the repair depends on: the file is the OS's and only the
    line is ours, so this appends rather than replacing what is there."""
    target = tmp_path / 'zshenv'
    target.write_text('# put here by the distribution\n')
    entry = managed_file(path=str(target), append_line='export ZDOTDIR="$HOME/.config/zsh"')

    assert sysconfig.observe(entry).verdict is Verdict.STALE


def test_appending_keeps_what_the_distribution_put_there(tmp_path: Path, granted: Privilege) -> None:
    target = tmp_path / 'zshenv'
    target.write_text('# put here by the distribution\n')
    entry = managed_file(path=str(target), append_line='export ZDOTDIR="$HOME/.config/zsh"')

    assert sysconfig.apply(entry, granted).ok
    assert target.read_text() == '# put here by the distribution\nexport ZDOTDIR="$HOME/.config/zsh"\n'
    assert sysconfig.observe(entry).verdict is Verdict.MATCHED


def test_appending_to_a_file_with_no_trailing_newline_does_not_join_two_lines(tmp_path: Path, granted: Privilege) -> None:
    """The failure `>>` has in shell too, and the one that would leave a system
    zshenv whose last line is two statements zsh reads as one."""
    target = tmp_path / 'zshenv'
    target.write_text('umask 022')
    entry = managed_file(path=str(target), append_line='export ZDOTDIR="$HOME/.config/zsh"')

    assert sysconfig.apply(entry, granted).ok
    assert target.read_text().splitlines() == ['umask 022', 'export ZDOTDIR="$HOME/.config/zsh"']


def test_a_wholly_owned_file_is_compared_exactly(tmp_path: Path) -> None:
    target = tmp_path / 'autologin.conf'
    entry = managed_file(path=str(target), content='[Service]\nExecStart=\n')

    target.write_text('[Service]\nExecStart=\n')
    assert sysconfig.observe(entry).verdict is Verdict.MATCHED

    target.write_text('[Service]\nExecStart=/sbin/agetty\n')
    assert sysconfig.observe(entry).verdict is Verdict.STALE


def test_writing_a_wholly_owned_file_creates_its_parent_directory(tmp_path: Path, granted: Privilege) -> None:
    """`/etc/systemd/system/getty@tty1.service.d/` does not exist on a fresh box,
    and the bash needed a separate privileged `mkdir -p` to make it."""
    target = tmp_path / 'getty@tty1.service.d' / 'autologin.conf'
    entry = managed_file(path=str(target), content='[Service]\nExecStart=\n')

    assert sysconfig.apply(entry, granted).ok
    assert target.read_text() == '[Service]\nExecStart=\n'


def test_the_user_placeholder_is_filled_in(tmp_path: Path, granted: Privilege) -> None:
    target = tmp_path / 'autologin.conf'
    entry = managed_file(path=str(target), content='--autologin {user} %I $TERM\n')

    assert sysconfig.apply(entry, granted).ok
    assert target.read_text() == f'--autologin {sysconfig.current_user()} %I $TERM\n'


def test_content_that_is_not_a_template_survives_being_rendered() -> None:
    """`%I`, `$TERM` and a brace that means a brace. `str.format` would raise on
    the third and silently eat the first two's neighbors."""
    entry = managed_file(path='/nowhere', content="ExecStart=-/sbin/agetty -o '-p -f -- \\u' %I $TERM {} {0}\n")

    assert sysconfig.rendered(entry) == "ExecStart=-/sbin/agetty -o '-p -f -- \\u' %I $TERM {} {0}\n"


def test_the_alternate_path_wins_where_its_directory_exists(tmp_path: Path) -> None:
    """Debian builds zsh with `--enable-etcdir=/etc/zsh`, so writing to
    `/etc/zshenv` there is a file zsh never reads."""
    (tmp_path / 'zsh').mkdir()
    entry = managed_file(path=str(tmp_path / 'zshenv'), alternate_path=str(tmp_path / 'zsh' / 'zshenv'), append_line='x')

    assert sysconfig.target_path(entry) == tmp_path / 'zsh' / 'zshenv'


def test_the_declared_path_is_used_where_the_alternate_directory_does_not_exist(tmp_path: Path) -> None:
    entry = managed_file(path=str(tmp_path / 'zshenv'), alternate_path=str(tmp_path / 'zsh' / 'zshenv'), append_line='x')

    assert sysconfig.target_path(entry) == tmp_path / 'zshenv'


def test_a_file_that_is_both_wholly_and_partly_ours_is_refused_at_load_time() -> None:
    entry = managed_file(path='/etc/zshenv', content='x\n', append_line='y')

    assert any('wholly ours or one line of ours' in problem for problem in entry.problems())


def test_a_declined_password_writes_nothing_and_says_so(tmp_path: Path, declined: Privilege) -> None:
    """The unprivileged rest of a run still has to land, so this is a reported
    refusal rather than an exception escaping into the phase."""
    target = tmp_path / 'zshenv'
    entry = managed_file(path=str(target), append_line='export ZDOTDIR="$HOME/.config/zsh"')

    result = sysconfig.apply(entry, declined)

    assert not result.ok
    assert result.kind is Kind.PRIVILEGE_UNAVAILABLE
    assert not target.exists()


# ─────────────────────────────────────────────────────────────────────────────
# systemd units
# ─────────────────────────────────────────────────────────────────────────────


def unit(**fields: object) -> catalog.SystemdUnit:
    return catalog.SystemdUnit.from_mapping({'name': 'docker.socket', **fields})


def test_a_machine_with_no_systemctl_is_unknown_rather_than_drifted(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS, and any container without systemd. Reporting a unit missing there
    would be drift `apply` could never repair."""
    monkeypatch.setenv('PATH', str(fake_bin))
    state = sysconfig.observe(unit(enabled=True))

    assert state.verdict is Verdict.UNKNOWN
    assert state.repair is Repair.NONE


def test_an_enabled_unit_that_should_be_enabled_matches(fake_bin: Path) -> None:
    executable(fake_bin, 'systemctl', '#!/bin/sh\nexit 0\n')

    assert sysconfig.observe(unit(enabled=True)).verdict is Verdict.MATCHED


def test_a_disabled_unit_that_should_be_enabled_is_stale(fake_bin: Path) -> None:
    executable(fake_bin, 'systemctl', '#!/bin/sh\nexit 1\n')

    assert sysconfig.observe(unit(enabled=True)).verdict is Verdict.STALE


def test_a_unit_that_should_be_disabled_matches_when_it_is_not_installed(fake_bin: Path) -> None:
    """`systemctl is-enabled gdm` on a machine with no gdm exits non-zero, and
    "not enabled" is exactly the state that entry asks for."""
    executable(fake_bin, 'systemctl', '#!/bin/sh\nexit 1\n')

    assert sysconfig.observe(catalog.SystemdUnit.from_mapping({'name': 'gdm', 'enabled': False})).verdict is Verdict.MATCHED


def test_a_unit_that_should_be_running_and_is_not_is_stale(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sysconfig, 'SYSTEMD_RUNTIME', Path(__file__).parent)
    executable(fake_bin, 'systemctl', '#!/bin/sh\n[ "$1" = "is-active" ] && exit 3\nexit 0\n')

    assert sysconfig.observe(unit(enabled=True, active=True)).verdict is Verdict.STALE


def test_whether_a_unit_is_running_is_not_asserted_without_a_running_systemd(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`enable` manages symlinks and answers correctly in a container; anything
    about a unit *running* does not, and asserting it would report drift on every
    harness with nothing wrong with it."""
    monkeypatch.setattr(sysconfig, 'SYSTEMD_RUNTIME', Path('/nonexistent'))
    executable(fake_bin, 'systemctl', '#!/bin/sh\n[ "$1" = "is-active" ] && exit 3\nexit 0\n')

    state = sysconfig.observe(unit(enabled=True, active=True))

    assert state.verdict is Verdict.MATCHED
    assert 'running systemd' in state.detail


def test_enabling_a_unit_passes_the_verb_the_entry_asks_for(fake_bin: Path, tmp_path: Path, granted: Privilege) -> None:
    log = tmp_path / 'systemctl-calls'
    executable(fake_bin, 'systemctl', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\nexit 0\n')

    assert sysconfig.apply(catalog.SystemdUnit.from_mapping({'name': 'gdm', 'enabled': False}), granted).ok
    assert log.read_text().splitlines() == ['disable gdm']


# ─────────────────────────────────────────────────────────────────────────────
# systemd units — user scope
# ─────────────────────────────────────────────────────────────────────────────


def user_unit(**fields: object) -> catalog.SystemdUnit:
    return catalog.SystemdUnit.from_mapping({'name': 'ntfy-client.service', 'scope': 'user', 'needs_root': False, **fields})


def test_a_user_unit_is_asked_of_the_user_manager(fake_bin: Path, tmp_path: Path) -> None:
    """The two managers are blind to each other, so the wrong one answers about a
    unit it has never heard of."""
    log = tmp_path / 'systemctl-calls'
    executable(fake_bin, 'systemctl', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\necho enabled\nexit 0\n')

    sysconfig.observe(user_unit(enabled=True))

    assert log.read_text().splitlines()[0].startswith('--user is-enabled')


def test_a_system_unit_is_not_asked_of_the_user_manager(fake_bin: Path, tmp_path: Path) -> None:
    log = tmp_path / 'systemctl-calls'
    executable(fake_bin, 'systemctl', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\necho enabled\nexit 0\n')

    sysconfig.observe(unit(enabled=True))

    assert log.read_text().splitlines()[0].startswith('is-enabled'), 'a manager was asked at all'
    assert '--user' not in log.read_text()


def test_an_unreachable_user_bus_is_unknown_rather_than_drift(fake_bin: Path) -> None:
    """`systemctl --user` goes over the session bus, and with no bus it exits 1
    with the error on stderr — the same exit code a disabled unit gives. A shell
    without a bus is the live case: non-interactive SSH, which the fleet has to
    every workstation. Reporting drift there would be a repair `apply` runs
    against a manager it cannot reach.

    Measured 2026-08-16: a manager that answered always writes a word to stdout.
    A bus failure leaves it empty, and that is the only thing separating them.
    """
    executable(fake_bin, 'systemctl', '#!/bin/sh\necho "Failed to connect to user scope bus" >&2\nexit 1\n')

    state = sysconfig.observe(user_unit(enabled=True))

    assert state.verdict is Verdict.UNKNOWN
    assert state.repair is Repair.NONE


def test_a_user_unit_the_manager_calls_disabled_is_still_drift(fake_bin: Path) -> None:
    """The guard above must not swallow a real answer. `disabled` exits 1 too."""
    executable(fake_bin, 'systemctl', '#!/bin/sh\necho disabled\nexit 1\n')

    assert sysconfig.observe(user_unit(enabled=True)).verdict is Verdict.STALE


def test_a_unit_file_newer_than_the_manager_has_loaded_is_stale(fake_bin: Path) -> None:
    """This repo deploys the unit file at Stage.SYMLINKS and enables it at
    Stage.SYSTEM_CONFIG. Nothing in between tells the manager to re-read it, so
    without this the file changes, the row reports MATCHED, and the machine goes
    on running the definition it read at boot."""
    executable(
        fake_bin, 'systemctl', '#!/bin/sh\n[ "$1" = "--user" ] && shift\ncase "$1" in show) echo yes ;; *) echo enabled ;; esac\nexit 0\n'
    )

    state = sysconfig.observe(user_unit(enabled=True))

    assert state.verdict is Verdict.STALE
    assert 'newer than the manager has loaded' in state.detail


def test_a_reload_is_issued_before_the_unit_is_enabled(fake_bin: Path, tmp_path: Path, granted: Privilege) -> None:
    """Order matters: enabling against a definition the manager has not read is
    what leaves a service running the old one."""
    log = tmp_path / 'systemctl-calls'
    script = (
        '#!/bin/sh\n'
        f'printf "%s\\n" "$*" >> {log}\n'
        '[ "$1" = "--user" ] && shift\n'
        'case "$1" in show) echo yes ;; *) echo enabled ;; esac\n'
        'exit 0\n'
    )
    executable(fake_bin, 'systemctl', script)

    assert sysconfig.apply(user_unit(enabled=True), granted).ok

    issued = [line for line in log.read_text().splitlines() if 'show' not in line]
    assert issued[0] == '--user daemon-reload'
    assert issued[1] == '--user enable ntfy-client.service'


def systemctl_that(fake_bin: Path, log: Path, *, reload_fails: bool, needs_reload: str = '', restart_fails: bool = False) -> None:
    """A `systemctl` recording its argv, with the three answers these rows turn on.

    `show` is what `_needs_reload` reads and decides whether a failed reload is
    fatal, so it is a parameter rather than a fixed `yes`.
    """
    refuses = 'echo "Failed to connect to user scope bus" >&2; exit 1' if reload_fails else 'exit 0'
    restarts = 'echo "Job for ntfy-client.service failed" >&2; exit 1' if restart_fails else 'exit 0'
    script = (
        '#!/bin/sh\n'
        f'printf "%s\\n" "$*" >> {log}\n'
        '[ "$1" = "--user" ] && shift\n'
        'case "$1" in\n'
        f'  show) echo "{needs_reload}"; exit 0 ;;\n'
        f'  daemon-reload) {refuses} ;;\n'
        f'  restart) {restarts} ;;\n'
        '  *) echo enabled; exit 0 ;;\n'
        'esac\n'
    )
    executable(fake_bin, 'systemctl', script)


def issued(log: Path) -> list[str]:
    """The calls that were writes, with `_needs_reload`'s read dropped."""
    return [line for line in log.read_text().splitlines() if 'show' not in line]


def test_a_failed_reload_still_enables_the_unit_where_no_manager_holds_an_older_copy(
    fake_bin: Path, tmp_path: Path, granted: Privilege
) -> None:
    """`enable` writes a symlink and `daemon-reload` needs a session bus, so an
    account can have the second unavailable and the first working.

    Refusing the whole repair left such a machine with neither, and `PARTIALLY_APPLIED`
    is what says which of the two success branches ran without matching the sentence.
    """
    log = tmp_path / 'systemctl-calls'
    systemctl_that(fake_bin, log, reload_fails=True)

    result = sysconfig.apply(user_unit(enabled=True), granted)

    assert result.ok, result.detail
    assert result.kind is Kind.PARTIALLY_APPLIED
    assert issued(log) == ['--user daemon-reload', '--user enable ntfy-client.service']


def test_the_caveat_carries_what_the_reload_said(fake_bin: Path, tmp_path: Path, granted: Privilege) -> None:
    """A unit file systemd will not parse and a polkit refusal both fail this call,
    and without the transcript they read identically to the missing bus this
    tolerates. Failing fast rather than defaulting asks for the path and
    the error, and the branch kept only the path."""
    log = tmp_path / 'systemctl-calls'
    systemctl_that(fake_bin, log, reload_fails=True)

    result = sysconfig.apply(user_unit(enabled=True), granted)

    assert 'Failed to connect to user scope bus' in result.detail


def test_a_reload_that_worked_reports_a_whole_repair(fake_bin: Path, tmp_path: Path, granted: Privilege) -> None:
    """The caveat is a claim about a partial repair, so a whole one does not carry
    it — asserted as the kind, which is the value the sentence is built from."""
    log = tmp_path / 'systemctl-calls'
    systemctl_that(fake_bin, log, reload_fails=False)

    result = sysconfig.apply(user_unit(enabled=True), granted)

    assert result.ok, result.detail
    assert result.kind is Kind.APPLIED


def test_a_failed_reload_is_still_fatal_where_the_manager_holds_an_older_copy(fake_bin: Path, tmp_path: Path, granted: Privilege) -> None:
    """The case the fatal branch was written for, and still the right answer.

    A manager answering `NeedDaemonReload` is reachable and holding an older copy of
    this file, so enabling against it leaves the service on the old one. It is also
    what `_observe_unit` turns into STALE — so tolerating it would report `ok=True`
    about a row the next `check` calls drift, every run, on a bus that is not coming
    back.
    """
    log = tmp_path / 'systemctl-calls'
    systemctl_that(fake_bin, log, reload_fails=True, needs_reload='yes')

    result = sysconfig.apply(user_unit(enabled=True), granted)

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert issued(log) == ['--user daemon-reload']


def test_a_unit_wanted_running_is_not_started_after_a_reload_the_manager_refused(
    fake_bin: Path, tmp_path: Path, granted: Privilege, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`systemctl --user restart` goes to the same bus the reload could not reach.

    `SYSTEMD_RUNTIME` is `/run/systemd/system`, which answers for the *system*
    manager — so a host whose system manager runs and whose user bus does not opens
    that gate and then fails on the bus. `install/system.yml` declares this repo's
    only user unit `active: true`, so it is the shape that ships and the one no row
    here reached before.
    """
    monkeypatch.setattr(sysconfig, 'SYSTEMD_RUNTIME', Path(__file__).parent)
    log = tmp_path / 'systemctl-calls'
    systemctl_that(fake_bin, log, reload_fails=True)

    result = sysconfig.apply(user_unit(enabled=True, active=True), granted)

    assert result.ok, result.detail
    assert result.kind is Kind.PARTIALLY_APPLIED
    assert issued(log) == ['--user daemon-reload', '--user enable ntfy-client.service']


def test_a_unit_wanted_running_is_started_when_the_reload_worked(
    fake_bin: Path, tmp_path: Path, granted: Privilege, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side of the gate above, so neither answer is the only one measured."""
    monkeypatch.setattr(sysconfig, 'SYSTEMD_RUNTIME', Path(__file__).parent)
    log = tmp_path / 'systemctl-calls'
    systemctl_that(fake_bin, log, reload_fails=False)

    result = sysconfig.apply(user_unit(enabled=True, active=True), granted)

    assert result.kind is Kind.APPLIED
    assert issued(log) == ['--user daemon-reload', '--user enable ntfy-client.service', '--user restart ntfy-client.service']


def test_a_start_the_manager_refused_fails_the_row_rather_than_caveating_it(
    fake_bin: Path, tmp_path: Path, granted: Privilege, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A unit declared `active: true` that will not start is not a partial repair.

    The reload succeeded, so the manager is reachable and it said no to this unit —
    a bad unit file or a failing daemon, which is a person's to read. The caveat
    above is for a manager that never answered.
    """
    monkeypatch.setattr(sysconfig, 'SYSTEMD_RUNTIME', Path(__file__).parent)
    log = tmp_path / 'systemctl-calls'
    systemctl_that(fake_bin, log, reload_fails=False, restart_fails=True)

    result = sysconfig.apply(user_unit(enabled=True, active=True), granted)

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert 'Job for ntfy-client.service failed' in result.detail


def test_a_user_unit_declaring_needs_root_is_refused(fake_bin: Path) -> None:
    """`sudo systemctl --user` reaches root's manager, not this account's — a
    wrong answer with no error, which is why it fails at load instead."""
    entry = catalog.SystemdUnit.from_mapping({'name': 'ntfy-client.service', 'scope': 'user', 'needs_root': True})

    assert any('needs_root' in problem for problem in entry.problems())


def test_a_scope_that_is_not_a_manager_is_refused() -> None:
    entry = catalog.SystemdUnit.from_mapping({'name': 'ntfy-client.service', 'scope': 'sytem'})

    assert any('is owned by the system or user manager' in problem for problem in entry.problems())


# ─────────────────────────────────────────────────────────────────────────────
# Group membership
# ─────────────────────────────────────────────────────────────────────────────


def group_entry(**fields: object) -> catalog.GroupMembership:
    return catalog.GroupMembership.from_mapping({'name': 'docker', **fields})


def declare_group(monkeypatch: pytest.MonkeyPatch, members: list[str]) -> None:
    monkeypatch.setattr(grp, 'getgrnam', lambda _name: grp.struct_group(('docker', 'x', 999, members)))


def test_a_member_of_the_group_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read from the group database, not from `id -nG`.

    `id` reports the *session's* groups, which do not change until the next
    login — so a check built on `id` reports drift forever on a correct box, and
    an apply re-runs `usermod` on every install after the first.
    """
    declare_group(monkeypatch, [sysconfig.current_user()])

    assert sysconfig.observe(group_entry(create_group=True)).verdict is Verdict.MATCHED


def test_a_non_member_is_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    declare_group(monkeypatch, ['someone-else'])

    assert sysconfig.observe(group_entry(create_group=True)).verdict is Verdict.STALE


def test_a_group_that_does_not_exist_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(grp, 'getgrnam', _raises_keyerror)

    assert sysconfig.observe(group_entry(create_group=True)).verdict is Verdict.MISSING


def test_a_group_nothing_here_creates_is_nobody_s_to_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(grp, 'getgrnam', _raises_keyerror)
    state = sysconfig.observe(group_entry())

    assert state.verdict is Verdict.MISSING
    assert state.repair is Repair.NONE


def test_a_missing_group_is_created_before_the_user_is_added(
    monkeypatch: pytest.MonkeyPatch,
    fake_bin: Path,
    tmp_path: Path,
    granted: Privilege,
) -> None:
    log = tmp_path / 'calls'
    for tool in ('groupadd', 'usermod'):
        executable(fake_bin, tool, f'#!/bin/sh\nprintf "{tool} %s\\n" "$*" >> {log}\nexit 0\n')
    monkeypatch.setattr(grp, 'getgrnam', _raises_keyerror)

    assert sysconfig.apply(group_entry(create_group=True), granted).ok
    assert log.read_text().splitlines() == ['groupadd docker', f'usermod -aG docker {sysconfig.current_user()}']


def _raises_keyerror(_name: str) -> grp.struct_group:
    raise KeyError(_name)


# ─────────────────────────────────────────────────────────────────────────────
# Login shell
# ─────────────────────────────────────────────────────────────────────────────


def declare_shell(monkeypatch: pytest.MonkeyPatch, shell: str) -> None:
    """Rebuilt rather than copied: `pwd.struct_passwd` is a structseq, so it has
    no `_replace`, and the name is kept real because `current_user` reads it too."""
    real = pwd.getpwuid(os.getuid())
    fake = pwd.struct_passwd((real.pw_name, 'x', real.pw_uid, real.pw_gid, '', real.pw_dir, shell))
    monkeypatch.setattr(pwd, 'getpwuid', lambda _uid: fake)


def test_the_declared_login_shell_matches_when_it_is_already_set(monkeypatch: pytest.MonkeyPatch) -> None:
    declare_shell(monkeypatch, '/usr/bin/zsh')

    assert sysconfig.observe(catalog.LoginShell.from_mapping({'name': 'zsh'})).verdict is Verdict.MATCHED


def test_a_different_login_shell_is_stale(monkeypatch: pytest.MonkeyPatch, fake_bin: Path) -> None:
    executable(fake_bin, 'zsh', '#!/bin/sh\nexit 0\n')
    declare_shell(monkeypatch, '/bin/bash')

    assert sysconfig.observe(catalog.LoginShell.from_mapping({'name': 'zsh'})).verdict is Verdict.STALE


def test_a_shell_the_run_has_not_installed_yet_is_still_repairable(monkeypatch: pytest.MonkeyPatch, fake_bin: Path) -> None:
    """Ordering, and it must not be stated as a verdict.

    zsh is a system package at `SYSTEM` and this row is decided at
    `SYSTEM_CONFIG` of the same run, so "not installed" measured up front is a
    fact about the machine *before* the run. Answering `Repair.NONE` there made
    every fresh install finish with bash as the login shell and call itself
    converged. The repair is what asks, at the point the answer is final.
    """
    monkeypatch.setenv('PATH', str(fake_bin))
    declare_shell(monkeypatch, '/bin/bash')
    state = sysconfig.observe(catalog.LoginShell.from_mapping({'name': 'zsh'}))

    assert state.verdict is Verdict.STALE
    assert state.repair is Repair.AUTOMATIC


def test_a_shell_still_missing_at_the_write_is_refused_rather_than_failed(monkeypatch: pytest.MonkeyPatch, fake_bin: Path) -> None:
    """`apply` exits non-zero on failures, and a package an earlier stage could
    not deliver is not this run failing to change a login shell."""
    monkeypatch.setenv('PATH', str(fake_bin))
    declare_shell(monkeypatch, '/bin/bash')

    result = sysconfig.apply(catalog.LoginShell.from_mapping({'name': 'zsh'}), Privilege(offer=False))

    assert not result.ok
    assert result.refused
    assert result.kind is Kind.PREREQUISITE_MISSING


def test_changing_the_login_shell_passes_the_resolved_path(
    monkeypatch: pytest.MonkeyPatch,
    fake_bin: Path,
    tmp_path: Path,
    granted: Privilege,
) -> None:
    """`chsh -s zsh` is not the same command as `chsh -s /usr/bin/zsh`, and the
    user argument is explicit because `$USER` is unset under `docker exec`, a
    systemd unit and cron — where `chsh -s zsh ""` fails with `user "" does not
    exist`."""
    log = tmp_path / 'calls'
    executable(fake_bin, 'zsh', '#!/bin/sh\nexit 0\n')
    executable(fake_bin, 'chsh', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\nexit 0\n')
    declare_shell(monkeypatch, '/bin/bash')

    assert sysconfig.apply(catalog.LoginShell.from_mapping({'name': 'zsh'}), granted).ok
    assert log.read_text().splitlines() == [f'-s {fake_bin}/zsh {sysconfig.current_user()}']
