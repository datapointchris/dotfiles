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
from dotfiles.privilege import Escalation
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable

NOT_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason='the ALREADY_ROOT path is the one that runs as root')

INSTALL_DOCKER = (Escalation('add chris to the docker group'),)


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
# Authorization
# ─────────────────────────────────────────────────────────────────────────────


def test_nothing_to_escalate_never_touches_sudo(tmp_path: Path, fake_bin: Path) -> None:
    """A converged machine must not be asked for a password to be told so."""
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log)
    privilege = Privilege()

    assert privilege.authorize(()) is Authorization.NOT_NEEDED
    assert recorded(log) == []


@NOT_ROOT
def test_a_machine_without_sudo_reports_unavailable_rather_than_failing(fake_bin: Path) -> None:
    """The LXC container and the Docker harnesses. The unprivileged 90% of a run
    still has to land, which is what makes them runnable without a
    passwordless-sudo carve-out."""
    assert Privilege().authorize(INSTALL_DOCKER) is Authorization.UNAVAILABLE


@NOT_ROOT
def test_a_declined_password_is_declined_rather_than_retried(tmp_path: Path, fake_bin: Path) -> None:
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log, exit_code=1)

    assert Privilege().authorize(INSTALL_DOCKER) is Authorization.DECLINED
    assert recorded(log) == ['-v']


@NOT_ROOT
def test_authorizing_twice_asks_once(tmp_path: Path, fake_bin: Path) -> None:
    """`authorize` is the run's, not a provider's, and a provider that called it
    anyway must not open a second prompt."""
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log)
    privilege = Privilege()
    try:
        assert privilege.authorize(INSTALL_DOCKER) is Authorization.GRANTED
        assert privilege.authorize(INSTALL_DOCKER) is Authorization.GRANTED
    finally:
        privilege.stop()

    assert recorded(log) == ['-v']


# ─────────────────────────────────────────────────────────────────────────────
# Running something
# ─────────────────────────────────────────────────────────────────────────────


def test_running_before_authorizing_raises_rather_than_prompting() -> None:
    """A write reached without the run having asked is a bug in the run, not a
    reason to open a password prompt in the middle of one."""
    with pytest.raises(PrivilegeUnavailable):
        Privilege().run(['true'], reason='anything')


@NOT_ROOT
def test_a_privileged_command_cannot_open_a_second_prompt(tmp_path: Path, fake_bin: Path) -> None:
    """`-n` after `-v`: the timestamp is valid, so this is the whole of "one
    prompt, at the front, or none"."""
    log = tmp_path / 'calls'
    fake_sudo(fake_bin, log)
    privilege = Privilege()
    try:
        privilege.authorize(INSTALL_DOCKER)
        assert privilege.run(['usermod', '-aG', 'docker', 'chris'], reason='group').ok
    finally:
        privilege.stop()

    assert recorded(log) == ['-v', '-n usermod -aG docker chris']


@NOT_ROOT
def test_a_refused_run_names_why_in_words_a_report_can_print(fake_bin: Path) -> None:
    privilege = Privilege()
    privilege.authorize(INSTALL_DOCKER)

    with pytest.raises(PrivilegeUnavailable):
        privilege.run(['true'], reason='anything')
    assert 'no sudo' in privileges.refusal(privilege.state)
