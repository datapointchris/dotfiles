"""Turning a run's events into the record `dotfiles report` reads.

Recording works because it is one more reader of a stream that yields values. A
reader that called the walk and printed on the way past would leave `runs.py`
with nothing to record.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from dotfiles import logging as log
from dotfiles import runs
from dotfiles import sinks
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.plan import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.results import ResourceVerdict

MACHINE = 'linux-lxc-server'
BEGAN = dt.datetime(2026, 8, 9, 0, 0, 0, tzinfo=dt.UTC)


def identity(verb: str = 'plan') -> runs.Identity:
    return runs.Identity(id='abc123abc123', machine=MACHINE, verb=verb, started=BEGAN)


def change(item: str, verdict: Verdict = Verdict.MISSING) -> Change:
    return Change('packages', Stage.TOOLS, item, verdict, repair=Repair.AUTOMATIC)


def by_hand(item: str, resource: str = 'env') -> Change:
    """An item that differs and only a person can repair — an unset value, a file
    safekeep restores. `BY_HAND` refuses to construct without advice, which is why
    this is a helper rather than a literal at each site."""
    return Change(resource, Stage.ENVIRONMENT, item, Verdict.MISSING, repair=Repair.BY_HAND, advice=f'set {item}')


def unmeasurable(item: str) -> Change:
    """Nothing could establish anything either way. The pair is the definition:
    `repair_for` answers `NONE` for `UNKNOWN`, so a verdict without it is a second
    opinion that happens to agree."""
    return Change('packages', Stage.TOOLS, item, Verdict.UNKNOWN, repair=Repair.NONE)


def timing(seconds: float) -> runs.Timing:
    return runs.Timing(started_at='2026-08-09T00:00:00Z', duration_seconds=seconds)


def test_a_planned_change_is_recorded_with_its_verdict_and_no_action() -> None:
    """A plan decided something and did nothing, and the record has to be able to
    say which — otherwise a report cannot tell a dry run from a run that acted."""
    written = sinks.record([Event('packages', change('zk'))], identity('plan'))

    assert [(outcome.address, outcome.verdict, outcome.action) for outcome in written.outcomes] == [
        ('packages/zk', str(Verdict.MISSING), 'planned')
    ]


def test_an_outcome_is_recorded_with_what_was_done_to_it() -> None:
    performed = Outcome(change('zk'), OutcomeStatus.DONE, 'installed zk')
    written = sinks.record([Event('packages', performed)], identity('apply'))

    assert written.outcomes[0].action == str(OutcomeStatus.DONE)
    assert written.outcomes[0].address == 'packages/zk'


def test_why_an_item_failed_is_carried_onto_the_record() -> None:
    """`apply` points a failed run at the record, and a record that kept the
    status but dropped the reason sends the reader back to the machine — which is
    the one thing an uploaded record cannot do."""
    failed = Outcome(change('win32yank'), OutcomeStatus.FAILED, 'checksum mismatch')
    written = sinks.record([Event('packages', failed)], identity('apply'))

    assert written.outcomes[0].message == 'checksum mismatch'


def test_keeping_a_record_hands_back_where_it_landed(runs_dir: Path) -> None:
    """The verb prints the path, so `keep` has to say what it wrote rather than
    leaving the caller to name a command that would go and find out."""
    written = sinks.keep([Event('packages', change('zk'))], identity('plan'))

    assert written is not None
    assert written.exists()


def test_a_record_that_cannot_be_written_says_so_without_failing_the_run(runs_dir: Path, monkeypatch) -> None:
    """`$XDG_STATE_HOME` is absent on a fresh machine, and that is not a reason for
    a verb to exit non-zero on a question it answered."""
    monkeypatch.setattr('dotfiles.runs.write', _refuse)

    assert sinks.keep([Event('packages', change('zk'))], identity('plan')) is None


def _refuse(*_args, **_kwargs):
    raise OSError('read-only file system')


def test_the_log_and_the_record_are_one_run_under_two_extensions(runs_dir: Path) -> None:
    """Opened at the start, written at the end, and they have to meet. Nothing
    reconciles them afterwards — an id minted at either end would file half a run
    under a name the other half never used."""
    who = identity('apply')

    sinks.open_log(who)
    log.get_logger('test').debug('something happened')
    written = sinks.keep([Event('packages', change('zk'))], who)

    assert written is not None
    assert written.with_suffix('.jsonl').exists()
    assert json.loads(written.read_text())['id'] == who.id
    assert json.loads(written.with_suffix('.jsonl').read_text().splitlines()[0])['run_id'] == who.id


def test_a_log_that_cannot_be_opened_leaves_the_console_working(runs_dir: Path, monkeypatch) -> None:
    """`$XDG_STATE_HOME` is absent on a fresh machine and read-only in more
    containers than it should be. Neither is a reason for a verb to fail a
    question it can answer, which is the same rule `keep` holds at the other end."""
    monkeypatch.setattr('dotfiles.logging.configure', _refuse_once())

    sinks.open_log(identity('check'))


def _refuse_once():
    """An OSError on the call that names a file, and success on the fallback."""
    original = log.configure

    def guarded(event_log=None):
        if event_log is not None:
            raise OSError('read-only file system')
        original()

    return guarded


def test_a_refusal_is_an_issue_not_an_outcome() -> None:
    """The distinction the exit code carries. An Issue is something wrong; a
    decision about an item is not, however unwelcome."""
    written = sinks.record([Event('packages', Refusal('pacman is not installed'))], identity('check'))

    assert written.outcomes == []
    assert [(issue.address, issue.kind) for issue in written.issues] == [('packages', 'refused')]


def test_the_resource_row_carries_what_measuring_cost() -> None:
    """An inventory is one query per manager, not one per package, so the time is
    the resource's. Splitting it across the items would be inventing a number."""
    written = sinks.record([Event('packages', Summary('all installed'), timing=timing(0.44))], identity('plan'))

    assert written.outcomes[0].address == 'packages'
    assert written.outcomes[0].timing.duration_seconds == 0.44


def test_an_untimed_decision_is_written_as_a_measured_zero() -> None:
    """`record_outcome` refuses an outcome with no timing on purpose — an untimed
    resource would drop out of every report that aggregates duration — so a
    decision the engine did not clock has to be a zero rather than absent."""
    written = sinks.record([Event('packages', change('zk'))], identity('plan'))

    assert written.outcomes[0].timing.duration_seconds == 0.0


def test_a_record_round_trips_through_the_file_it_is_written_to(tmp_path: Path) -> None:
    """The record crosses machines by replication, so writing it and reading it
    back has to produce the same thing — including the nested timings."""
    written = sinks.record(
        [
            Event('packages', change('zk')),
            Event('packages', Summary('all installed'), timing=timing(0.44)),
            Event('symlinks', Refusal('could not be examined')),
        ],
        identity('plan'),
    )

    destination = runs.write(written, runs_dir=tmp_path)

    assert runs.read(destination) == written


class TestVerdict:
    """What one run found, graded from the record the writer actually emits.

    Built through `sinks.record` rather than by hand, because the verdict reads
    `action` and `sinks` is the only thing that writes one. A record assembled in
    a test agrees with whatever the test typed, which is how a fold that was false
    on every real record passed the suite.
    """

    def test_a_run_that_found_nothing_is_converged(self) -> None:
        written = sinks.record([Event('packages', Summary('all installed'), timing=timing(0.4))], identity('check'))

        assert written.verdict is ResourceVerdict.CONVERGED

    def test_the_resource_row_alone_does_not_make_a_run_unconverged(self) -> None:
        """`examined` is not a `Verdict` member, and every record carries one row
        of it per resource. Read as an item verdict it made `converged` false on
        every run the fleet has ever recorded."""
        written = sinks.record(
            [Event(name, Summary('nothing to do'), timing=timing(0.1)) for name in ('packages', 'symlinks', 'env')],
            identity('check'),
        )

        assert [outcome.verdict for outcome in written.outcomes] == [runs.EXAMINED] * 3
        assert written.converged

    def test_an_item_apply_would_repair_is_drift(self) -> None:
        written = sinks.record([Event('packages', change('zk'))], identity('plan'))

        assert written.verdict is ResourceVerdict.DRIFT

    def test_an_item_apply_repaired_is_still_drift(self) -> None:
        """The verdict says what the run found, never what it left behind. An
        apply that fixed two things found a machine that differed."""
        written = sinks.record([Event('packages', Outcome(change('zk'), OutcomeStatus.DONE, 'installed zk'))], identity('apply'))

        assert written.verdict is ResourceVerdict.DRIFT

    def test_an_item_only_a_person_can_repair_is_an_issue(self) -> None:
        """The case the whole fold exists for: three unset values made
        `status-<box>.json` say `issue` while the run record said `ok`, and
        `doit dashboard` reads the record."""
        written = sinks.record([Event('env', by_hand('FRESHRSS_URL'))], identity('check'))

        assert written.outcomes[0].action == str(runs.Intention.DECLINED)
        assert written.verdict is ResourceVerdict.ISSUE

    def test_a_failed_write_is_an_issue(self) -> None:
        failed = Outcome(change('zk'), OutcomeStatus.FAILED, 'pacman exited 1')

        written = sinks.record([Event('packages', failed)], identity('apply'))

        assert written.verdict is ResourceVerdict.ISSUE

    def test_a_refused_resource_is_an_issue(self) -> None:
        written = sinks.record([Event('packages', Refusal('pacman is not installed'))], identity('check'))

        assert written.verdict is ResourceVerdict.ISSUE

    def test_something_unmeasurable_moves_no_verdict(self) -> None:
        """A cold release cache makes every declared release unmeasurable at once,
        and calling that drift reports a screen of faults on a healthy machine."""
        written = sinks.record([Event('packages', unmeasurable('zk'))], identity('check'))

        assert written.outcomes[0].action == str(runs.Intention.UNMEASURED)
        assert written.verdict is ResourceVerdict.CONVERGED

    def test_an_issue_outranks_the_drift_beside_it(self) -> None:
        """`reconcile.worst` grades a whole machine the same way, and the two folds
        answer about one walk — so a run carrying both kinds cannot report drift
        here and issue there."""
        written = sinks.record([Event('packages', change('zk')), Event('env', by_hand('FRESHRSS_URL'))], identity('check'))

        assert written.verdict is ResourceVerdict.ISSUE


def test_every_action_a_run_writes_is_a_named_intention_or_outcome() -> None:
    """`action` carries two vocabularies and every reader compares against both.

    A third spelling reaching the field is invisible: it is a string, it
    serializes, it renders in the table, and it silently matches no set — which is
    how a resource row's `examined` came to be read as an item verdict.
    """
    named = {str(word) for word in runs.Intention} | {str(status) for status in OutcomeStatus}

    written = sinks.record(
        [
            Event('packages', change('zk')),
            Event('packages', unmeasurable('fd')),
            Event('packages', by_hand('yq')),
            Event('packages', Outcome(change('zk'), OutcomeStatus.DONE, 'installed zk')),
            Event('packages', Summary('all installed'), timing=timing(0.4)),
        ],
        identity('apply'),
    )

    assert {outcome.action for outcome in written.outcomes} <= named
    assert len(written.outcomes) == 5
