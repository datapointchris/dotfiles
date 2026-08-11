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


def timed(**steps) -> runs.Timing:
    stopwatch = runs.Stopwatch()
    for name in steps:
        with stopwatch.step(name):
            pass
    return stopwatch.finish()


def a_run(machine='macos-personal-workstation', verb='apply', host=None) -> runs.RunRecord:
    """Verdicts and actions spelled by the enums the writer serialises, never by
    hand. `converged` compared against a hand-typed `'MATCHED'` for its whole life
    and was therefore never true, and this fixture typing the same word is the
    reason no test noticed.

    `host` is explicit rather than left to default, because the default is the
    real hostname of whatever box runs the suite — which put `archlinux` in the
    filenames these tests assert on.
    """
    record = runs.start(runs.begin(machine, verb, host=machine if host is None else host), flags={'skip': ['system']})
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
        assert payload['outcomes'][0]['timing']['steps']['fetch'] >= 0

    def test_a_pre_4_record_is_read_through_its_old_spelling(self, runs_dir):
        """`phases` became `steps` at schema 4, and a rename is the one schema
        change a default cannot absorb: the old key reaches the constructor and
        raises, where a merely-absent field would have taken its default. 68 of
        the fleet's records were written at schema 1 and must stay readable.
        """
        path = runs.write(a_run(), runs_dir)
        payload = json.loads(path.read_text())
        payload['schema'] = 3
        payload['outcomes'][0]['timing']['phases'] = payload['outcomes'][0]['timing'].pop('steps')
        path.write_text(json.dumps(payload))

        recovered = runs.read(path)

        assert recovered.outcomes[0].timing.steps['fetch'] >= 0

    def test_every_outcome_carries_a_step_breakdown(self, runs_dir):
        """A resource that lands untimed drops silently out of every duration
        report, so the record is the place to catch it."""
        recovered = runs.read(runs.write(a_run(), runs_dir))

        for outcome in recovered.outcomes:
            assert outcome.timing.started_at
            assert outcome.timing.steps, f'{outcome.address} recorded no steps'
            assert set(outcome.timing.steps) <= set(runs.STEPS)

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

    def test_an_unknown_step_is_refused_rather_than_recorded(self):
        with pytest.raises(ValueError, match='unknown step'), runs.Stopwatch().step('sprint'):
            pass

    def test_re_entering_a_step_adds_to_it(self):
        """One item fetching several assets should report fetching once."""
        stopwatch = runs.Stopwatch()
        with stopwatch.step('fetch'):
            pass
        first = stopwatch.steps['fetch']
        with stopwatch.step('fetch'):
            pass

        assert stopwatch.steps['fetch'] > first
        assert list(stopwatch.finish().steps) == ['fetch']


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
        identity = runs.begin('wsl-work-workstation', 'apply', began, host='worklaptop')
        path = runs.write(runs.finish(runs.start(identity)), runs_dir)

        assert path.stem == '20260810T140000Z-worklaptop-apply'


class TestListing:
    def test_runs_come_back_newest_first(self, runs_dir):
        for index in range(3):
            record = a_run()
            record.started_at = f'2026-08-0{index + 1}T00:00:00Z'
            runs.write(record, runs_dir)

        listed = runs.list_runs(runs_dir)
        assert [path.stem.split('-')[0] for path in listed] == ['20260803T000000Z', '20260802T000000Z', '20260801T000000Z']

    def test_two_boxes_sharing_a_manifest_are_separate_runs(self, runs_dir):
        """macmini and mbp both declare `macos-personal-workstation`. Keyed on the
        manifest their records were one indistinguishable stream — the reason
        "check the reports for both of them" could not be answered at all."""
        runs.write(a_run(host='macmini'), runs_dir)
        older = a_run(host='mbp')
        older.started_at = '2026-08-01T00:00:00Z'
        runs.write(older, runs_dir)

        assert len(runs.list_runs(runs_dir, machine='macmini')) == 1
        assert len(runs.list_runs(runs_dir, machine='mbp')) == 1
        assert {runs.read(path).box for path in runs.list_runs(runs_dir)} == {'macmini', 'mbp'}

    def test_a_record_written_before_the_host_field_still_names_its_machine(self, runs_dir):
        """Every reader takes `box`, not `host`: a bare `host` would pool the whole
        pre-schema-3 history of all four boxes into one nameless bucket."""
        record = a_run()
        record.host = ''
        written = runs.write(record, runs_dir)

        assert runs.read(written).box == 'macos-personal-workstation'

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

    def test_the_link_is_read_from_where_it_was_written(self, runs_dir, monkeypatch):
        """Read and write have to derive the link from the same root.

        `write` took it from the records directory while `latest` took it from
        `STATE_HOME`, which agree only because `RUNS_DIR` happens to sit directly
        under it. Anything pointed elsewhere — every test using a tmp directory,
        and `report latest` with it — wrote the link to one place and resolved a
        *real* one from the other, so a rendered record came from the live machine
        rather than the directory it was handed.
        """
        monkeypatch.setattr(paths, 'LATEST_RUN', paths.STATE_HOME / 'latest-thisbox')
        monkeypatch.setattr(paths, 'RUNS_DIR', runs_dir)
        written = runs.write(a_run(), runs_dir)

        assert runs.latest() == written, 'the default read has to find the link the write left'
        assert runs.latest(runs_dir) == written
