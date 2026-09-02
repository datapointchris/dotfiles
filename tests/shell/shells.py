"""Running the shell libraries the way their callers do.

`configs/common/.local/shell/` is deployed to `~/.local/shell/` and sourced by
`.zshrc`, by every script in `apps/`, and by what is left of `install/`. The
subject is bash — and zsh, for the one property that has to agree across both —
so a real shell still runs the code; only the runner changed, from bats to
pytest.

Each call gets a fresh interpreter because every library here resolves something
at source time. The color palette is the clearest case: it is decided once, when
the file is sourced, so a long-lived shell would answer every later test with
whatever the first one decided.

A plain module rather than a `conftest.py`, because there is nothing to inject
and `tests/conftest.py` already carries the warning: two conftests are both the
module `conftest` to an importer, so `from conftest import ...` resolves to
whichever one the tool looked at first.
"""

from __future__ import annotations

import dataclasses as dc
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SHELL_DIR = REPO / 'configs' / 'common' / '.local' / 'shell'

COLOR_KNOBS = ('NO_COLOR', 'FORCE_COLOR', 'TERM')
"""Scrubbed from every run unless a test names one, so the developer's own
terminal cannot decide the answer."""

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def requires(interpreter: str) -> pytest.MarkDecorator:
    """Declare that a test drives an interpreter no machine is guaranteed to have.

    Deliberately not a `skipif` resolved here. Whether a missing interpreter is a
    skip or a hard failure is the *runner's* question — a workstation without zsh
    should report a skip, and CI must not report green having silently run a third
    of this directory. `tests/conftest.py` decides, and the set it enforces is the
    set these markers ask for, so a tier that starts driving a third interpreter
    extends the CI gate by existing rather than by someone editing a workflow.

    bash needs no marker: a missing one raises FileNotFoundError out of every
    call, which is a failure already and cannot be mistaken for coverage.
    """
    return pytest.mark.interpreter(interpreter)


SHELLS = ('bash', pytest.param('zsh', marks=requires('zsh')))
"""A parameter rather than an inline skip, so a machine without zsh reports the
skip per case instead of silently covering half of one."""


@dc.dataclass(frozen=True, slots=True)
class Shell:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def plain(self) -> str:
        """stdout with the escapes removed, which is how alignment is asserted."""
        return ANSI.sub('', self.stdout)


def library_path(library: str) -> Path:
    """A bare filename means the shell library directory; anything with a slash is
    relative to the repo root, which is how the `install/` libraries are named."""
    return REPO / library if '/' in library else SHELL_DIR / library


def shell_out(snippet: str, *args: str, shell: str = 'bash', **environment: str) -> Shell:
    """Run `snippet` in a fresh shell, with `args` as its positional parameters.

    stdout and stderr stay apart. bats merged them into one `$output`, which is
    how logging.sh's stderr routing regressed unnoticed: an assertion on the
    merged stream passes whichever stream the code chose.
    """
    env = {key: value for key, value in os.environ.items() if key not in COLOR_KNOBS}
    # formatting.sh prefers $SHELL_DIR over its own location when it looks for
    # colors.sh, and `.zshrc` exports it — so without this, a test run from a
    # normal shell would read the *deployed* copy under ~/.local/shell and pass
    # while the repo's copy was broken.
    env['SHELL_DIR'] = str(SHELL_DIR)
    env.update(environment)

    completed = subprocess.run(
        [shell, '-c', snippet, '_', *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return Shell(completed.stdout, completed.stderr, completed.returncode)


def source(library: str, snippet: str, *, shell: str = 'bash', **environment: str) -> Shell:
    """Run `snippet` in a fresh shell with one library already sourced."""
    return shell_out(f'source "$1"; {snippet}', str(library_path(library)), shell=shell, **environment)
