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


@pytest.fixture
def only_bash(tmp_path: Path) -> str:
    """A PATH carrying bash and nothing else, which is how a bare runner is simulated.

    Emptying PATH outright does not work: `test_repo_root` and
    `test_windows_shell_sync_sh` build their parameters by running bash at import
    time, so collection would die on the wrong binary and the refusal below would
    never be reached. Dropping the directory zsh lives in is no better — it is
    /usr/bin, which takes bash with it.
    """
    bash = shutil.which('bash')
    assert bash, 'a machine with no bash cannot run this tier at all'
    (tmp_path / 'bash').symlink_to(bash)
    return str(tmp_path)


def test_the_run_is_refused_when_a_required_interpreter_is_missing(only_bash: str):
    """Both marker spellings reach the same enforcement.

    tmux is required by a module-wide `pytestmark` and zsh by a single parameter
    of one, so naming both in the refusal is what proves the set is read off the
    collected items rather than off a list someone maintains.
    """
    result = run_pytest('tests/shell', '--collect-only', '--require-interpreters', path=only_bash)

    assert result.returncode != 0
    assert 'no tmux, zsh' in result.output


def test_a_missing_interpreter_is_only_a_skip_without_the_flag(only_bash: str):
    """The workstation reading, asserted on the tier that needs the missing binary."""
    result = run_pytest(TMUX_TIER, '-rs', path=only_bash)

    assert result.returncode == 0
    assert 'tmux is not installed' in result.output


def test_the_flag_is_satisfied_by_this_machine():
    """The positive case, which is what CI actually runs.

    A gate asserted only by its refusal would pass on a machine where it refuses
    unconditionally, and every CI run would then fail for a reason no test names.
    """
    result = run_pytest('tests/shell', '--collect-only', '--require-interpreters')

    assert result.returncode == 0, result.output
