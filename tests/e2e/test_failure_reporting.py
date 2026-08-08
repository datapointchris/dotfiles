"""What a run does when things genuinely fail.

The `restricted` environment is firewalled and carries no bundle, so the tools
that come from release assets really cannot be fetched. That is the point: the
failure machinery is the only thing here under test, and it needs real failures
to report. Every other environment is arranged so that nothing fails, which makes
all of them useless for this.

The properties are the ones the reporting was built for. Each was a real defect
first: a run that stopped at the first failure and left the machine half
installed; a failure log per installer, so the summary named one of six; a
summary printed only when nothing had gone wrong.
"""

from __future__ import annotations

import pytest
from harness import Machine

pytestmark = pytest.mark.docker

FAILURE_LOGS = 'ls /tmp/dotfiles-install-failures-*.txt 2>/dev/null'


@pytest.fixture(scope='session')
def restricted(machine: Machine) -> Machine:
    if machine.environment.name != 'restricted':
        pytest.skip('only the firewalled, bundle-less environment produces real failures')
    return machine


def test_the_firewall_actually_broke_something(restricted: Machine) -> None:
    """Guard on the premise: every assertion below is vacuous on a run where
    nothing failed, and a green suite would then mean nothing at all."""
    assert restricted.install_status == 3, 'nothing failed, so the reporting is untested'


def test_the_run_continued_past_its_failures(restricted: Machine) -> None:
    """Stopping at the first one leaves a machine half installed and hides every
    other problem behind it — so the apt packages, which need no GitHub, must be
    there even though the release downloads could not be."""
    assert restricted.succeeds('command -v gcc'), 'build-essential never installed, so the run stopped early'
    assert restricted.succeeds('command -v zsh')


def test_there_is_exactly_one_failure_log(restricted: Machine) -> None:
    """One per installer is how a summary came to name one failure out of six."""
    logs = restricted.read(f'{FAILURE_LOGS} || true').split()
    assert len(logs) == 1, f'expected one failure log, found {logs}'


def test_every_failure_reached_that_log(restricted: Machine) -> None:
    """More than one thing fails behind this firewall, and the log is the only
    place a person sees them after the scroll is gone."""
    contents = restricted.read(f'cat $({FAILURE_LOGS} | head -1)')
    assert contents.count('Installation Failed') > 1, contents[-2000:]


def test_the_summary_names_the_phases_and_the_log(restricted: Machine) -> None:
    """The run's last words have to carry both, or the log is a file nobody knows
    to open."""
    assert 'phases reported a failure' in restricted.install_log
    assert 'dotfiles-install-failures-' in restricted.install_log


def test_a_failure_is_not_silently_converged(restricted: Machine) -> None:
    """The defect this whole tier exists for: `install.sh` used to exit 0 no
    matter what failed, so `install.sh && next-thing` chained straight past a
    broken machine."""
    assert restricted.install_status != 0
