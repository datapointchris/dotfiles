"""The run record survives being written and read back.

Every field a report verb will read has to round-trip, because a record that
loses one is only discovered by the report that needed it, long after the run it
described. These land before anything writes records so the format is settled
while it is still free to change.
"""

import json

import pytest

from dotfiles import runs


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
    record = runs.start(machine, verb, flags={'skip': ['system']})
    record.record_outcome('packages/github/fzf', 'OUTDATED', 'installed', timed(observe=1, fetch=1, act=1))
    record.record_outcome('symlinks/common', 'MATCHED', 'none', timed(observe=1))
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
        record = runs.start('m', 'apply')
        with pytest.raises(TypeError):
            record.record_outcome('packages/github/fzf', 'MATCHED', 'none')  # type: ignore[call-arg]

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
        record = runs.start('m', 'check')
        record.record_outcome('symlinks/common', 'MATCHED', 'none', timed(observe=1))
        assert runs.finish(record).converged


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

    def test_latest_points_at_the_newest_record(self, runs_dir):
        older = a_run()
        older.started_at = '2026-08-01T00:00:00Z'
        runs.write(older, runs_dir)
        newest = runs.write(a_run(), runs_dir)

        link = runs_dir.parent / 'latest'
        assert link.is_symlink()
        assert link.resolve() == newest.resolve()
        assert runs.latest(runs_dir) == newest


class TestPrune:
    def write_records(self, runs_dir, count):
        for index in range(count):
            record = a_run()
            record.started_at = f'2026-08-{index + 1:02d}T00:00:00Z'
            path = runs.write(record, runs_dir)
            runs.event_log_path(record, runs_dir).write_text('{}\n')
            assert path.exists()

    def test_it_keeps_the_newest_and_drops_the_rest(self, runs_dir):
        self.write_records(runs_dir, 5)

        removed = runs.prune(runs_dir, keep=2)

        assert len(removed) == 3
        assert len(runs.list_runs(runs_dir)) == 2

    def test_it_takes_the_event_stream_with_the_record(self, runs_dir):
        self.write_records(runs_dir, 3)

        runs.prune(runs_dir, keep=1)

        assert not list(runs_dir.glob('20260801*.jsonl'))
        assert len(list(runs_dir.glob('*.jsonl'))) == 1

    def test_it_is_idempotent(self, runs_dir):
        self.write_records(runs_dir, 4)

        runs.prune(runs_dir, keep=2)
        assert runs.prune(runs_dir, keep=2) == []

    def test_it_never_leaves_latest_dangling(self, runs_dir):
        self.write_records(runs_dir, 3)

        runs.prune(runs_dir, keep=1)

        link = runs_dir.parent / 'latest'
        assert link.resolve().exists()
