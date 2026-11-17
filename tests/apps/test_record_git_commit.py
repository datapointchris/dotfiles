"""What the commit hook records for each commit, run through real commits and merges."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO = Path(__file__).resolve().parents[2]
RECORD_HOOK = REPO / 'apps' / 'trust' / 'fleet' / 'record-git-commit'
SCHEMA = json.loads((REPO / 'apps' / 'trust' / 'fleet' / 'git-commit-record.schema.json').read_text())
HOOK_LIBRARY = REPO / 'configs' / 'trust' / 'fleet' / '.local' / 'shell'
SESSION_VARIABLES = (
    'CLAUDE_CODE_SESSION_ID', 'CLAUDE_CODE_SESSION_ATTENDED', 'SLATE_ACTOR', 'FLEET_RUN_ID', 'TMUX_PANE', 'BAGGAGE', 'TRACEPARENT',
    'OTEL_RESOURCE_ATTRIBUTES',
)  # fmt: skip
FLOW = '4bf92f3577b34da6a3ce929d0e0e4736'
SESSION = {
    'CLAUDE_CODE_SESSION_ID': 's-1',
    'SLATE_ACTOR': 'inbox-fix@build-box',
    'FLEET_RUN_ID': 'run-8',
    'BAGGAGE': f'other=1, fleet.flow.id={FLOW};origin=queue',
    'TRACEPARENT': f'00-{FLOW}-00f067aa0ba902b7-01',
    'OTEL_RESOURCE_ATTRIBUTES': 'fleet.worker=build-box,gen_ai.agent.name=inbox-fix',
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    checkout = tmp_path / 'checkout'
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(checkout)], check=True)
    subprocess.run(['git', 'remote', 'add', 'origin', 'git@example.com:someone/some-repo.git'], cwd=checkout, check=True)
    return checkout


def git(repo: Path, *args: str, **variables: str) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if name not in SESSION_VARIABLES}
    env |= {
        'GIT_CONFIG_GLOBAL': os.devnull,
        'GIT_CONFIG_NOSYSTEM': '1',
        'XDG_STATE_HOME': str(repo.parent / 'state'),
        'SHELL_DIR': str(HOOK_LIBRARY),
        **variables,
    }
    return subprocess.run(
        ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com',
         '-c', 'hook.record.event=post-commit', '-c', 'hook.record.event=post-merge', '-c', f'hook.record.command={RECORD_HOOK}', *args],
        cwd=repo, env=env, check=True, capture_output=True, text=True,
    )  # fmt: skip


def records(repo: Path) -> list[dict[str, Any]]:
    """Each record the hook wrote, every one of them checked against the schema it publishes."""
    written = repo.parent / 'state' / 'telemetry' / 'git-commits.jsonl'
    found = [json.loads(line) for line in written.read_text().splitlines()] if written.exists() else []
    for record in found:
        jsonschema.validate(record, SCHEMA)
    return found


def sha(repo: Path, ref: str = 'HEAD') -> str:
    return git(repo, 'rev-parse', ref).stdout.strip()


def test_a_commit_and_a_landings_merge_each_record_once_and_a_fast_forward_records_nothing(repo: Path) -> None:
    git(repo, 'commit', '-q', '--allow-empty', '-m', 'chore: base', **SESSION)
    git(repo, 'switch', '-q', '-c', 'work')
    git(repo, 'commit', '-q', '--allow-empty', '-m', 'feat: work', **SESSION)
    git(repo, 'switch', '-q', '--detach', 'main')
    git(repo, 'merge', '-q', '--no-ff', '--no-edit', '-m', 'chore: merge work into main', 'work', **SESSION)
    merge = sha(repo)
    git(repo, 'switch', '-q', 'main')
    git(repo, 'merge', '-q', '--ff-only', merge, **SESSION)

    base, work, merged = records(repo)
    assert re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', base['timestamp'])
    assert base == {
        'timestamp': base['timestamp'],
        'name': 'git.commit_made',
        'resource': 'fleet.worker=build-box,gen_ai.agent.name=inbox-fix,service.name=git',
        'fleet.schema_version': 1,
        'trace_id': FLOW,
        'span_id': '00f067aa0ba902b7',
        'vcs.ref.head.revision': sha(repo, 'main~1'),
        'vcs.repository.name': 'some-repo',
        'vcs.ref.head.name': 'main',
        'session.id': 's-1',
        'fleet.commit.parents': [],
        'fleet.agent.name': 'claude-code-unattended/inbox-fix',
        'fleet.run.id': 'run-8',
        'fleet.flow.id': FLOW,
    }
    assert (work['vcs.ref.head.revision'], work['vcs.ref.head.name']) == (sha(repo, 'work'), 'work')
    assert merged['vcs.ref.head.revision'] == merge
    assert merged['fleet.commit.parents'] == [sha(repo, 'main~1'), sha(repo, 'work')]
    assert 'vcs.ref.head.name' not in merged


def test_a_persons_commit_names_no_session_or_flow_and_a_fixture_repo_records_nothing(repo: Path) -> None:
    git(repo, 'commit', '-q', '--allow-empty', '-m', 'chore: typed by a person', BAGGAGE='fleet.flow.id=' + '0' * 32)
    git(repo, 'remote', 'remove', 'origin')
    git(repo, 'commit', '-q', '--allow-empty', '-m', 'test: a fixture', **SESSION)

    (typed,) = records(repo)
    assert typed['resource'] == 'service.name=git'
    assert {'session.id', 'fleet.agent.name', 'fleet.run.id', 'fleet.flow.id', 'trace_id'}.isdisjoint(typed)
