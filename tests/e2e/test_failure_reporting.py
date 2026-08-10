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

**The report is the run record now**, not a text file in `/tmp`. The log this
asserted against was written by the phase layer, which returned booleans and had
no per-item value to keep — so it held one line per failed tool and nothing about
what was decided, attempted or refused. `apply` records what every other verb
records, and `dotfiles report latest` is where a person reads it.
"""

from __future__ import annotations

import json

import pytest
from harness import Machine

pytestmark = pytest.mark.docker

LATEST_RECORD = '${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles/latest'
"""`paths.LATEST_RUN`, spelled for a shell because this reads it inside the
container. `runs.write` points it at the record it just wrote."""


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
    written = restricted.read(f'cat {LATEST_RECORD}')
    assert written.strip(), f'the install wrote no run record at {LATEST_RECORD}'
    return json.loads(written)


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


def test_every_failure_reached_the_record(record: dict) -> None:
    """More than one thing fails behind this firewall, and the record is the only
    place a person sees them after the scroll is gone."""
    failed = [outcome for outcome in record['outcomes'] if outcome['action'] == 'failed']
    assert len(failed) > 1, [outcome['address'] for outcome in record['outcomes']][:40]


def test_the_summary_names_what_did_not_converge(restricted: Machine) -> None:
    """The run's last words have to carry both the count and where to read the
    rest, or the record is a file nobody knows to open."""
    assert 'did not converge' in restricted.install_log
    assert 'dotfiles report latest' in restricted.install_log


def test_a_failure_is_not_silently_converged(restricted: Machine) -> None:
    """The defect this whole tier exists for: `install.sh` used to exit 0 no
    matter what failed, so `install.sh && next-thing` chained straight past a
    broken machine."""
    assert restricted.install_status != 0
