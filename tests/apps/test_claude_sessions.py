"""What claude-sessions prints for registry rows, through `--self` and the full listing.

`--self` finds the registry file named for an ancestor pid, so a file named for
this test process is the one it reads. The full listing keeps every file whose
pid is alive, and this test process is.

Run with: pytest tests/apps/test_claude_sessions.py
"""

from __future__ import annotations

import json
import os
import re
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
    env = {'PATH': os.environ['PATH'], 'HOME': str(tmp_path), 'CLAUDE_CONFIG_DIR': str(tmp_path), 'TMUX_TMPDIR': str(tmp_path)}
    result = subprocess.run([str(CLAUDE_SESSIONS), '--self', *args], capture_output=True, text=True, env=env, check=True)
    return result.stdout


def test_a_row_with_no_status_reads_as_unknown(tmp_path):
    assert json.loads(self_row(tmp_path, registry_row(), '--json'))['status'] == 'unknown'


def test_a_row_with_no_status_reads_as_unknown_in_the_table(tmp_path):
    assert self_row(tmp_path, registry_row()).split('\t')[1] == 'unknown'


def test_a_written_status_is_passed_through(tmp_path):
    assert json.loads(self_row(tmp_path, registry_row(status='busy'), '--json'))['status'] == 'busy'


def listing(tmp_path: Path, files: dict[str, str]) -> subprocess.CompletedProcess[str]:
    registry = tmp_path / 'sessions'
    registry.mkdir()
    for name, body in files.items():
        (registry / name).write_text(body)
    env = {'PATH': os.environ['PATH'], 'HOME': str(tmp_path), 'CLAUDE_CONFIG_DIR': str(tmp_path), 'TMUX_TMPDIR': str(tmp_path)}
    return subprocess.run([str(CLAUDE_SESSIONS), '--json'], capture_output=True, text=True, env=env, check=False)


# jq reads several files as one stream, so an unterminated string in one file
# runs into the next. Each file sorts between two good ones here.
def test_a_half_written_file_hides_no_other_session(tmp_path):
    result = listing(
        tmp_path,
        {
            '1.json': json.dumps(registry_row(name='alpha-1')),
            '2.json': '{"pid": 1, "name": "half',
            '3.json': json.dumps(registry_row(name='gamma-3'), indent=2),
        },
    )
    assert result.returncode == 0
    assert sorted(row['name'] for row in json.loads(result.stdout)) == ['alpha-1', 'gamma-3']


def transcript(tmp_path: Path, launched_in: str, session_id: str, lines: list[dict[str, Any]]) -> None:
    project = tmp_path / 'projects' / re.sub('[^A-Za-z0-9]', '-', launched_in)
    project.mkdir(parents=True, exist_ok=True)
    (project / f'{session_id}.jsonl').write_text(
        ''.join(json.dumps(line | {'sessionId': session_id}, separators=(',', ':')) + '\n' for line in lines)
    )


# A session that moved into a worktree keeps its transcript where it launched.
def test_a_rename_outranks_the_generated_title_and_the_newest_of_each_wins(tmp_path):
    transcript(
        tmp_path,
        '/w/alpha',
        'renamed',
        [
            {'type': 'ai-title', 'aiTitle': 'first'},
            {'type': 'custom-title', 'customTitle': 'picked'},
            {'type': 'ai-title', 'aiTitle': 'later'},
        ],
    )
    transcript(
        tmp_path,
        '/w/alpha',
        'generated',
        [{'type': 'ai-title', 'aiTitle': 'old'}, {'type': 'user'}, {'type': 'ai-title', 'aiTitle': 'new'}],
    )
    transcript(tmp_path, '/w/alpha', 'moved', [{'type': 'ai-title', 'aiTitle': 'found by id'}])
    rows = {
        'renamed': registry_row(sessionId='renamed'),
        'generated': registry_row(sessionId='generated'),
        'moved': registry_row(sessionId='moved', cwd='/w/.worktrees/alpha/slug'),
        'untitled': registry_row(sessionId='untitled'),
    }
    result = listing(tmp_path, {f'{name}.json': json.dumps(row) for name, row in rows.items()})
    assert result.returncode == 0, result.stderr
    assert {row['sessionId']: row['title'] for row in json.loads(result.stdout)} == {
        'renamed': 'picked',
        'generated': 'new',
        'moved': 'found by id',
        'untitled': None,
    }


def test_a_dead_session_listed_last_does_not_fail_the_listing(tmp_path):
    result = listing(
        tmp_path,
        {
            '1.json': json.dumps(registry_row(name='alpha-1')),
            '9.json': json.dumps(registry_row(name='gone-9', pid=2**22 + 1)),
        },
    )
    assert result.returncode == 0
    assert [row['name'] for row in json.loads(result.stdout)] == ['alpha-1']
