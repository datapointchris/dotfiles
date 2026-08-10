"""Turning a run's events into the record `dotfiles report` reads.

`runs.py` was complete and tested for months with no caller, because everything
that wanted to know what a run found called the walk and printed on the way past.
Recording works now because it is one more reader of a stream that yields values.
"""

from __future__ import annotations

from pathlib import Path

from dotfiles import runs
from dotfiles import sinks
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Verdict

MACHINE = 'linux-lxc-server'


def change(item: str, verdict: Verdict = Verdict.MISSING) -> Change:
    return Change('packages', Stage.TOOLS, item, verdict)


def timing(seconds: float) -> runs.Timing:
    return runs.Timing(started_at='2026-08-09T00:00:00Z', duration_seconds=seconds)


def test_a_planned_change_is_recorded_with_its_verdict_and_no_action() -> None:
    """A plan decided something and did nothing, and the record has to be able to
    say which — otherwise a report cannot tell a dry run from a run that acted."""
    written = sinks.record([Event('packages', change('zk'))], MACHINE, 'plan')

    assert [(outcome.address, outcome.verdict, outcome.action) for outcome in written.outcomes] == [
        ('packages/zk', str(Verdict.MISSING), 'planned')
    ]


def test_an_outcome_is_recorded_with_what_was_done_to_it() -> None:
    performed = Outcome(change('zk'), OutcomeStatus.DONE, 'installed zk')
    written = sinks.record([Event('packages', performed)], MACHINE, 'apply')

    assert written.outcomes[0].action == str(OutcomeStatus.DONE)
    assert written.outcomes[0].address == 'packages/zk'


def test_a_refusal_is_an_issue_not_an_outcome() -> None:
    """The distinction the nudge fires on. An Issue is something wrong; a decision
    about an item is not, however unwelcome."""
    written = sinks.record([Event('packages', Refusal('pacman is not installed'))], MACHINE, 'check')

    assert written.outcomes == []
    assert [(issue.address, issue.kind) for issue in written.issues] == [('packages', 'refused')]


def test_the_resource_row_carries_what_measuring_cost() -> None:
    """An inventory is one query per manager, not one per package, so the time is
    the resource's. Splitting it across the items would be inventing a number."""
    written = sinks.record([Event('packages', Summary('all installed'), timing=timing(0.44))], MACHINE, 'plan')

    assert written.outcomes[0].address == 'packages'
    assert written.outcomes[0].timing.duration_seconds == 0.44


def test_an_untimed_decision_is_written_as_a_measured_zero() -> None:
    """`record_outcome` refuses an outcome with no timing on purpose — an untimed
    resource would drop out of every report that aggregates duration — so a
    decision the engine did not clock has to be a zero rather than absent."""
    written = sinks.record([Event('packages', change('zk'))], MACHINE, 'plan')

    assert written.outcomes[0].timing.duration_seconds == 0.0


def test_a_record_round_trips_through_the_file_it_is_written_to(tmp_path: Path) -> None:
    """The record crosses machines over Syncthing, so writing it and reading it
    back has to produce the same thing — including the nested timings."""
    written = sinks.record(
        [
            Event('packages', change('zk')),
            Event('packages', Summary('all installed'), timing=timing(0.44)),
            Event('symlinks', Refusal('could not be examined')),
        ],
        MACHINE,
        'plan',
    )

    destination = runs.write(written, runs_dir=tmp_path)

    assert runs.read(destination) == written
