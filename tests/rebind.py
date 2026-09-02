"""Re-run what `paths` derived at import, from the variables as they stand now.

`paths` reads `$DOTFILES_DIR`, `$XDG_STATE_HOME` and the hostname once, in the
module body, and every path below them is a constant by the time a test runs. So
a test that sets one of those variables changes nothing, and the two ways out are
to re-run the derivation or to write the answer down. Writing it down is what
this exists to stop: `tests/cli/test_status.py` derived `status-box.json` where
the module derives `status-{MACHINE_ID}.json`, and the two agreed only because no
test asked the module.

Nothing here invents a value. `_repo_root`, `xdg_home` and `machine_id` are the
module's own calls, so `$DOTFILES_DIR`, `$XDG_STATE_HOME` and the hostname stay
what decide, and a change to any of the three reaches every caller with no edit
here.

**The eleven expressions below them are restated, and cannot be otherwise.** They
are module-level, so there is no function to call a second time — `RUNS_DIR` is
the text `STATE_HOME / 'runs'` and nothing more. A test therefore still cannot
see a change to one of those, which is a limit of this file rather than something
a caller can work around. It is also the sharpest argument for finding #4: the
restatement exists only because the value was bound at import.

A module rather than a fixture in `tests/conftest.py`, because `tests/` is on
`pythonpath` and `conftest` is not importable by name — `tests/conftest.py` and
`tests/e2e/conftest.py` are both `conftest` to an importer, and a
`from conftest import ...` resolves to whichever landed in `sys.modules` first.

This is what finding #4 removes. Once `paths` is all functions there is nothing
derived at import, a variable set by a test is read on the next call, and the
whole file deletes.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

from dotfiles import paths

if TYPE_CHECKING:
    import pytest


def hostname(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Answer `socket.gethostname` with `name`, and re-derive what reads it.

    The hostname rather than `paths.MACHINE_ID`, so `machine_id()` runs: it strips
    the domain and lowercases, and a test pinning the constant skips both. A name
    is needed at all because `LATEST_RUN` and `STATUS_FILE` carry it, and a shared
    `runs/` directory makes "the newest record" depend on which box ran last —
    which is the answer a suite must not take from the machine it happens to be on.
    """
    monkeypatch.setattr(socket, 'gethostname', lambda: name)
    derive(monkeypatch)


def derive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every constant `paths` computed at import, computed again from the world as it stands."""
    repo = paths._repo_root()  # noqa: SLF001 — the module's own derivation, re-run rather than reimplemented
    state = paths.xdg_home('XDG_STATE_HOME', '.local/state') / 'dotfiles'
    machine = paths.machine_id()

    derived = {
        'REPO_ROOT': repo,
        'PYPROJECT_FILE': repo / 'pyproject.toml',
        'INSTALL_DIR': repo / 'install',
        'PACKAGES_FILE': repo / 'install' / 'packages.yml',
        'MANIFESTS_DIR': repo / 'install' / 'manifests',
        'FLAGS_FILE': repo / 'install' / 'flags.yml',
        'STATE_HOME': state,
        'RUNS_DIR': state / 'runs',
        'MACHINE_ID': machine,
        'LATEST_RUN': state / f'latest-{machine}',
        'STATUS_FILE': state / f'status-{machine}.json',
    }
    for name, value in derived.items():
        monkeypatch.setattr(paths, name, value)
