"""The run record survives being written and read back.

Every field a report verb will read has to round-trip, because a record that
loses one is only discovered by the report that needed it, long after the run it
described. These land before anything writes records so the format is settled
while it is still free to change.
"""

import datetime as dt
import json

import pytest

from dotfiles import paths
from dotfiles import runs
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Verdict


@pytest.fixture
def runs_dir(tmp_path):
    directory = tmp_path / 'state' / 'runs'
    directory.mkdir(parents=True)
    return directory


def timed(**phases) -> runs.Timing:
    stopwatch = runs.Stopwatch()
    for name in phases:
        with stopwatch.phase(name):
            pass
    return stopwatch.finish()


def a_run(machine='macos-personal-workstation', verb='apply') -> runs.RunRecord:
    """Verdicts and actions spelled by the enums the writer serialises, never by
    hand. `converged` compared against a hand-typed `'MATCHED'` for its whole life
    and was therefore never true, and this fixture typing the same word is the
    reason no test noticed."""
    record = runs.start(runs.begin(machine, verb), flags={'skip': ['system']})
    record.record_outcome('packages/github/fzf', str(Verdict.STALE), str(OutcomeStatus.DONE), timed(observe=1, fetch=1, act=1))
    record.record_outcome('symlinks/common', str(Verdict.MATCHED), 'planned', timed(observe=1))
    record.record_issue('packages/github/yq', 'checksum', 'no checksum published')
    return runs.finish(record)


class TestRoundTrip:
    def test_every_field_survives_being_written_and_read(self, runs_dir):
        written = a_run()
        recovered = runs.read(runs.write(written, runs_dir))

        assert recovered == written

    def test_the_record_is_plain_json_anything_can_read(self, runs_dir):
        path = runs.write(a_run(), runs_dir)
        payload = json.loads(path.read_text())

        assert payload['schema'] == runs.SCHEMA
        assert payload['outcomes'][0]['timing']['phases']['fetch'] >= 0

    def test_every_outcome_carries_a_phase_breakdown(self, runs_dir):
        """A resource that lands untimed drops silently out of every duration
        report, so the record is the place to catch it."""
        recovered = runs.read(runs.write(a_run(), runs_dir))

        for outcome in recovered.outcomes:
            assert outcome.timing.started_at
            assert outcome.timing.phases, f'{outcome.address} recorded no phases'
            assert set(outcome.timing.phases) <= set(runs.PHASES)

    def test_an_outcome_cannot_be_recorded_without_a_timing(self):
        record = runs.start(runs.begin('m', 'apply'))
        with pytest.raises(TypeError):
            record.record_outcome('packages/github/fzf', str(Verdict.MATCHED), 'planned')  # type: ignore[call-arg]

    def test_why_a_failure_failed_survives_the_round_trip(self, runs_dir):
        """The record is what leaves the machine when an offline install goes
        wrong, so a failure whose reason lives only in the console is a record
        that cannot answer the one question it was uploaded for."""
        record = runs.start(runs.begin('m', 'apply'))
        record.record_outcome(
            'packages/ghrelease/win32yank',
            str(Verdict.MISSING),
            str(OutcomeStatus.FAILED),
            timed(act=1),
            'checksum mismatch',
        )

        recovered = runs.read(runs.write(runs.finish(record), runs_dir))
        assert recovered.outcomes[0].message == 'checksum mismatch'

    def test_an_unknown_phase_is_refused_rather_than_recorded(self):
        with pytest.raises(ValueError, match='unknown phase'), runs.Stopwatch().phase('sprint'):
            pass

    def test_re_entering_a_phase_adds_to_it(self):
        """One item fetching several assets should report fetching once."""
        stopwatch = runs.Stopwatch()
        with stopwatch.phase('fetch'):
            pass
        first = stopwatch.phases['fetch']
        with stopwatch.phase('fetch'):
            pass

        assert stopwatch.phases['fetch'] > first
        assert list(stopwatch.finish().phases) == ['fetch']


class TestConvergence:
    def test_a_run_with_an_issue_has_not_converged(self, runs_dir):
        assert not a_run().converged

    def test_a_run_where_everything_matched_has_converged(self):
        record = runs.start(runs.begin('m', 'check'))
        record.record_outcome('symlinks/common', str(Verdict.MATCHED), 'planned', timed(observe=1))
        assert runs.finish(record).converged

    def test_a_run_that_changed_something_has_not_converged(self):
        record = runs.start(runs.begin('m', 'apply'))
        record.record_outcome('packages/github/fzf', str(Verdict.STALE), str(OutcomeStatus.DONE), timed(act=1))
        assert not runs.finish(record).converged


class TestSpan:
    def test_the_run_is_as_long_as_the_caller_says_it_was(self):
        """A record assembled from an event stream is assembled once the run is
        over, so measuring from here times the walk over an already-collected list
        — which is how an apply that installed 112 things recorded 0.0003s."""
        began = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=4)
        record = runs.finish(runs.start(runs.begin('m', 'apply', began)))

        assert record.duration_seconds > 200

    def test_the_file_is_named_after_the_start_not_the_finish(self, runs_dir):
        began = dt.datetime(2026, 8, 10, 14, 0, 0, tzinfo=dt.UTC)
        path = runs.write(runs.finish(runs.start(runs.begin('wsl-work-workstation', 'apply', began))), runs_dir)

        assert path.stem == '20260810T140000Z-wsl-work-workstation-apply'


class TestListing:
    def test_runs_come_back_newest_first(self, runs_dir):
        for index in range(3):
            record = a_run()
            record.started_at = f'2026-08-0{index + 1}T00:00:00Z'
            runs.write(record, runs_dir)

        listed = runs.list_runs(runs_dir)
        assert [path.stem.split('-')[0] for path in listed] == ['20260803T000000Z', '20260802T000000Z', '20260801T000000Z']

    def test_a_machine_whose_name_contains_hyphens_still_filters(self, runs_dir):
        runs.write(a_run(machine='macos-personal-workstation'), runs_dir)
        record = a_run(machine='linux-lxc-server')
        record.started_at = '2026-08-01T00:00:00Z'
        runs.write(record, runs_dir)

        assert len(runs.list_runs(runs_dir, machine='linux-lxc-server')) == 1
        assert len(runs.list_runs(runs_dir, machine='macos-personal-workstation')) == 1

    def test_filtering_by_verb(self, runs_dir):
        runs.write(a_run(verb='apply'), runs_dir)
        record = a_run(verb='check')
        record.started_at = '2026-08-01T00:00:00Z'
        runs.write(record, runs_dir)

        assert len(runs.list_runs(runs_dir, verb='check')) == 1

    def test_latest_points_at_the_newest_record(self, runs_dir, monkeypatch):
        """Both halves are per-machine now that the fleet shares runs/: the link
        carries the name in it, and the lookup narrows to the machine asking."""
        monkeypatch.setattr(paths, 'MACHINE_ID', 'macos-personal-workstation')
        monkeypatch.setattr(paths, 'LATEST_RUN', paths.STATE_HOME / 'latest-macos-personal-workstation')
        older = a_run()
        older.started_at = '2026-08-01T00:00:00Z'
        runs.write(older, runs_dir)
        newest = runs.write(a_run(), runs_dir)

        link = runs_dir.parent / 'latest-macos-personal-workstation'
        assert link.is_symlink()
        assert link.resolve() == newest.resolve()
        assert runs.latest(runs_dir) == newest

    def test_latest_is_this_boxs_run_and_not_the_fleets_newest(self, runs_dir, monkeypatch):
        """The directory is shared, so the newest record in it is whichever box ran
        most recently. Narrowing on the record's machine does not fix that either:
        it names the manifest, and both Macs declare the same one — so the answer
        is the per-host link, which is written here and deliberately not synced.
        """
        monkeypatch.setattr(paths, 'LATEST_RUN', paths.STATE_HOME / 'latest-thisbox')
        mine = a_run()
        mine.started_at = '2026-08-01T00:00:00Z'
        written = runs.write(mine, runs_dir)

        # Another machine's record, newer, written without touching this box's link.
        theirs = a_run(machine='macos-personal-workstation')
        (runs_dir / f'{runs.record_filename(theirs)}.json').write_text('{}')

        assert runs.latest(runs_dir) == written

    def test_latest_falls_back_to_the_newest_record_when_the_link_is_absent(self, runs_dir, monkeypatch):
        """A machine that has never run under this scheme still has records, and
        answering nothing there is worse than answering approximately."""
        monkeypatch.setattr(paths, 'LATEST_RUN', paths.STATE_HOME / 'latest-thisbox')
        written = runs.write(a_run(), runs_dir)
        (runs_dir.parent / 'latest-thisbox').unlink()

        assert runs.latest(runs_dir) == written
