"""A zero exit code is not evidence that a package arrived.

The install is stubbed and the inventory is real. That split is the point: the
subject is what `_transact` concludes when a manager reports success and its own
inventory disagrees, so the success is the premise and the disagreement is what
is under test. The harness refuses a real `yay -S` anyway, per `INSTALLING` in
tests/conftest.py, and a fake yay on PATH is still `yay -S` to that guard.

The inventory stays a real binary shadowed on PATH, because `pacman -Qq` output
is a manager's own convention and a mock would assert nothing about it.

`aur` is the manager under test because it shares pacman's inventory query while
being absent from `syspkg.ESCALATES`, so nothing here prompts for root.

The two cases that produced this, both exiting 0: `yay -S --needed` printing
"up to date -- skipping" for a name that resolves to no package at all, and
`brew install pkg-config` installing a formula renamed to `pkgconf`.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from dotfiles import registry
from dotfiles.privilege import Privilege
from dotfiles.providers import Result
from dotfiles.providers import syspkg
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict

ITEM = 'sioyek'
PACKAGE = 'sioyek-git'


def executable(directory: Path, name: str, script: str) -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def pacman_holding(fake_bin: Path, *names: str) -> None:
    """A pacman whose `-Qq` lists exactly `names`, and which fails anything else."""
    listing = ''.join(f'{name}\\n' for name in names)
    executable(fake_bin, 'pacman', f'#!/bin/sh\n[ "$1" = "-Qq" ] || exit 1\nprintf "{listing}"\n')


@pytest.fixture
def install_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A manager that reports success whatever it was asked to install."""
    monkeypatch.setattr(syspkg, 'install', lambda manager, names, privilege: Result(True, f'{manager}: {" ".join(names)}'))


def transact(privilege: Privilege) -> Outcome:
    change = Change('packages', Stage.TOOLS, ITEM, Verdict.MISSING, repair=Repair.AUTOMATIC)
    return registry._transact('aur', [(change, PACKAGE)], privilege)[ITEM]


@pytest.mark.usefixtures('install_succeeds')
def test_a_manager_that_exits_zero_and_installs_nothing_is_not_done(fake_bin: Path, unprivileged: Privilege) -> None:
    """The sioyek case. `aur: sioyek` named a package that had been deleted from
    the AUR, so every apply succeeded, every run reported converged, and the
    machine never had it. Nothing said so until three applies of run history had
    accumulated, which a container installing once can never reach.
    """
    pacman_holding(fake_bin, 'curl', 'git')

    assert transact(unprivileged).status is OutcomeStatus.ABSENT


@pytest.mark.usefixtures('install_succeeds')
def test_an_absent_install_is_not_ok_so_the_run_reports_it(fake_bin: Path, unprivileged: Privilege) -> None:
    """`ok` is what decides the tick and what `_unsuccessful` collects. An outcome
    that reads as success here is the original defect with a new name on it."""
    pacman_holding(fake_bin, 'curl')

    outcome = transact(unprivileged)

    assert not outcome.ok
    assert PACKAGE in outcome.message


@pytest.mark.usefixtures('install_succeeds')
def test_a_package_that_actually_arrived_is_still_done(fake_bin: Path, unprivileged: Privilege) -> None:
    """The control. Re-observing has to leave an ordinary install alone, or every
    apply reports failure."""
    pacman_holding(fake_bin, 'curl', PACKAGE)

    assert transact(unprivileged).status is OutcomeStatus.DONE


@pytest.mark.usefixtures('install_succeeds')
def test_a_manager_that_cannot_be_asked_stays_done(fake_bin: Path, unprivileged: Privilege) -> None:
    """Not verifying is the state this replaced, so it keeps that state's answer.

    Reporting ABSENT here would name a fault in the declaration on the strength of
    no evidence — the inventory query failed, which says nothing about the package.
    """
    executable(fake_bin, 'pacman', '#!/bin/sh\nexit 1\n')

    assert transact(unprivileged).status is OutcomeStatus.DONE
