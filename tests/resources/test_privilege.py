"""The sudo chokepoint: one module escalates, once, and refuses rather than raising.

Every seam here is a real one. `sudo` is found on `PATH`, so shadowing it with a
script that records its argv is how the escalation is observed — nothing in
`src/dotfiles/` is patched, and the assertions are about what a real subprocess
was actually asked to do.
"""

from __future__ import annotations

import ast
import os
import stat
from pathlib import Path

import pytest

from dotfiles import paths
from dotfiles import privilege as privileges
from dotfiles.privilege import Authorization
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable

NOT_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason='the ALREADY_ROOT path is the one that runs as root')


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A bin directory that is the *whole* PATH, so `sudo` is only what is put here."""
    directory = tmp_path / 'bin'
    directory.mkdir()
    monkeypatch.setenv('PATH', str(directory))
    return directory


def fake_sudo(directory: Path, log: Path, exit_code: int = 0) -> None:
    script = directory / 'sudo'
    script.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\nexit {exit_code}\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)


def recorded(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.is_file() else []


# ─────────────────────────────────────────────────────────────────────────────
# One module says the word
# ─────────────────────────────────────────────────────────────────────────────


def test_only_privilege_py_contains_the_string_sudo() -> None:
    """The rule that makes the chokepoint a chokepoint rather than a convention.

    Asserted over string *literals* rather than over the file's text, because
    half the package explains in prose why it does not escalate and deleting
    those sentences to satisfy a grep would remove the reasoning this depends on.
    """
    offenders: list[str] = []
    for module in sorted((paths.REPO_ROOT / 'src' / 'dotfiles').rglob('*.py')):
        if module.name == 'privilege.py':
            continue
        tree = ast.parse(module.read_text())
        literals = [node for node in ast.walk(tree) if isinstance(node, ast.Constant) and node.value == 'sudo']
        offenders.extend(f'{module.relative_to(paths.REPO_ROOT)}:{node.lineno}' for node in literals)

    assert not offenders, 'only privilege.py may escalate; these pass sudo as a literal: ' + ', '.join(offenders)


# ─────────────────────────────────────────────────────────────────────────────
# Acquiring root
# ─────────────────────────────────────────────────────────────────────────────


def test_a_run_that_writes_nothing_privileged_never_touches_sudo(tmp_path: Path, fake_bin: Path) -> None:
    """A converged machine must not be asked for a password to be told so. Root is
    acquired at the write, so a run with no privileged write never reaches one."""
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log)

    assert Privilege().state is Authorization.NOT_NEEDED
    assert recorded(log) == []


@NOT_ROOT
def test_a_machine_without_sudo_reports_unavailable_rather_than_failing(fake_bin: Path) -> None:
    """The LXC container and the Docker harnesses. The unprivileged 90% of a run
    still has to land, which is what makes them runnable without a
    passwordless-sudo carve-out."""
    assert Privilege().acquire('add chris to the docker group') is Authorization.UNAVAILABLE


@NOT_ROOT
def test_a_caller_that_must_not_block_declines_without_prompting(tmp_path: Path, fake_bin: Path) -> None:
    """`offer=False` is how a non-interactive caller says so. Without it, root is
    acquired at the write — which is right at a terminal and a hang under a timer."""
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log)

    assert Privilege(offer=False).acquire('anything') is Authorization.DECLINED
    assert recorded(log) == []


@NOT_ROOT
def test_a_declined_password_is_declined_rather_than_retried(tmp_path: Path, fake_bin: Path) -> None:
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log, exit_code=1)

    assert Privilege().acquire('add chris to the docker group') is Authorization.DECLINED
    assert recorded(log) == ['-v']


@NOT_ROOT
def test_a_refusal_is_not_reopened_for_every_later_write(tmp_path: Path, fake_bin: Path) -> None:
    """A machine without a password is not going to grow one between two writes,
    and asking again per item is how one refusal becomes a wall of prompts."""
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log, exit_code=1)
    privilege = Privilege()

    assert privilege.acquire('first') is Authorization.DECLINED
    assert privilege.acquire('second') is Authorization.DECLINED
    assert recorded(log) == ['-v']


@NOT_ROOT
def test_two_privileged_writes_ask_for_one_password(tmp_path: Path, fake_bin: Path) -> None:
    """Acquiring at the write does not mean acquiring per write. The prompt happens
    once and the rest of the run rides the answer."""
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log)
    privilege = Privilege()

    assert privilege.run(['usermod', '-aG', 'docker', 'chris'], reason='group').ok
    assert privilege.run(['systemctl', 'enable', 'docker'], reason='unit').ok

    assert recorded(log) == ['-v', 'usermod -aG docker chris', 'systemctl enable docker']


# ─────────────────────────────────────────────────────────────────────────────
# Running something
# ─────────────────────────────────────────────────────────────────────────────


@NOT_ROOT
def test_a_write_acquires_root_by_itself(tmp_path: Path, fake_bin: Path) -> None:
    """No caller authorizes any more. This is the whole of the model change: the
    front prompt was buying a property macOS will not give, because a sudo
    timestamp cannot be kept alive there."""
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log)

    assert Privilege().run(['usermod', '-aG', 'docker', 'chris'], reason='group').ok
    assert recorded(log) == ['-v', 'usermod -aG docker chris']


@NOT_ROOT
def test_a_refused_run_raises_having_written_nothing(fake_bin: Path) -> None:
    """No sudo on the machine at all. The write must not half-happen, and the
    caller has to be able to report why."""
    privilege = Privilege()

    with pytest.raises(PrivilegeUnavailable):
        privilege.run(['true'], reason='anything')
    assert 'no sudo' in privileges.refusal(privilege.state)
