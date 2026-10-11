"""What claude-sessions prints for a registry row, read through `--self`.

`--self` finds the registry file named for an ancestor pid, so a file named for
this test process is the one it reads. It renders through the same two jq
programs the full listing does, and reaches them without `fd`, which the runner
does not have.

Run with: pytest tests/apps/test_claude_sessions.py
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CLAUDE_SESSIONS = REPO / 'apps' / 'common' / 'claude-sessions'


def registry_row(**fields: Any) -> dict[str, Any]:
    return {
        'pid': os.getpid(),
        'name': 'alpha-1',
        'sessionId': 'abc',
        'cwd': '/w/alpha',
        'tmux': 'system:@1.%1',
    } | fields


def self_row(tmp_path: Path, row: dict[str, Any], *args: str) -> str:
    registry = tmp_path / 'sessions'
    registry.mkdir()
    (registry / f'{os.getpid()}.json').write_text(json.dumps(row))
    env = {'PATH': os.environ['PATH'], 'HOME': str(tmp_path), 'CLAUDE_CONFIG_DIR': str(tmp_path)}
    result = subprocess.run([str(CLAUDE_SESSIONS), '--self', *args], capture_output=True, text=True, env=env, check=True)
    return result.stdout


def test_a_row_with_no_status_reads_as_unknown(tmp_path):
    assert json.loads(self_row(tmp_path, registry_row(), '--json'))['status'] == 'unknown'


def test_a_row_with_no_status_reads_as_unknown_in_the_table(tmp_path):
    assert self_row(tmp_path, registry_row()).split('\t')[1] == 'unknown'


def test_a_written_status_is_passed_through(tmp_path):
    assert json.loads(self_row(tmp_path, registry_row(status='busy'), '--json'))['status'] == 'busy'
