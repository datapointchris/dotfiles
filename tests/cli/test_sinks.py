"""Turning a run's events into the record `dotfiles report` reads.

`runs.py` was complete and tested for months with no caller, because everything
that wanted to know what a run found called the walk and printed on the way past.
Recording works now because it is one more reader of a stream that yields values.
"""

from __future__ import annotations

import datetime as dt
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
BEGAN = dt.datetime(2026, 8, 9, 0, 0, 0, tzinfo=dt.UTC)


def change(item: str, verdict: Verdict = Verdict.MISSING) -> Change:
    return Change('packages', Stage.TOOLS, item, verdict)


def timing(seconds: float) -> runs.Timing:
    return runs.Timing(started_at='2026-08-09T00:00:00Z', duration_seconds=seconds)


def test_a_planned_change_is_recorded_with_its_verdict_and_no_action() -> None:
    """A plan decided something and did nothing, and the record has to be able to
    say which — otherwise a report cannot tell a dry run from a run that acted."""
    written = sinks.record([Event('packages', change('zk'))], MACHINE, 'plan', BEGAN)

    assert [(outcome.address, outcome.verdict, outcome.action) for outcome in written.outcomes] == [
        ('packages/zk', str(Verdict.MISSING), 'planned')
    ]


def test_an_outcome_is_recorded_with_what_was_done_to_it() -> None:
    performed = Outcome(change('zk'), OutcomeStatus.DONE, 'installed zk')
    written = sinks.record([Event('packages', performed)], MACHINE, 'apply', BEGAN)

    assert written.outcomes[0].action == str(OutcomeStatus.DONE)
    assert written.outcomes[0].address == 'packages/zk'


def test_why_an_item_failed_is_carried_onto_the_record() -> None:
    """`apply` points a failed run at the record, and a record that kept the
    status but dropped the reason sends the reader back to the machine — which is
    the one thing an uploaded record cannot do."""
    failed = Outcome(change('win32yank'), OutcomeStatus.FAILED, 'checksum mismatch')
    written = sinks.record([Event('packages', failed)], MACHINE, 'apply', BEGAN)

    assert written.outcomes[0].message == 'checksum mismatch'


def test_keeping_a_record_hands_back_where_it_landed(tmp_path: Path, monkeypatch) -> None:
    """The verb prints the path, so `keep` has to say what it wrote rather than
    leaving the caller to name a command that would go and find out."""
    monkeypatch.setattr('dotfiles.paths.RUNS_DIR', tmp_path / 'runs')
    written = sinks.keep([Event('packages', change('zk'))], MACHINE, 'plan', BEGAN)

    assert written is not None
    assert written.exists()


def test_a_record_that_cannot_be_written_says_so_without_failing_the_run(tmp_path: Path, monkeypatch) -> None:
    """`$XDG_STATE_HOME` is absent on a fresh machine, and that is not a reason for
    a verb to exit non-zero on a question it answered."""
    monkeypatch.setattr('dotfiles.paths.RUNS_DIR', tmp_path / 'runs')
    monkeypatch.setattr('dotfiles.runs.write', _refuse)

    assert sinks.keep([Event('packages', change('zk'))], MACHINE, 'plan', BEGAN) is None


def _refuse(*_args, **_kwargs):
    raise OSError('read-only file system')


def test_a_refusal_is_an_issue_not_an_outcome() -> None:
    """The distinction the nudge fires on. An Issue is something wrong; a decision
    about an item is not, however unwelcome."""
    written = sinks.record([Event('packages', Refusal('pacman is not installed'))], MACHINE, 'check', BEGAN)

    assert written.outcomes == []
    assert [(issue.address, issue.kind) for issue in written.issues] == [('packages', 'refused')]


def test_the_resource_row_carries_what_measuring_cost() -> None:
    """An inventory is one query per manager, not one per package, so the time is
    the resource's. Splitting it across the items would be inventing a number."""
    written = sinks.record([Event('packages', Summary('all installed'), timing=timing(0.44))], MACHINE, 'plan', BEGAN)

    assert written.outcomes[0].address == 'packages'
    assert written.outcomes[0].timing.duration_seconds == 0.44


def test_an_untimed_decision_is_written_as_a_measured_zero() -> None:
    """`record_outcome` refuses an outcome with no timing on purpose — an untimed
    resource would drop out of every report that aggregates duration — so a
    decision the engine did not clock has to be a zero rather than absent."""
    written = sinks.record([Event('packages', change('zk'))], MACHINE, 'plan', BEGAN)

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
        BEGAN,
    )

    destination = runs.write(written, runs_dir=tmp_path)

    assert runs.read(destination) == written
