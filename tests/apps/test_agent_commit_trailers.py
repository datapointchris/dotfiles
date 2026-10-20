"""The agent trailers a commit carries, run through real commits."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / 'apps' / 'trust' / 'fleet' / 'agent-commit-trailers'
SESSION_VARIABLES = ('CLAUDE_CODE_SESSION_ID', 'CLAUDE_CODE_SESSION_ATTENDED', 'ICB_ACTOR', 'FLEET_RUN_ID', 'TMUX_PANE')


def commit(repo: Path, *args: str, **variables: str) -> None:
    env = {name: value for name, value in os.environ.items() if name not in SESSION_VARIABLES}
    env |= {'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1', **variables}
    subprocess.run(
        ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com', '-c', 'hook.agent.event=prepare-commit-msg',
         '-c', f'hook.agent.command={HOOK}', 'commit', '-q', '--allow-empty', *args],
        cwd=repo, env=env, check=True,
    )  # fmt: skip


def trailers(repo: Path) -> list[str]:
    return subprocess.run(['git', 'log', '--format=%(trailers)%x00'], cwd=repo, capture_output=True, text=True, check=True).stdout.split(
        '\0'
    )[:-1]


def test_a_session_commit_is_stamped_once_and_a_persons_commit_never(tmp_path: Path) -> None:
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)

    commit(tmp_path, '-m', 'chore: typed by a person')
    commit(
        tmp_path, '-m', 'fix: made by a scheduled job', CLAUDE_CODE_SESSION_ID='s-1', ICB_ACTOR='inbox-fix@build-box', FLEET_RUN_ID='run-8'
    )
    commit(tmp_path, '--amend', '--no-edit', CLAUDE_CODE_SESSION_ID='s-2')

    amended, typed = trailers(tmp_path)
    assert amended.strip().splitlines() == ['Agent-Name: claude-code-unattended/inbox-fix', 'Agent-Session: s-1', 'Agent-Run: run-8']
    assert typed.strip() == ''
