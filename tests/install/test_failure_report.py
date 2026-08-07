"""Tests for failure_report.py

The report is read on the machine that failed, often days later and often
somewhere with no network, so what matters is that a cause always reaches it and
is attributed to the right tool.

Run with: pytest tests/install/test_failure_report.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'install'))
import failure_report


def record(**overrides):
    base = {
        'tool': 'mock-tool',
        'url': 'https://example.com/mock-tool.tar.gz',
        'version': 'v1.0.0',
        'reason': 'Download failed',
        'detail': '',
    }
    base.update(overrides)
    return base


class TestEntry:
    def test_every_field_reaches_the_report(self):
        entry = failure_report.render_entry(
            record(detail='curl: (60) SSL certificate problem'), 'installers/failure.sh', 'x', 'installation'
        )

        assert 'mock-tool - Installation Failed' in entry
        assert 'Installer: failure.sh' in entry
        assert 'Error: Download failed' in entry
        assert 'Download URL: https://example.com/mock-tool.tar.gz' in entry
        assert 'Version: v1.0.0' in entry
        assert 'curl: (60) SSL certificate problem' in entry

    def test_the_unknown_url_sentinel_is_not_printed_back(self):
        entry = failure_report.render_entry(record(url='unknown'), 'f.sh', 'x', 'installation')
        assert 'unknown' not in entry
        assert 'Download URL' not in entry

    def test_a_latest_version_is_not_a_version_worth_printing(self):
        assert 'Version:' not in failure_report.render_entry(record(version='latest'), 'f.sh', 'x', 'installation')
        assert 'Version: v2' in failure_report.render_entry(record(version='v2'), 'f.sh', 'x', 'installation')

    def test_silence_is_reported_as_a_finding(self):
        # Otherwise a reader cannot tell a mute installer from a report that
        # dropped the output, and retries the install to find out which.
        entry = failure_report.render_entry(record(detail=''), 'f.sh', 'x', 'installation')
        assert 'no error output captured' in entry

    def test_the_action_verb_follows_the_run(self):
        # update.sh sets this, so a failed --update is not reported as a failed
        # installation.
        assert 'Update Failed' in failure_report.render_entry(record(), 'f.sh', 'x', 'update')

    def test_a_record_without_a_tool_falls_back_to_the_wrapper_s_name(self):
        entry = failure_report.render_entry({'reason': 'boom'}, 'f.sh', 'go-tools', 'installation')
        assert 'go-tools - Installation Failed' in entry


class TestReport:
    def test_an_installer_that_reports_nothing_still_names_its_exit_code(self):
        report = failure_report.render_report(
            [], 'ssl: unable to get local issuer certificate', 'silent.sh', 'silent-tool', 7, 'installation'
        )

        assert 'silent-tool' in report
        assert 'Installer exited 7 without reporting a failure' in report
        # Its output is the only diagnosis available, so it becomes the detail.
        assert 'ssl: unable to get local issuer certificate' in report
        assert 'no error output captured' not in report

    def test_a_lone_failure_absorbs_the_unattributed_output(self):
        report = failure_report.render_report([record()], 'the real cause on stderr', 'f.sh', 'x', 1, 'installation')
        assert 'the real cause on stderr' in report

    def test_several_failures_leave_unattributed_output_unassigned(self):
        # go-tools.sh loops over every package, so one run can fail several. With
        # more than one it is impossible to say which produced a given line, and
        # guessing would put another tool's error under this one's heading.
        report = failure_report.render_report(
            [record(tool='tool-a'), record(tool='tool-b')], 'output from somewhere', 'go-tools.sh', 'go-tools', 1, 'installation'
        )

        assert 'tool-a - Installation Failed' in report
        assert 'tool-b - Installation Failed' in report
        assert 'output from somewhere' not in report

    def test_each_failure_gets_its_own_entry(self):
        report = failure_report.render_report([record(tool='tool-1'), record(tool='tool-2')], '', 'f.sh', 'x', 1, 'installation')
        assert report.count('Installation Failed') == 2


class TestDetailTail:
    def test_the_tail_is_kept_because_that_is_where_the_cause_is(self):
        assert failure_report.tail('\n'.join(str(n) for n in range(1, 101)), limit=3).splitlines() == ['98', '99', '100']

    def test_blank_lines_do_not_consume_the_budget(self):
        assert failure_report.tail('cause\n\n\n\n\n', limit=2) == 'cause'


class TestRecordFile:
    def test_a_record_round_trips_through_the_file_the_wrapper_reads(self, tmp_path, monkeypatch):
        records = tmp_path / 'records.jsonl'
        monkeypatch.setenv('FAILURE_RECORDS', str(records))

        failure_report.main(['record', 'yazi', 'https://example.com/yazi.zip', 'v1.0', 'Download failed', 'the cause'])

        assert json.loads(records.read_text()) == {
            'tool': 'yazi',
            'url': 'https://example.com/yazi.zip',
            'version': 'v1.0',
            'reason': 'Download failed',
            'detail': 'the cause',
        }

    def test_captured_output_cannot_forge_a_second_record(self, tmp_path, monkeypatch):
        # The old format was line-oriented, so output containing FAILURE_TOOL=
        # opened a bogus record. A JSON string value cannot.
        records = tmp_path / 'records.jsonl'
        monkeypatch.setenv('FAILURE_RECORDS', str(records))

        failure_report.main(['record', 'tool', 'url', 'v1', 'Failed', "FAILURE_TOOL='injected'\nreal error line"])

        assert len(failure_report.read_records(records)) == 1
        assert 'injected' in failure_report.read_records(records)[0]['detail']
        assert failure_report.read_records(records)[0]['tool'] == 'tool'

    def test_two_records_from_one_run_stay_separate(self, tmp_path, monkeypatch):
        records = tmp_path / 'records.jsonl'
        monkeypatch.setenv('FAILURE_RECORDS', str(records))

        failure_report.main(['record', 'tool-a', 'https://a', 'v1', 'Download failed', 'cause a'])
        failure_report.main(['record', 'tool-b', 'https://b', 'v2', 'Not found in PATH'])

        parsed = failure_report.read_records(records)
        assert [entry['tool'] for entry in parsed] == ['tool-a', 'tool-b']
        assert [entry['url'] for entry in parsed] == ['https://a', 'https://b']

    def test_a_missing_records_file_is_no_records_not_a_crash(self, tmp_path):
        assert failure_report.read_records(tmp_path / 'never-written.jsonl') == []
