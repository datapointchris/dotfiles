"""wait-for ends on what its check reads, and never takes an empty or garbled read as "not yet".

Run with: pytest tests/apps/test_wait_for.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

WAIT_FOR = Path(__file__).resolve().parents[2] / 'apps' / 'common' / 'wait-for'


def waits(check: str, timeout: str = '5s', *flags: str) -> tuple[int, dict]:
    done = subprocess.run(
        [WAIT_FOR, '--timeout', timeout, '--every', '0.05', *flags, '--json', '--', 'sh', '-c', check],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return done.returncode, json.loads(done.stdout)


@pytest.mark.parametrize(
    ('check', 'exit_code', 'outcome', 'polls'),
    [
        ('echo ready', 0, 'ready', 1),
        ('echo "the run ended canceled"; echo failed', 1, 'failed', 1),
        ('n=$(cat count 2>/dev/null || echo 0); echo $((n+1)) > count; [ "$n" -ge 1 ] && echo ready || echo pending', 0, 'ready', 2),
        ('echo maybe', 2, 'unreadable', 3),
        ('echo', 2, 'unreadable', 3),
        ('echo "no such tag" >&2; exit 3', 2, 'unreadable', 3),
    ],
    ids=['ready', 'failed', 'pending then ready', 'garbled', 'empty', 'non-zero exit'],
)
def test_a_wait_ends_on_its_reading(tmp_path, monkeypatch, check, exit_code, outcome, polls) -> None:
    monkeypatch.chdir(tmp_path)
    got, verdict = waits(check)
    assert (got, verdict['outcome'], verdict['polls']) == (exit_code, outcome, polls)


def test_a_check_still_pending_ends_at_the_deadline() -> None:
    got, verdict = waits('echo pending', timeout='0m0.4s')
    assert (got, verdict['outcome']) == (1, 'deadline')


# The check counts its own polls in a file: n is 0 on the first.
COUNTED = 'n=$(cat count 2>/dev/null || echo 0); echo $((n+1)) > count; '


@pytest.mark.parametrize(
    ('check', 'flags', 'exit_code', 'outcome'),
    [
        (COUNTED + '[ "$n" -ge 2 ] && echo "pending 1" || echo "pending $((n+5))"', (), 1, 'regressed'),
        (COUNTED + '[ "$n" -ge 1 ] && echo "pending 7" || echo "pending 3"', ('--stall', '0.3s'), 1, 'stalled'),
        (COUNTED + 'echo "pending $n"; [ "$n" -lt 3 ] || echo ready', ('--stall', '0.3s'), 0, 'ready'),
        ('echo pending', ('--stall', '0.3s'), 2, 'unreadable'),
    ],
    ids=['went back', 'stopped rising', 'rising then ready', 'no number under --stall'],
)
def test_a_wait_ends_when_its_progress_stops_or_goes_back(tmp_path, monkeypatch, check, flags, exit_code, outcome) -> None:
    monkeypatch.chdir(tmp_path)
    got, verdict = waits(check, '10s', *flags)
    assert (got, verdict['outcome']) == (exit_code, outcome)
