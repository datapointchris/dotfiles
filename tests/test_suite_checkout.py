"""The suite measures the checkout it lives in, whatever `$DOTFILES_DIR` says.

`tests/conftest.py` pins `DOTFILES_DIR` to this tree before anything imports
`dotfiles.paths`, which resolves the root once at import. Every declaration a test
reads without naming a path resolves through that root. `catalog.load` falls back to
`paths.PACKAGES_FILE` and `machine.load` to `paths.INSTALL_DIR`, and both of those
are built from `REPO_ROOT`. Dozens of call sites take those defaults. The two
signatures are where that is checkable — an `rg` for the bare calls would count this
docstring among them.

So the pin is what makes a bare load correct, rather than a second belt over one.
`.zshenv` exports `DOTFILES_DIR` to the primary checkout on every machine here, and
a run from a worktree without the pin reads what `main` declares while the branch
under test sits unread — green against a file the change never touched.

Until this file the pin was a comment and an import-order assert, and neither runs.

`tests/shell/test_repo_root.py` is the same question asked of the shell scripts,
which resolve the checkout themselves rather than through a pin.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotfiles import paths

REPO = Path(__file__).resolve().parent.parent

PINNED = 'test_the_suite_measures_the_checkout_it_lives_in'
"""Named rather than spelled twice: the subprocess below runs this same test, so
the two halves cannot drift into asserting different things."""


def test_the_suite_measures_the_checkout_it_lives_in() -> None:
    assert paths.REPO_ROOT == REPO


def test_a_shell_pointed_at_another_checkout_does_not_move_the_suite(tmp_path: Path) -> None:
    """The pin beats an inherited `$DOTFILES_DIR`, proved by handing it a decoy.

    A subprocess rather than a monkeypatch, because `paths.REPO_ROOT` is resolved
    once at import and the pin runs before that — neither is reachable from a test
    that is already running.

    The decoy carries the repo marker, so an unpinned run does not fail on a missing
    file. It reads the decoy's declaration and reports on it, which is the silent
    direction and the one worth catching.
    """
    decoy = tmp_path / 'decoy'
    (decoy / 'install').mkdir(parents=True)
    (decoy / paths.REPO_MARKER).write_text('system_packages: []\n')

    ran = subprocess.run(
        [sys.executable, '-m', 'pytest', f'{__file__}::{PINNED}', '-q', '-p', 'no:cacheprovider'],
        cwd=REPO,
        env={**os.environ, 'DOTFILES_DIR': str(decoy)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert ran.returncode == 0, ran.stdout + ran.stderr
