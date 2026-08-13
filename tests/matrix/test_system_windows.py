"""`system` and `windows`: the two halves of the machine that answer to somebody else.

`system` is the only resource whose repairs need root, and every one of them is
measured here through the front door with root *declined*. That is not a
concession to the harness — it is the property the resource was built on. Every
observation is unprivileged, so a machine with no password still reports what is
wrong with it, and every write is refused and named rather than attempted. A test
that granted root would install packages, add the account to groups and rewrite a
login shell on whatever box ran the suite.

**`sudo` is shadowed with a binary that answers no**, in a fixture that no test
opts into. Without it `Privilege.acquire` finds the real `/usr/bin/sudo` behind
the sandbox bin, `sudo -n true` fails on any box without NOPASSWD, and `_ask`
runs `sudo -v` against the terminal — a password prompt inside a test run, which
hangs rather than fails.

**The privileged tools are shadowed too, with recorders that write a file**, so
"reported rather than performed" is an assertion about the machine and not about
a message. `groupadd`, `usermod`, `systemctl enable`, `install`, `chsh`,
`apt-get`: if any of them runs, the witness file exists.

**Two seams are the standard library rather than this package.** The group and
passwd databases are read through `grp` and `pwd`, which answer for the account
running the suite and have no injectable knob — the same two `tests/resources/
test_sysconfig.py` patches, for the same reason. Everything else is a real seam:
`system.yml` on disk, a fake bin dir on `PATH`, files under the sandbox.

`windows` reaches the Windows side through `/proc/version` and `/mnt/c`, and
those are the one place this module patches `dotfiles` itself. See
`under_a_windows_side` for what has no seam and why.
"""

from __future__ import annotations

import dataclasses as dc
import grp
import os
import pwd
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import windows
from dotfiles.vocabulary import ExitCode
from matrix.harness import ANSWERS
from matrix.harness import REFUSED
from matrix.harness import Invocation
from matrix.harness import ReachedTheNetwork
from matrix.harness import Sandbox

Arrange = Callable[[Sandbox, pytest.MonkeyPatch], None]
"""How one case makes its machine. Given the sandbox and the same monkeypatch it
was built with, so a case can shadow a binary and patch `grp` in one place."""


# ─────────────────────────────────────────────────────────────────────────────
# The declaration, and the account the rows are about
# ─────────────────────────────────────────────────────────────────────────────

LINUX = {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'}
"""A machine that subscribes to the package section, on apt with no display stack.

`system_packages: workstation` is what makes a declared package reach the plan at
all; without it the section is unsubscribed and every row below would measure an
empty plan.
"""

CURL = {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}

ACCOUNT = 'boxuser'
PRIMARY_GID = 4242
"""The synthetic account's own group, and deliberately not a plausible one.

`_observe_group` matches on `pw_gid == gr_gid` as well as on membership, so a
group built for a STALE case would read MATCHED if its gid collided with the
account's primary one. Every group below uses `OTHER_GID`.
"""

OTHER_GID = 999


def declare_system(sandbox: Sandbox, rows: dict[str, Any]) -> Path:
    """Write `install/system.yml`, which the harness's declaration leaves absent.

    Absent is the right default — `catalog.load` reads it as an empty declaration
    — so this exists rather than a knob on `declare`, and a test that writes none
    is measuring a machine with no configuration rows.
    """
    path = sandbox.repo / 'install' / 'system.yml'
    path.write_text(yaml.safe_dump(rows, sort_keys=False))
    return path


def synthetic_account(monkeypatch: pytest.MonkeyPatch, shell: str = '/bin/bash') -> None:
    """One passwd entry, answering both lookups, so no row is about whoever ran the suite.

    `pwd` has no seam: `current_user` reads `getpwuid(os.getuid())` and
    `_observe_group` reads `getpwnam(user)`, and both go to the machine's own
    database. Patched together rather than separately, because a group's verdict
    depends on the same entry the login shell's does.
    """
    entry = pwd.struct_passwd((ACCOUNT, 'x', os.getuid(), PRIMARY_GID, '', str(Path.home()), shell))
    monkeypatch.setattr(pwd, 'getpwuid', lambda _uid: entry)
    monkeypatch.setattr(pwd, 'getpwnam', lambda _name: entry)


def group_holding(monkeypatch: pytest.MonkeyPatch, *members: str) -> None:
    """A group that exists on this machine, with the membership a case wants."""
    monkeypatch.setattr(grp, 'getgrnam', lambda name: grp.struct_group((name, 'x', OTHER_GID, list(members))))


def no_such_group(monkeypatch: pytest.MonkeyPatch) -> None:
    def absent(name: str) -> grp.struct_group:
        raise KeyError(name)

    monkeypatch.setattr(grp, 'getgrnam', absent)


ANSWERS_NO = REFUSED
NOTHING_INSTALLED = '#!/bin/sh\nprintf ""\n'


@pytest.fixture(autouse=True)
def root_is_declined(sandbox: Sandbox) -> None:
    """Every run in this module meets a machine that will not give it root.

    Autouse and unconditional. `reconcile._perform` builds its own `Privilege`
    with `offer=True`, so a run that reached a privileged write with the real
    `sudo` on `PATH` would prompt for a password on the terminal — and the sandbox
    keeps `/usr/bin` behind its own bin precisely so `git` and `sh` still resolve.
    A `sudo` that exits non-zero settles the question as DECLINED before anything
    is asked of a person.
    """
    sandbox.shadow('sudo', ANSWERS_NO)


WITNESS = 'privileged-commands'


def records(sandbox: Sandbox, *tools: str) -> Path:
    """Shadow each privileged tool with one that leaves a trace, and return the trace.

    The file is the assertion. A message saying root was declined proves what the
    run *said*; an absent witness proves `groupadd` was never handed the account.
    """
    log = sandbox.root / WITNESS
    for tool in tools:
        sandbox.shadow(tool, f'#!/bin/sh\nprintf "%s %s\\n" "$(basename "$0")" "$*" >> {log}\nexit 0\n')
    return log


# ─────────────────────────────────────────────────────────────────────────────
# One configuration row, and where its verdict puts it
# ─────────────────────────────────────────────────────────────────────────────


def managed_line(sandbox: Sandbox) -> dict[str, Any]:
    """The zdotdir row's shape: a file the OS owns, of which one line is ours."""
    return {'managed_files': [{'name': 'zdotdir', 'path': str(sandbox.root / 'etc' / 'zshenv'), 'append_line': 'export ZDOTDIR="$HOME"'}]}


def managed_whole(sandbox: Sandbox) -> dict[str, Any]:
    """The autologin row's shape: a file that is wholly this repo's."""
    return {'managed_files': [{'name': 'autologin', 'path': str(sandbox.root / 'etc' / 'autologin.conf'), 'content': '[Service]\n'}]}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def absent_file(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, managed_line(sandbox))


def file_with_the_line(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, managed_line(sandbox))
    write(sandbox.root / 'etc' / 'zshenv', '# distribution\nexport ZDOTDIR="$HOME"\n')


def file_without_the_line(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, managed_line(sandbox))
    write(sandbox.root / 'etc' / 'zshenv', '# distribution\n')


def file_matching_exactly(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, managed_whole(sandbox))
    write(sandbox.root / 'etc' / 'autologin.conf', '[Service]\n')


def file_differing(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, managed_whole(sandbox))
    write(sandbox.root / 'etc' / 'autologin.conf', '[Service]\nExecStart=/sbin/agetty\n')


DOCKER_GROUP = {'group_memberships': [{'name': 'docker', 'create_group': True}]}
UNCREATED_GROUP = {'group_memberships': [{'name': 'docker'}]}


def already_in_the_group(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, DOCKER_GROUP)
    synthetic_account(monkeypatch)
    group_holding(monkeypatch, ACCOUNT)


def not_in_the_group(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, DOCKER_GROUP)
    synthetic_account(monkeypatch)
    group_holding(monkeypatch, 'someone-else')


def group_this_entry_creates(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, DOCKER_GROUP)
    synthetic_account(monkeypatch)
    no_such_group(monkeypatch)


def group_nothing_here_creates(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, UNCREATED_GROUP)
    synthetic_account(monkeypatch)
    no_such_group(monkeypatch)


ENABLED_UNIT = {'systemd_units': [{'name': 'docker.socket', 'enabled': True}]}
DISABLED_UNIT = {'systemd_units': [{'name': 'gdm', 'enabled': False}]}


def unit_already_enabled(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, ENABLED_UNIT)
    sandbox.shadow('systemctl', ANSWERS)


def unit_not_enabled(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, ENABLED_UNIT)
    sandbox.shadow('systemctl', ANSWERS_NO)


def unit_wanted_off_and_not_installed(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """`systemctl is-enabled gdm` exits non-zero on a machine with no gdm, and
    "not enabled" is exactly what the row asks for."""
    declare_system(sandbox, DISABLED_UNIT)
    sandbox.shadow('systemctl', ANSWERS_NO)


def no_systemctl_at_all(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS, and any container without systemd.

    `PATH` is trimmed to the sandbox bin rather than a `systemctl` being shadowed,
    because the question is `shutil.which` finding nothing — and the harness keeps
    `/usr/bin` behind the sandbox, where every Linux box running the suite has one.
    Safe for a read-only verb: nothing under `plan` or `check` runs `git`.
    """
    declare_system(sandbox, ENABLED_UNIT)
    monkeypatch.setenv('PATH', str(sandbox.bin))


ZSH_LOGIN = {'login_shell': [{'name': 'zsh'}]}


def login_shell_already_zsh(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, ZSH_LOGIN)
    synthetic_account(monkeypatch, shell='/usr/bin/zsh')


def login_shell_still_bash(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_system(sandbox, ZSH_LOGIN)
    synthetic_account(monkeypatch, shell='/bin/bash')


ROWS: list[tuple[str, Arrange, int, int, int]] = [
    ('an-absent-managed-file', absent_file, 1, 0, 0),
    ('a-managed-file-already-carrying-the-line', file_with_the_line, 0, 0, 0),
    ('a-managed-file-missing-the-line', file_without_the_line, 1, 0, 0),
    ('a-wholly-owned-file-that-matches', file_matching_exactly, 0, 0, 0),
    ('a-wholly-owned-file-that-differs', file_differing, 1, 0, 0),
    ('a-group-the-account-is-already-in', already_in_the_group, 0, 0, 0),
    ('a-group-the-account-is-not-in', not_in_the_group, 1, 0, 0),
    ('a-group-this-entry-creates', group_this_entry_creates, 1, 0, 0),
    ('a-group-nothing-here-creates', group_nothing_here_creates, 0, 1, 0),
    ('a-unit-already-enabled', unit_already_enabled, 0, 0, 0),
    ('a-unit-that-should-be-enabled', unit_not_enabled, 1, 0, 0),
    ('a-unit-wanted-off-and-not-installed', unit_wanted_off_and_not_installed, 0, 0, 0),
    ('a-machine-with-no-systemctl', no_systemctl_at_all, 0, 0, 1),
    ('a-login-shell-already-set', login_shell_already_zsh, 0, 0, 0),
    ('a-login-shell-still-bash', login_shell_still_bash, 1, 0, 0),
]
"""Each `system.yml` kind in each state it can be in, with what the two read verbs
owe it: how many items `apply` would change, how many need a person, and how many
nothing could measure."""


@pytest.mark.parametrize(('arrange', 'pending', 'attention', 'unmeasured'), [row[1:] for row in ROWS], ids=[row[0] for row in ROWS])
def test_a_configuration_row_is_drift_for_plan_and_a_finding_only_for_check(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    monkeypatch: pytest.MonkeyPatch,
    arrange: Arrange,
    pending: int,
    attention: int,
    unmeasured: int,
) -> None:
    """One measurement, two questions, and the exit codes that separate them.

    A row `apply` can repair is drift: `plan` exits 1 and `check` says nothing.
    A row `apply` cannot repair — a group nothing here creates — is the inverse,
    and `check` is the only verb that reports it. A row nothing could measure is
    in neither, because "no evidence" is not a claim that anything differs.
    """
    arrange(sandbox, monkeypatch)

    planned = cli('system', 'plan', '--json')
    checked = cli('system', 'check', '--json')

    assert (planned.document['pending'], planned.document['attention'], planned.document['unmeasured']) == (pending, attention, unmeasured)
    assert planned.exit_code == (ExitCode.DRIFT if pending else ExitCode.CONVERGED)
    assert checked.exit_code == (ExitCode.ISSUE if attention else ExitCode.CONVERGED)
    assert checked.exit_code != ExitCode.DRIFT, 'check answers 0 or 3 and never 1'


@pytest.mark.parametrize(('arrange', 'pending'), [(row[1], row[2]) for row in ROWS], ids=[row[0] for row in ROWS])
def test_every_configuration_repair_declares_that_it_needs_root(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    monkeypatch: pytest.MonkeyPatch,
    arrange: Arrange,
    pending: int,
) -> None:
    """Counted before anything runs, which is the half of the front-loaded design
    that survived acquiring root at the write. A plan that is complete can say how
    many of its findings will stop for a password; nothing here prompts to find out.
    """
    arrange(sandbox, monkeypatch)

    planned = cli('system', 'plan', '--json')

    assert planned.document['privileged'] == pending


# ─────────────────────────────────────────────────────────────────────────────
# Which rows this machine's coordinates admit at all
# ─────────────────────────────────────────────────────────────────────────────

NARROWED: list[tuple[str, dict[str, Any], dict[str, Any], bool]] = [
    ('an-unnarrowed-row', {}, {}, True),
    ('a-row-for-another-os-family', {'os_family': 'darwin'}, {}, False),
    ('a-row-for-this-os-family', {'os_family': 'linux'}, {}, True),
    ('a-row-for-another-host', {'host': 'wsl'}, {}, False),
    ('a-row-for-another-display-stack', {'display_stack': 'wayland'}, {}, False),
    ('a-row-needing-a-package-this-machine-plans', {'requires_package': 'curl'}, {}, True),
    ('a-row-needing-a-package-nothing-declares', {'requires_package': 'docker'}, {}, False),
    ('a-row-behind-a-feature-the-manifest-sets', {'feature': 'configure_zsh'}, {'configure_zsh': True}, True),
    ('a-row-behind-a-feature-the-manifest-omits', {'feature': 'configure_zsh'}, {}, False),
]
"""Every key `resolve.configures` narrows on, in both directions.

A `system.yml` row is not subscribed to the way a package section is — no manifest
names a group membership — so what decides one is a coordinate, a feature, or
whether the first pass planned the package it configures.
"""


@pytest.mark.parametrize(('narrowing', 'manifest', 'planned'), [row[1:] for row in NARROWED], ids=[row[0] for row in NARROWED])
def test_a_configuration_row_reaches_the_plan_only_where_its_narrowing_holds(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    narrowing: dict[str, Any],
    manifest: dict[str, Any],
    planned: bool,
) -> None:
    """Each key narrows independently and all of them must hold, so a row wanting
    two conditions says both rather than needing a combined axis."""
    sandbox.declare(packages=CURL, manifest={**LINUX, **manifest})
    sandbox.shadow('dpkg-query', NOTHING_INSTALLED)
    declare_system(sandbox, {'managed_files': [{'name': 'probe', 'path': str(sandbox.root / 'probe'), 'content': 'x\n', **narrowing}]})

    ran = cli('system', 'plan', '--json')

    # The declared package is pending on every one of these, so the row under test
    # is the difference between one pending item and two.
    assert ran.document['pending'] == (2 if planned else 1)


# ─────────────────────────────────────────────────────────────────────────────
# Every privileged repair, refused and named rather than attempted
# ─────────────────────────────────────────────────────────────────────────────


def pending_group(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> Path:
    declare_system(sandbox, DOCKER_GROUP)
    synthetic_account(monkeypatch)
    no_such_group(monkeypatch)
    return records(sandbox, 'groupadd', 'usermod')


def pending_unit(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`systemctl` is both the read and the write here, so the shadow answers the
    read and records the write — a recorder that answered `is-enabled` with 0
    would report the unit already enabled and plan nothing."""
    declare_system(sandbox, ENABLED_UNIT)
    log = sandbox.root / WITNESS
    sandbox.shadow(
        'systemctl',
        f'#!/bin/sh\ncase "$1" in is-enabled|is-active) exit 1 ;; esac\nprintf "systemctl %s\\n" "$*" >> {log}\nexit 0\n',
    )
    return log


def pending_file(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> Path:
    declare_system(sandbox, managed_whole(sandbox))
    return records(sandbox, 'install')


def pending_login_shell(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> Path:
    """zsh is put on `PATH` deliberately: a shell the run has not installed yet is
    refused *before* privilege is asked for, which is the next case down."""
    declare_system(sandbox, ZSH_LOGIN)
    synthetic_account(monkeypatch, shell='/bin/bash')
    sandbox.shadow('zsh', ANSWERS)
    return records(sandbox, 'chsh')


def pending_package(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> Path:
    sandbox.declare(packages=CURL, manifest=LINUX)
    sandbox.shadow('dpkg-query', NOTHING_INSTALLED)
    return records(sandbox, 'apt-get')


def pending_manager_upgrade(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The package is installed and the manager is behind, so the only pending row
    is the whole-manager upgrade `update.sh` used to run unconditionally."""
    sandbox.declare(packages=CURL, manifest=LINUX)
    sandbox.shadow('dpkg-query', '#!/bin/sh\nprintf "curl\\n"\n')
    sandbox.shadow('apt', '#!/bin/sh\n[ "$1" = "--version" ] && exit 0\nprintf "linux-image/noble 6.8 amd64 [upgradable]\\n"\n')
    return records(sandbox, 'apt-get')


PRIVILEGED: list[tuple[str, Callable[[Sandbox, pytest.MonkeyPatch], Path], str, str]] = [
    ('group-membership', pending_group, 'group/docker', 'authorization was declined'),
    ('systemd-unit', pending_unit, 'systemd/docker.socket', 'authorization was declined'),
    ('managed-file', pending_file, 'file/autologin', 'authorization was declined'),
    ('login-shell', pending_login_shell, 'login-shell/zsh', 'authorization was declined'),
    ('system-package', pending_package, 'system/curl', 'could not be refreshed'),
    ('manager-upgrade', pending_manager_upgrade, 'manager/apt', 'authorization was declined'),
]
"""Every write in this resource that escalates, and the address each is reported as.

Six mechanisms and one authorization. `sysconfig` owns the first four,
`syspkg.install` the fifth and `syspkg.upgrade` the sixth — and every one of them
has to end the same way on a machine that will not give root: nothing written, the
item named, and the run saying which.
"""


@pytest.mark.parametrize(('arrange', 'item', 'message'), [row[1:] for row in PRIVILEGED], ids=[row[0] for row in PRIVILEGED])
def test_a_privileged_repair_without_root_is_reported_rather_than_performed(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    monkeypatch: pytest.MonkeyPatch,
    arrange: Callable[[Sandbox, pytest.MonkeyPatch], Path],
    item: str,
    message: str,
) -> None:
    """The witness is the assertion. A run that printed "declined" having already
    run `usermod` would satisfy every message assertion in this file.

    Exit 3 rather than 1: `apply` answers whether the work it attempted succeeded,
    and a write it could not do is a failure of this run rather than drift.
    """
    log = arrange(sandbox, monkeypatch)

    ran = cli('system', 'apply')

    assert not log.exists(), f'a privileged command ran without root: {log.read_text()}'
    assert ran.exit_code == ExitCode.ISSUE
    assert item in ran.output
    assert message in ran.output


def test_the_plan_names_how_many_writes_will_stop_for_a_password(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Root is acquired at the write, so the only warning anyone gets is this one.

    Three rows of three different mechanisms, counted as one number before any of
    them runs.
    """
    synthetic_account(monkeypatch, shell='/bin/bash')
    no_such_group(monkeypatch)
    sandbox.shadow('systemctl', ANSWERS_NO)
    declare_system(sandbox, {**DOCKER_GROUP, **ENABLED_UNIT, **ZSH_LOGIN})

    ran = cli('system', 'plan')

    assert ran.exit_code == ExitCode.DRIFT
    assert '3 needing root' in ran.output


def test_a_login_shell_the_run_has_not_installed_is_refused_rather_than_failed(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """zsh arrives at `SYSTEM` in the same run this row is decided at
    `SYSTEM_CONFIG` of, so a shell that is still absent at the write is a
    precondition an earlier stage did not deliver — not this run failing.

    `apply` exits 0, which is what keeps a fresh machine from reporting a failed
    install for a package that simply has not landed yet.
    """
    declare_system(sandbox, {'login_shell': [{'name': 'ashellnobodyhas'}]})
    synthetic_account(monkeypatch, shell='/bin/bash')
    log = records(sandbox, 'chsh')

    ran = cli('system', 'apply')

    assert ran.exit_code == ExitCode.CONVERGED
    assert 'is not installed, and the stage that supplies it has not' in ran.output
    assert not log.exists()


def test_a_row_that_became_true_before_the_write_is_skipped_rather_than_repeated(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`observe` runs before the report is printed and before the package stage
    installs anything, so what it decided from can be minutes old — and the
    re-read is what stops the run asking for a password it does not need.

    Arranged through the machine rather than through a clock: the unit's shadow
    reports it disabled while the plan is measured and enabled by the time the
    write is reached.
    """
    declare_system(sandbox, ENABLED_UNIT)
    log = sandbox.root / WITNESS
    flag = sandbox.root / 'enabled-since'
    sandbox.shadow('systemctl', f'#!/bin/sh\n[ -f {flag} ] && exit 0\ntouch {flag}\nprintf "systemctl %s\\n" "$*" >> {log}\nexit 1\n')

    ran = cli('system', 'apply')

    assert ran.exit_code == ExitCode.CONVERGED
    assert 'already configured' in ran.output
    assert log.read_text().splitlines() == ['systemctl is-enabled docker.socket'], 'the only call that reached systemctl was a read'


# ─────────────────────────────────────────────────────────────────────────────
# --source: the package payload without the configuration
# ─────────────────────────────────────────────────────────────────────────────


def test_narrowing_to_the_package_section_drops_the_manager_row_beside_it(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`--source system_packages` is what a container image wants baked in, and
    what a machine wants after adding one package to the list.

    The manager row is the difference. It is planned because the packages were,
    not because anything declares it, so a selection naming the section leaves it
    out — and with it the UNKNOWN currency answer nothing asked for.
    """
    sandbox.declare(packages=CURL, manifest=LINUX)
    sandbox.shadow('dpkg-query', NOTHING_INSTALLED)

    whole = cli('system', 'plan', '--json')
    narrowed = cli('system', 'plan', '--source', 'system_packages', '--json')

    assert (whole.document['pending'], whole.document['unmeasured']) == (1, 1)
    assert (narrowed.document['pending'], narrowed.document['unmeasured']) == (1, 0)


def test_narrowing_the_write_to_the_package_section_leaves_the_configuration_alone(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same `_selected` decides the read and the write, so a preview and the
    write it rehearses cannot disagree about what a section covers."""
    sandbox.declare(packages=CURL, manifest=LINUX)
    sandbox.shadow('dpkg-query', '#!/bin/sh\nprintf "curl\\n"\n')
    sandbox.shadow('apt', ANSWERS_NO)
    declare_system(sandbox, managed_whole(sandbox))
    log = records(sandbox, 'install')

    ran = cli('system', 'apply', '--source', 'system_packages')

    assert ran.exit_code == ExitCode.CONVERGED
    assert not log.exists()
    assert not (sandbox.root / 'etc' / 'autologin.conf').exists()


SOURCES: list[tuple[str, str, str]] = [
    ('a-section-of-the-other-resource', 'go_tools', 'go_tools belongs to packages, not system'),
    ('a-section-of-system-yml', 'managed_files', 'unknown source'),
    ('a-word-that-names-no-section', 'nonsense', 'unknown source'),
]


@pytest.mark.parametrize(('source', 'message'), [row[1:] for row in SOURCES], ids=[row[0] for row in SOURCES])
def test_a_source_this_resource_cannot_serve_is_a_usage_error(
    sandbox: Sandbox, cli: Callable[..., Invocation], source: str, message: str
) -> None:
    """A caller has to be able to tell "you typed it wrong" from "it ran and
    failed", and only the first is worth retrying.

    `managed_files` is a real section and still not a `--source`: the option's
    values are read out of `packages.yml`, and `system.yml`'s sections are not
    payload anything narrows to. The message says `unknown source` rather than
    naming the other file, which is the one place this reads worse than it is.
    """
    sandbox.declare(
        packages={**CURL, 'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}]},
        manifest={**LINUX, 'go_tools': ['task']},
    )

    ran = cli('system', 'plan', '--source', source, catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert message in ran.output


def test_a_source_the_machine_declares_no_section_for_is_rejected_rather_than_empty(
    sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The `--source` values are this machine's `packages.yml` keys, so a section
    the file happens not to declare is refused by the same message a typo gets.

    Deliberate — the option completes from the file rather than from a list
    written here, and a hand-written enum was already missing six sections on the
    day it was written.
    """
    sandbox.declare(packages={}, manifest=LINUX)

    ran = cli('system', 'plan', '--source', 'system_packages', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'unknown source' in ran.output


# ─────────────────────────────────────────────────────────────────────────────
# The offline gate, which is before the walk rather than inside it
# ─────────────────────────────────────────────────────────────────────────────


def test_an_offline_apply_with_no_staged_bundle_stops_before_measuring_anything(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The gate is above the walk, so a machine that cannot install anything is
    told why rather than shown a plan it has no way to act on.

    The absent summary sentence is what says the walk never started; the path in
    the message is not asserted because rich wraps it mid-word at this width.
    """
    sandbox.declare(packages=CURL, manifest=LINUX)
    sandbox.shadow('dpkg-query', NOTHING_INSTALLED)

    ran = cli('system', 'apply', '--offline')

    assert ran.exit_code == ExitCode.ISSUE
    assert 'offline needs a staged bundle' in ran.output
    assert 'declared system packages' not in ran.output


def test_a_staged_bundle_satisfies_the_offline_gate(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Nothing is staged over an existing bundle: a machine part way through an
    offline install has one, and re-reading the archive would be work for an
    answer already on disk."""
    sandbox.declare(packages=CURL, manifest=LINUX)
    sandbox.shadow('dpkg-query', '#!/bin/sh\nprintf "curl\\n"\n')
    sandbox.shadow('apt', ANSWERS_NO)
    sandbox.stage_bundle({'curl': '8.0.0'})

    ran = cli('system', 'apply', '--offline')

    assert 'offline needs a staged bundle' not in ran.output
    assert ran.exit_code == ExitCode.CONVERGED


# ─────────────────────────────────────────────────────────────────────────────
# What the summary sentence claims, counted from what was measured
# ─────────────────────────────────────────────────────────────────────────────


def a_machine_missing_its_declared_package(sandbox: Sandbox) -> None:
    sandbox.declare(packages=CURL, manifest=LINUX)
    sandbox.shadow('dpkg-query', NOTHING_INSTALLED)


def test_the_package_summary_does_not_claim_an_install_the_counts_contradict(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The sentence and the numbers beside it are one document and agree.

    It read `all N declared system packages installed`, where `N` was how many
    rows were *examined* — a count of the declaration wearing the word
    "installed". `check --json` answered `pending: 1` beside it in the same
    object, and the human run prints the sentence alone, so a reader who believed
    the prose was told the opposite of what was measured. `check` prints it
    whenever nothing needs a person, which is the common case for a machine that
    is merely missing a package.
    """
    a_machine_missing_its_declared_package(sandbox)

    ran = cli('system', 'check', '--json')

    assert ran.document['pending'] == 1, 'the machine is missing the one package it declares'
    assert '0 of 1 declared system packages installed' in ran.document['detail']
    assert 'all 1 declared system packages installed' not in ran.document['detail']


def test_the_configuration_summary_counts_only_the_rows_that_match(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """One declared row, MISSING, and the count says none matched.

    The count was `len(self.config)`, which is every row `_observe_config`
    answered for whatever that answer turned out to be — so a machine with nine
    rows and three of them drifted said nine match.
    """
    declare_system(sandbox, managed_whole(sandbox))

    ran = cli('system', 'check', '--json')

    assert ran.document['pending'] == 1, 'the declared file does not exist'
    assert '0 configuration item(s) match' in ran.document['detail']


# ─────────────────────────────────────────────────────────────────────────────
# needs_root on a row whose repair escalates unconditionally
# ─────────────────────────────────────────────────────────────────────────────


def a_file_declaring_it_needs_no_root(sandbox: Sandbox) -> Path:
    declare_system(
        sandbox,
        {'managed_files': [{'name': 'thing', 'path': str(sandbox.root / 'etc' / 'thing.conf'), 'content': 'hello\n', 'needs_root': False}]},
    )
    return records(sandbox, 'install')


def test_a_row_declaring_it_needs_no_root_is_planned_as_needing_none(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Current behaviour on the read side, and it is the honest half.

    `needs_root` is a field on `SystemConfig`, so any of the four kinds may carry
    it; only the `steps` rows declare it today, which is why the mismatch below
    is latent rather than live.
    """
    a_file_declaring_it_needs_no_root(sandbox)

    ran = cli('system', 'plan', '--json')

    assert ran.document['pending'] == 1
    assert ran.document['privileged'] == 0


def test_a_row_declaring_it_needs_no_root_is_written_without_root(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`needs_root` says whether repairing this row escalates, and the repair does
    not read it.

    The field decides one thing today — the number `plan` prints and the password
    warning built from it — so a row that declares `false` is a row the plan
    promises costs nothing and the write refuses to do. Either the write honours
    it or the field stops being settable on a row whose repair cannot.
    """
    a_file_declaring_it_needs_no_root(sandbox)

    ran = cli('system', 'apply')

    assert ran.exit_code == ExitCode.CONVERGED
    assert (sandbox.root / 'etc' / 'thing.conf').read_text() == 'hello\n'


# ─────────────────────────────────────────────────────────────────────────────
# windows: the Windows side of a WSL install
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def under_a_windows_side(monkeypatch: pytest.MonkeyPatch) -> Callable[[Path | None], None]:
    """Say whether this machine has a Windows side, and where its home is.

    **The one place this module patches `dotfiles` itself, because there is no
    seam.** `under_wsl` reads `/proc/version` — chosen deliberately over an
    environment variable, so that the marker survives `sudo` and a login shell
    that sets nothing — and `windows_home` builds an absolute path under
    `/mnt/c/Users`. Neither takes an argument, neither reads a variable, and the
    CLI calls `destination()` with nothing to pass. A test that read the real
    `/proc/version` would assert one thing on this box and the opposite on the
    work box, which is the machine-independence the matrix exists to keep.

    `cmd.exe` stays a real seam and is shadowed rather than patched wherever the
    question is what Windows answered.
    """

    def pretend(home: Path | None) -> None:
        monkeypatch.setattr(windows, 'under_wsl', lambda: home is not None)
        if home is not None:
            home.mkdir(parents=True, exist_ok=True)
            monkeypatch.setattr(windows, 'windows_home', lambda: home)

    return pretend


UNREACHABLE: list[tuple[str, str | None, str]] = [
    ('no-windows-side-at-all', None, 'not running under WSL'),
    ('windows-will-not-say-who-it-is', ANSWERS_NO, 'could not ask Windows for its username'),
    ('a-windows-home-that-is-not-there', '#!/bin/sh\nprintf "SYNTHETIC\\r\\n"\n', 'Windows home does not exist at /mnt/c/Users/SYNTHETIC'),
]
"""The three ways the Windows side is out of reach, and what each says.

`cmd.exe` is the seam for the last two: `windows_home` asks Windows for
`%USERNAME%` rather than reusing the WSL account, because the two differ on this
fleet and the employee id the Windows account is named after is exactly what does
not go in this repo.
"""


@pytest.mark.parametrize(('shell', 'message'), [row[1:] for row in UNREACHABLE], ids=[row[0] for row in UNREACHABLE])
@pytest.mark.parametrize('verb', ['check', 'apply'])
def test_a_windows_command_off_the_windows_side_says_so_rather_than_inventing_a_path(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    monkeypatch: pytest.MonkeyPatch,
    verb: str,
    shell: str | None,
    message: str,
) -> None:
    """A guess here writes binaries into a directory nothing reads, or reports a
    machine's Windows tools missing on a machine that has no Windows."""
    monkeypatch.setattr(windows, 'under_wsl', lambda: shell is not None)
    if shell is not None:
        sandbox.shadow('cmd.exe', shell)

    ran = cli('windows', verb)

    assert ran.exit_code == ExitCode.ISSUE
    assert message in ran.output


def test_windows_check_reports_the_declared_filenames_missing_from_one_directory(
    sandbox: Sandbox, cli: Callable[..., Invocation], under_a_windows_side: Callable[[Path | None], None]
) -> None:
    """The whole measurement is which filenames exist in the one directory Git
    Bash puts on its PATH — no winget, no network, which is what stopped this
    existing while the answer lived inside a script that could only install."""
    under_a_windows_side(sandbox.root / 'windows-home')

    ran = cli('windows', 'check')

    assert ran.exit_code == ExitCode.DRIFT
    assert f'0 of {len(windows.TOOLS)} Windows tools' in ran.output
    for tool in windows.TOOLS:
        # By field rather than by sentence. The rows are column-aligned, so the
        # gap between the state and the name is padding and changes whenever the
        # widest name does.
        assert re.search(rf'missing\s+{re.escape(tool.name)}\b', ran.output)


def test_windows_check_is_converged_once_every_declared_binary_is_there(
    sandbox: Sandbox, cli: Callable[..., Invocation], under_a_windows_side: Callable[[Path | None], None]
) -> None:
    """Keyed on the declared `exe` rather than the tool name, which differ:
    ripgrep's binary is `rg.exe`."""
    home = sandbox.root / 'windows-home'
    under_a_windows_side(home)
    destination = home / '.local' / 'bin'
    destination.mkdir(parents=True)
    for tool in windows.TOOLS:
        (destination / tool.exe).write_text('BINARY')

    ran = cli('windows', 'check')

    assert ran.exit_code == ExitCode.CONVERGED
    assert f'{len(windows.TOOLS)} of {len(windows.TOOLS)} Windows tools' in ran.output


def test_an_offline_windows_apply_without_a_source_is_a_usage_error(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`--offline` names *where from*, and a run that accepted it alone would fall
    through to winget on the one machine that cannot reach it."""
    ran = cli('windows', 'apply', '--offline', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert '--offline needs --source' in ran.output


BUNDLES: list[tuple[str, str, ExitCode, str]] = [
    ('a-bundle-that-is-not-there', 'absent.tar.gz', ExitCode.ISSUE, 'bundle not found'),
    ('a-bundle-carrying-nothing', 'empty', ExitCode.ISSUE, 'no .exe files'),
]


@pytest.mark.parametrize(('name', 'code', 'message'), [row[1:] for row in BUNDLES], ids=[row[0] for row in BUNDLES])
def test_an_unusable_bundle_fails_rather_than_reporting_a_clean_install(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    under_a_windows_side: Callable[[Path | None], None],
    name: str,
    code: ExitCode,
    message: str,
) -> None:
    """An empty directory copies zero files and would otherwise exit as though it
    had done the job — on the one machine that cannot go and get them."""
    under_a_windows_side(sandbox.root / 'windows-home')
    (sandbox.root / 'empty').mkdir()

    ran = cli('windows', 'apply', '--offline', '--source', str(sandbox.root / name))

    assert ran.exit_code == code
    assert message in ran.output


def test_an_offline_windows_apply_installs_what_the_bundle_carries_and_names_the_rest(
    sandbox: Sandbox, cli: Callable[..., Invocation], under_a_windows_side: Callable[[Path | None], None]
) -> None:
    """Exit 3 for a partial bundle, because a tool this machine expects and the
    bundle lacks is the failure worth naming."""
    home = sandbox.root / 'windows-home'
    under_a_windows_side(home)
    bundle = sandbox.root / 'bundle'
    bundle.mkdir()
    (bundle / 'rg.exe').write_text('RIPGREP')

    ran = cli('windows', 'apply', '--offline', '--source', str(bundle))

    assert (home / '.local' / 'bin' / 'rg.exe').read_text() == 'RIPGREP'
    assert ran.exit_code == ExitCode.ISSUE
    assert f'1 of {len(windows.TOOLS)} Windows tools' in ran.output
    assert re.search(r'jq\s+did not land', ran.output)


def test_a_complete_bundle_converges_and_reaches_no_windows_side_to_do_it(
    sandbox: Sandbox, cli: Callable[..., Invocation], under_a_windows_side: Callable[[Path | None], None]
) -> None:
    home = sandbox.root / 'windows-home'
    under_a_windows_side(home)
    bundle = sandbox.root / 'bundle'
    bundle.mkdir()
    for tool in windows.TOOLS:
        (bundle / tool.exe).write_text('BINARY')

    ran = cli('windows', 'apply', '--offline', '--source', str(bundle))

    assert ran.exit_code == ExitCode.CONVERGED
    assert cli('windows', 'check').exit_code == ExitCode.CONVERGED


def test_an_online_windows_apply_asks_winget_for_every_declared_package(
    sandbox: Sandbox, cli: Callable[..., Invocation], under_a_windows_side: Callable[[Path | None], None]
) -> None:
    """winget exits non-zero for "already at latest version", so its status is
    ignored and what decides the outcome is whether the binary landed. A winget
    that installs nothing therefore has to report every tool unresolved rather
    than a clean run."""
    under_a_windows_side(sandbox.root / 'windows-home')
    asked = sandbox.root / 'winget-calls'
    sandbox.shadow('cmd.exe', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {asked}\nexit 0\n')

    ran = cli('windows', 'apply')

    requested = asked.read_text()
    for tool in windows.TOOLS:
        assert tool.winget in requested
    assert ran.exit_code == ExitCode.ISSUE
    assert f'0 of {len(windows.TOOLS)} Windows tools' in ran.output


def test_windows_create_runs_off_the_windows_side_and_upstream_is_where_it_stops(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unlike its siblings this one only downloads, so the machine building the
    bundle is deliberately not the machine that will install it.

    Which makes it the one command in this module that must reach GitHub — so the
    matrix's network guard is the assertion. It gets past the WSL check, creates
    the directory it was told to write into, and stops at the first release
    lookup.
    """
    monkeypatch.setattr(windows, 'under_wsl', lambda: False)

    with pytest.raises(ReachedTheNetwork):
        cli('windows', 'create', str(sandbox.root / 'out' / 'tools.tar.gz'))

    assert (sandbox.root / 'out').is_dir()


# ─────────────────────────────────────────────────────────────────────────────
# What the verbs write, and what they leave alone
# ─────────────────────────────────────────────────────────────────────────────


@dc.dataclass(frozen=True)
class Verb:
    argv: tuple[str, ...]
    records_a_run: bool


VERBS: list[tuple[str, Verb]] = [
    ('system-plan', Verb(('system', 'plan'), records_a_run=False)),
    ('system-check', Verb(('system', 'check'), records_a_run=False)),
    ('system-apply', Verb(('system', 'apply'), records_a_run=True)),
]


@pytest.mark.parametrize('verb', [row[1] for row in VERBS], ids=[row[0] for row in VERBS])
def test_only_the_write_verb_leaves_a_run_record(sandbox: Sandbox, cli: Callable[..., Invocation], verb: Verb) -> None:
    """A resource-scoped read goes through `_survey`, which begins no run — the
    record belongs to the whole-machine verbs and to every apply.

    Asserted here because the two read verbs are what a shell prompt and a timer
    call, and a record per prompt is what filled the state directory with
    thousands of empty files once already.
    """
    declare_system(sandbox, managed_whole(sandbox))
    write(sandbox.root / 'etc' / 'autologin.conf', '[Service]\n')

    ran = cli(*verb.argv)

    assert ran.exit_code == ExitCode.CONVERGED
    assert bool(sandbox.run_files) is verb.records_a_run


def test_a_read_verb_writes_nothing_the_machine_can_notice(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Structural rather than a promise: there is no code path a `--dry-run` could
    switch off, so what proves it is that every privileged tool is shadowed and
    the declared file is still absent."""
    declare_system(sandbox, {**DOCKER_GROUP, **managed_whole(sandbox)})
    synthetic_account(monkeypatch)
    no_such_group(monkeypatch)
    log = records(sandbox, 'groupadd', 'usermod', 'install', 'chsh', 'systemctl')

    assert cli('system', 'plan').exit_code == ExitCode.DRIFT
    assert cli('system', 'check').exit_code == ExitCode.CONVERGED
    assert not log.exists()
    assert not (sandbox.root / 'etc' / 'autologin.conf').exists()
