"""The suite measures the checkout it lives in, whatever `$DOTFILES_DIR` says.

`tests/conftest.py` assigns `DOTFILES_DIR` the test tree's own root, and asserts
first that nothing has imported `dotfiles.paths` — which resolves `REPO_ROOT` once,
at import. Both lines are the pin, and each is useless without the other.

Every declaration a test reads without naming a path resolves through that root.
`catalog.load` falls back to `paths.PACKAGES_FILE` and `machine.load` to
`paths.INSTALL_DIR`, and both are built from `REPO_ROOT`. Dozens of call sites take
those defaults, so the pin is what makes a bare load name the branch under test.

`.zshenv` exports `DOTFILES_DIR` to the primary checkout on every machine here. A
run from a worktree that took that value would read what the primary checkout
declares while the branch under test sat unread.

`tests/shell/test_repo_root.py` is the same question asked of the shell scripts,
which resolve the checkout themselves rather than through a pin.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotfiles import catalog
from dotfiles import paths

REPO = Path(__file__).resolve().parent.parent

DECOY_MESSAGE = 'a bare load read a declaration this checkout does not carry'
ORDER_MESSAGE = 'something above imported dotfiles.paths'
"""What `tests/conftest.py` says when its assert fires, matched rather than restated:
a run that fails for some other reason prints neither."""


def test_the_suite_measures_the_checkout_it_lives_in() -> None:
    assert catalog.load().section('system_packages'), DECOY_MESSAGE
    assert paths.REPO_ROOT == REPO


PINNED = test_the_suite_measures_the_checkout_it_lives_in.__name__
"""Read off the function so a rename cannot leave the two halves asserting
different things. The subprocesses below run this same test by node id."""


def decoy_checkout(root: Path) -> Path:
    """A checkout declaring nothing, which is what makes an unpinned run silent.

    `catalog.load` parses this and answers with an empty `system_packages`, so a
    child that resolved here reports on a declaration the branch never wrote rather
    than dying on a missing file.
    """
    decoy = root / 'decoy'
    (decoy / 'install').mkdir(parents=True)
    (decoy / paths.REPO_MARKER).write_text('system_packages: []\n')
    return decoy


def run_pinned_case(decoy: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """The pinned test, run again in a child that `$DOTFILES_DIR` points elsewhere.

    A subprocess rather than a monkeypatch: `paths.REPO_ROOT` resolves once at
    import and the pin runs before that, so neither is reachable from a test that
    is already running.
    """
    return subprocess.run(
        [sys.executable, '-m', 'pytest', f'{__file__}::{PINNED}', '-q', '-p', 'no:cacheprovider', *arguments],
        cwd=REPO,
        env={**os.environ, 'DOTFILES_DIR': str(decoy)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_shell_pointed_at_another_checkout_does_not_move_the_suite(tmp_path: Path) -> None:
    """The assignment half of the pin, proved against a decoy it should ignore.

    `'1 passed'` rather than the exit code, which a child that collected nothing or
    skipped the case also returns. That is reachable rather than hypothetical:
    `tests/conftest.py` adds `pytest.mark.skip` from `pytest_collection_modifyitems`
    for every opt-in tier and every missing interpreter.
    """
    ran = run_pinned_case(decoy_checkout(tmp_path))

    assert '1 passed' in ran.stdout, ran.stdout + ran.stderr


def test_resolving_the_root_before_the_pin_runs_is_refused(tmp_path: Path) -> None:
    """The assert half, which the case above passes without.

    `-p dotfiles.paths` imports the module as a plugin, and pytest loads plugins
    before conftest — the one way in reach to arrive at `tests/conftest.py` with the
    root already resolved. Without the assert the child fails later and differently,
    or passes outright where `$DOTFILES_DIR` is unset, so the message is what
    separates this from any other red.
    """
    ran = run_pinned_case(decoy_checkout(tmp_path), '-p', 'dotfiles.paths')

    assert ran.returncode != 0, ran.stdout + ran.stderr
    assert ORDER_MESSAGE in ran.stdout + ran.stderr
