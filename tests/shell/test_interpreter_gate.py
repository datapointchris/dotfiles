"""The gate that stops CI reporting green on a runner with no zsh.

This tier degrades to skips on a machine missing an interpreter, which is right
on a workstation and wrong on a runner. `--require-interpreters` inverts it, and
CI passes the flag — so the flag is load-bearing, and nothing else in the suite
would notice if it stopped working. A renamed marker, a hook that stopped being
called, an option registered on a conftest pytest no longer treats as initial:
each leaves a run that still exits 0 while enforcing nothing.

So both readings are asserted by running pytest itself against a PATH with the
interpreters taken off it. The refusal fires during collection, which is when the
hook runs, so proving it needs no test to execute.
"""

from __future__ import annotations

import dataclasses as dc
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from shells import REPO

PYTEST = (sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider')
TMUX_TIER = 'tests/shell/test_tmux_plugins_sh.py'


@dc.dataclass(frozen=True, slots=True)
class Run:
    stdout: str
    stderr: str
    returncode: int

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


def run_pytest(*arguments: str, path: str | None = None) -> Run:
    """Run pytest in a subprocess, optionally against a stripped PATH."""
    env = dict(os.environ)
    if path is not None:
        env['PATH'] = path
    completed = subprocess.run([*PYTEST, *arguments], capture_output=True, text=True, env=env, cwd=REPO, check=False)
    return Run(completed.stdout, completed.stderr, completed.returncode)


COLLECTION_NEEDS = ('bash', 'git')
"""What collecting this directory runs before any test does.

`test_repo_root` shells out to `git ls-files` and `test_windows_shell_sync_sh`
builds its parameters from a bash run, both at import time. A PATH without these
dies during collection for the wrong reason, and the refusal under test is never
reached — so they are carried, and only the interpreters are taken away.
"""


@pytest.fixture
def without_interpreters(tmp_path: Path) -> str:
    """A bare runner: no zsh, no tmux, and nothing else missing to confuse the result.

    Built up rather than cut down. Dropping the directory zsh lives in would take
    /usr/bin, and with it bash and git.
    """
    for tool in COLLECTION_NEEDS:
        found = shutil.which(tool)
        assert found, f'this tier cannot be collected on a machine without {tool}'
        (tmp_path / tool).symlink_to(found)
    return str(tmp_path)


@pytest.fixture
def with_interpreters(without_interpreters: str) -> str:
    """The satisfied PATH, built rather than borrowed from the machine underneath.

    Asserting that *this* machine satisfies the flag would be a test of the
    machine: the generic CI job installs neither interpreter on purpose, so the
    positive case has to supply its own. Stubs are enough because the gate calls
    `shutil.which` and never runs them — what runs a real zsh is the rest of the
    tier, in the job that installs one.
    """
    for interpreter in ('zsh', 'tmux'):
        stub = Path(without_interpreters) / interpreter
        stub.write_text('#!/bin/sh\nexit 0\n')
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return without_interpreters


def test_the_run_is_refused_when_a_required_interpreter_is_missing(without_interpreters: str):
    """Both marker spellings reach the same enforcement.

    tmux is required by a module-wide `pytestmark` and zsh by a single parameter
    of one, so naming both in the refusal is what proves the set is read off the
    collected items rather than off a list someone maintains.
    """
    result = run_pytest('tests/shell', '--collect-only', '--require-interpreters', path=without_interpreters)

    assert result.returncode != 0
    assert 'no tmux, zsh' in result.output


def test_a_missing_interpreter_is_only_a_skip_without_the_flag(without_interpreters: str):
    """The workstation reading, asserted on the tier that needs the missing binary."""
    result = run_pytest(TMUX_TIER, '-rs', path=without_interpreters)

    assert result.returncode == 0
    assert 'tmux is not installed' in result.output


def test_the_flag_lets_a_satisfied_machine_through(with_interpreters: str):
    """The positive case, which is what CI actually runs.

    A gate asserted only by its refusal would pass on a machine where it refuses
    unconditionally, and every CI run would then fail for a reason no test names.
    """
    result = run_pytest('tests/shell', '--collect-only', '--require-interpreters', path=with_interpreters)

    assert result.returncode == 0, result.output
