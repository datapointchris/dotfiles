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

**The report is the run record**, which is why every assertion below reads a
field rather than grepping the console. A record carries what was decided,
attempted and refused for each address; console text carries a sentence, and a
test pinned to one fails when the sentence is reworded and nothing is wrong.
"""

from __future__ import annotations

import pytest
from harness import Machine
from harness import failed_outcomes
from harness import run_record

pytestmark = pytest.mark.docker


@pytest.fixture(scope='session')
def restricted(machine: Machine) -> Machine:
    if machine.environment.name != 'restricted':
        pytest.skip('only the firewalled, bundle-less environment produces real failures')
    return machine


@pytest.fixture(scope='session')
def record(restricted: Machine) -> dict:
    """What the install wrote about itself, read back off the machine.

    Read rather than reconstructed from the console: the scroll is gone by the
    time anyone asks, which is the whole reason a record exists.
    """
    return run_record(restricted)


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


def test_the_record_is_the_apply_that_just_ran(record: dict) -> None:
    """`apply` recorded nothing until the phase registry went, so a failed install
    left the one durable account of itself to a text file in `/tmp`."""
    assert record['verb'] == 'apply'
    assert record['outcomes'], 'a run that installed a machine recorded no outcomes'


def test_every_failure_reached_the_record(restricted: Machine, record: dict) -> None:
    """More than one thing fails behind this firewall, and the record is the only
    place a person sees them after the scroll is gone."""
    failed = failed_outcomes(restricted)
    assert len(failed) > 1, [outcome['address'] for outcome in record['outcomes']][:40]


def test_the_record_the_run_pointed_at_is_the_one_that_exists(restricted: Machine) -> None:
    """The run's last words name where to read the rest, and a pointer to a file
    that is not there is worse than no pointer.

    The command rather than the sentence around it: `report latest` is a public
    verb this asserts still answers, where grepping the summary would pin a
    wording the code is free to change.
    """
    assert restricted.succeeds('cd ~/dotfiles && uv run dotfiles report latest')


def test_a_failure_is_not_silently_converged(restricted: Machine) -> None:
    """The defect this whole tier exists for: an install exiting 0 whatever failed
    lets `install && next-thing` chain straight past a broken machine. The status
    is `apply`'s, since the bootstrap hands over rather than running it — a failed
    stage has to reach the caller."""
    assert restricted.install_status != 0
