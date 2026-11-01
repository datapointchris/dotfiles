"""The line a timer run appends is what a log agent parses, so its shape is pinned here."""

import json
import stat
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import timer_reports
from dotfiles.providers import periodic_job
from dotfiles.providers import timers
from dotfiles.resources import Repair
from dotfiles.resources import Verdict


def timer(*argv: str) -> catalog.UserTimer:
    return catalog.UserTimer(name='probe', argv=argv, every='1h')


def test_a_run_records_its_outcome_summary_and_report_in_a_line_that_opens_with_its_timestamp(tmp_path):
    failed = timer_reports.run(timer('sh', '-c', 'echo partial; echo the remote refused >&2; exit 4'))
    assert (failed['outcome'], failed['exit_code'], failed['summary']) == ('fail', 4, 'the remote refused')
    assert failed['report'] == {'stdout': 'partial\n', 'stderr': 'the remote refused\n'}

    passed = timer_reports.run(timer('sh', '-c', 'echo \'{"summary": "3 tools checked", "failing": []}\''))
    assert (passed['outcome'], passed['timer'], passed['summary']) == ('pass', 'probe', '3 tools checked')
    assert passed['report'] == {'summary': '3 tools checked', 'failing': []}
    assert timer_reports.run(timer('sh', '-c', 'echo plain text'))['report'] == {}, 'a pass ships no stream it was not asked for'

    path = timer_reports.record(passed, tmp_path)
    line = path.read_text().splitlines()[0]
    assert line.startswith('{"timestamp": "'), 'a file tailer tells files apart by their first bytes'
    assert json.loads(line) == passed


@pytest.fixture
def installed_probe(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The probe row's units installed on a Linux box whose systemctl answers yes."""
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setattr(periodic_job, 'is_darwin', lambda: False)
    monkeypatch.setattr(timer_reports, 'REPORTS_DIR', tmp_path / 'reports')
    systemctl = fake_bin / 'systemctl'
    systemctl.write_text('#!/bin/sh\nexit 0\n')
    systemctl.chmod(systemctl.stat().st_mode | stat.S_IEXEC)
    assert timers.apply(timer('true')).ok
    return tmp_path / 'config' / 'systemd' / 'user'


def test_a_box_with_no_agent_hears_of_a_failing_run_from_check(installed_probe: Path) -> None:
    probe = timer('false')
    assert timers.observe(probe).verdict is Verdict.MATCHED

    timer_reports.record(timer_reports.run(probe))
    failing = timers.observe(probe)

    assert (failing.verdict, failing.repair) == (Verdict.STALE, Repair.BY_HAND)
    assert 'failed: probe exited 1' in failing.detail


def test_a_retired_row_leaves_its_units_and_check_names_them_with_the_removal(installed_probe: Path) -> None:
    (installed_probe / 'dotfiles-timer-retired.timer').write_text('[Timer]\n')

    assert timers.strays({'probe'}) == {'retired': timers.removal('retired')}
    assert 'systemctl --user disable --now dotfiles-timer-retired.timer' in timers.removal('retired')
