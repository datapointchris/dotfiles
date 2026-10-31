"""The line a timer run appends is what a log agent parses, so its shape is pinned here."""

import json

from dotfiles import catalog
from dotfiles import timer_reports


def timer(*argv: str) -> catalog.UserTimer:
    return catalog.UserTimer(name='probe', argv=argv, every='1h', report_key='probe-failing')


def test_a_run_records_its_outcome_summary_and_report_in_a_line_that_opens_with_its_timestamp(tmp_path):
    failed = timer_reports.run(timer('sh', '-c', 'echo partial; echo the remote refused >&2; exit 4'))
    assert (failed['outcome'], failed['exit_code'], failed['summary']) == ('fail', 4, 'the remote refused')
    assert failed['report'] == {'stdout': 'partial\n', 'stderr': 'the remote refused\n'}

    passed = timer_reports.run(timer('sh', '-c', 'echo \'{"summary": "3 tools checked", "failing": []}\''))
    assert (passed['outcome'], passed['key'], passed['summary']) == ('pass', 'probe-failing', '3 tools checked')
    assert passed['report'] == {'summary': '3 tools checked', 'failing': []}

    path = timer_reports.record(passed, tmp_path)
    line = path.read_text().splitlines()[0]
    assert line.startswith('{"timestamp": "'), 'a file tailer tells files apart by their first bytes'
    assert json.loads(line) == passed
