"""`system`: the half of the machine that answers to somebody else.

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
"""

from __future__ import annotations

import dataclasses as dc
import grp
import json
import os
import pwd
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles.vocabulary import ExitCode
from matrix.harness import ANSWERS
from matrix.harness import REFUSED
from matrix.harness import Invocation
from matrix.harness import Sandbox
from matrix.harness import resource

Arrange = Callable[[Sandbox, pytest.MonkeyPatch], None]
"""How one case makes its machine. Given the sandbox and the same monkeypatch it
was built with, so a case can shadow a binary and patch `grp` in one place."""


def named(ran: Invocation, key: str) -> list[str]:
    """The addresses in one of the `system` row's lists: findings, others, examined.

    The reason this module has it. A `system` plan holds rows of six mechanisms at
    once — a package, its manager, a group, a unit, a file, a login shell — so the
    resource's `pending` is a sum and every case here is about exactly one of the
    addends. Asserting on the sum passed on a workstation and failed in CI at
    `assert 3 == 2`, naming neither the row under test nor the row that moved the
    total.

    One accessor for all three lists, because every one of them keys its rows on
    `item` — a change and an examined row alike — which is what lets the four sets
    below be told apart by *which list* an address turned up in rather than by
    re-deciding its verdict here. A second classification written in a test is one
    that can agree with `sift` today and disagree next week.
    """
    return [entry['item'] for entry in resource(ran, 'system')[key]]


class Lands(StrEnum):
    """Which set one address has to turn up in, once both read verbs have run.

    Four, and the pair of verbs is what separates them: `plan` keeps what `apply`
    can repair, `check` keeps what needs a person, what neither keeps is what
    nothing could measure, and an address in no finding at all was looked at and
    matched.
    """

    PENDING = 'pending'
    ATTENTION = 'attention'
    UNMEASURED = 'unmeasured'
    MATCHED = 'matched'


def lands(planned: Invocation, checked: Invocation, address: str) -> Lands:
    """Where the two documents between them put one address.

    `others` is each verb's residue — everything that drifted and it did not keep —
    so plan's holds attention and unmeasured, and check's holds pending and
    unmeasured. Their intersection is the unmeasured exactly, which is why this
    asks for both rather than reading one and trusting an order.
    """
    if address in named(planned, 'findings'):
        return Lands.PENDING
    if address in named(checked, 'findings'):
        return Lands.ATTENTION
    if address in named(planned, 'others') and address in named(checked, 'others'):
        return Lands.UNMEASURED
    if address in named(planned, 'examined'):
        return Lands.MATCHED
    raise AssertionError(f'{address} is in no list of the system row: {json.dumps(resource(planned, "system"), indent=2)}')


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


ROWS: list[tuple[str, Arrange, str, Lands]] = [
    ('an-absent-managed-file', absent_file, 'file/zdotdir', Lands.PENDING),
    ('a-managed-file-already-carrying-the-line', file_with_the_line, 'file/zdotdir', Lands.MATCHED),
    ('a-managed-file-missing-the-line', file_without_the_line, 'file/zdotdir', Lands.PENDING),
    ('a-wholly-owned-file-that-matches', file_matching_exactly, 'file/autologin', Lands.MATCHED),
    ('a-wholly-owned-file-that-differs', file_differing, 'file/autologin', Lands.PENDING),
    ('a-group-the-account-is-already-in', already_in_the_group, 'group/docker', Lands.MATCHED),
    ('a-group-the-account-is-not-in', not_in_the_group, 'group/docker', Lands.PENDING),
    ('a-group-this-entry-creates', group_this_entry_creates, 'group/docker', Lands.PENDING),
    ('a-group-nothing-here-creates', group_nothing_here_creates, 'group/docker', Lands.ATTENTION),
    ('a-unit-already-enabled', unit_already_enabled, 'systemd/docker.socket', Lands.MATCHED),
    ('a-unit-that-should-be-enabled', unit_not_enabled, 'systemd/docker.socket', Lands.PENDING),
    ('a-unit-wanted-off-and-not-installed', unit_wanted_off_and_not_installed, 'systemd/gdm', Lands.MATCHED),
    ('a-machine-with-no-systemctl', no_systemctl_at_all, 'systemd/docker.socket', Lands.UNMEASURED),
    ('a-login-shell-already-set', login_shell_already_zsh, 'login-shell/zsh', Lands.MATCHED),
    ('a-login-shell-still-bash', login_shell_still_bash, 'login-shell/zsh', Lands.PENDING),
]
"""Each `system.yml` kind in each state it can be in, named by the address it
produces and by which of the four sets that address belongs in.

The address is the point. Every case here declares exactly one row and is about
what happens to it, and each was written as a count of the whole resource instead —
which held only while nothing else in the walk had anything to say. It stopped
holding the moment the package managers were shadowed, and the failure that
followed read `assert 3 == 2`.
"""


@pytest.mark.parametrize(('arrange', 'address', 'expected'), [row[1:] for row in ROWS], ids=[row[0] for row in ROWS])
def test_a_configuration_row_is_drift_for_plan_and_a_finding_only_for_check(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    monkeypatch: pytest.MonkeyPatch,
    arrange: Arrange,
    address: str,
    expected: Lands,
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

    assert lands(planned, checked, address) is expected
    assert planned.exit_code == (ExitCode.DRIFT if expected is Lands.PENDING else ExitCode.CONVERGED)
    assert checked.exit_code == (ExitCode.ISSUE if expected is Lands.ATTENTION else ExitCode.CONVERGED)
    assert checked.exit_code != ExitCode.DRIFT, 'check answers 0 or 3 and never 1'


@pytest.mark.parametrize(('arrange', 'address', 'expected'), [row[1:] for row in ROWS], ids=[row[0] for row in ROWS])
def test_every_configuration_repair_declares_that_it_needs_root(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    monkeypatch: pytest.MonkeyPatch,
    arrange: Arrange,
    address: str,
    expected: Lands,
) -> None:
    """Declared before anything runs, which is the half of the front-loaded design
    that survived acquiring root at the write. A plan that is complete can say
    which of its findings will stop for a password; nothing here prompts to find out.

    Asserted on the row rather than on the resource's total. The two agreed only
    because every mechanism this file declares escalates — so a row that did not
    would have moved a count that named nothing, and `needs_root: false` below is
    exactly that row.
    """
    arrange(sandbox, monkeypatch)

    planned = cli('system', 'plan', '--json')
    escalating = [change['item'] for change in resource(planned, 'system')['findings'] if change['privileged']]

    assert escalating == ([address] if expected is Lands.PENDING else [])


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
    two conditions says both rather than needing a combined axis.

    The declared package is pending on every one of these, so the plan is never
    empty and the question is only whether `file/probe` is beside it. This asked
    whether the total was two or one, which is the same question until something
    else in the walk moves — and on the CI runner the real `apt` answered where the
    desk's had nothing to say, making it three and two, and the failure named
    neither row.
    """
    sandbox.declare(packages=CURL, manifest={**LINUX, **manifest})
    sandbox.shadow('dpkg-query', NOTHING_INSTALLED)
    declare_system(sandbox, {'managed_files': [{'name': 'probe', 'path': str(sandbox.root / 'probe'), 'content': 'x\n', **narrowing}]})

    ran = cli('system', 'plan', '--json')

    assert ('file/probe' in named(ran, 'findings')) is planned


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

    assert named(whole, 'findings') == named(narrowed, 'findings') == ['system/curl']
    assert 'manager/apt' in named(whole, 'others')
    assert 'manager/apt' not in named(narrowed, 'others')


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
    detail = resource(ran, 'system')['detail']

    assert 'system/curl' in named(ran, 'others'), 'the machine is missing the one package it declares'
    assert '0 of 1 declared system packages installed' in detail
    assert 'all 1 declared system packages installed' not in detail


def test_the_configuration_summary_counts_only_the_rows_that_match(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """One declared row, MISSING, and the count says none matched.

    The count was `len(self.config)`, which is every row `_observe_config`
    answered for whatever that answer turned out to be — so a machine with nine
    rows and three of them drifted said nine match.
    """
    declare_system(sandbox, managed_whole(sandbox))

    ran = cli('system', 'check', '--json')

    assert 'file/autologin' in named(ran, 'others'), 'the declared file does not exist'
    assert '0 configuration item(s) match' in resource(ran, 'system')['detail']


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
    (change,) = resource(ran, 'system')['findings']

    assert change['item'] == 'file/thing'
    assert change['privileged'] is False


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
