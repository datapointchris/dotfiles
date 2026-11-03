"""What a commit carries and what it records on slate, run through real commits against a stand-in slate."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TRAILER_HOOK = REPO / 'apps' / 'trust' / 'fleet' / 'agent-commit-trailers'
LINK_HOOK = REPO / 'apps' / 'trust' / 'fleet' / 'link-commit-to-slate-worklog'
SESSION_VARIABLES = ('CLAUDE_CODE_SESSION_ID', 'CLAUDE_CODE_SESSION_ATTENDED', 'SLATE_ACTOR', 'FLEET_RUN_ID', 'TMUX_PANE')
STAND_IN_SLATE = """#!/bin/sh
case "$2" in
current)
  [ -z "${CURRENT_FAILS:-}" ] || { echo "error: not logged in" >&2; exit 1; }
  [ -z "${WORKLOG:-}" ] || echo "$WORKLOG"
  ;;
link)
  [ -z "${LINK_FAILS:-}" ] || { echo "error: no such worklog" >&2; exit 1; }
  echo "$*" >>"$LINKS"
  ;;
esac
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    (bin_dir / 'slate').write_text(STAND_IN_SLATE)
    (bin_dir / 'slate').chmod(0o755)
    checkout = tmp_path / 'checkout'
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(checkout)], check=True)
    subprocess.run(['git', 'remote', 'add', 'origin', 'git@example.com:someone/some-repo.git'], cwd=checkout, check=True)
    return checkout


def git(repo: Path, *args: str, **variables: str) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if name not in SESSION_VARIABLES}
    env |= {
        'GIT_CONFIG_GLOBAL': os.devnull,
        'GIT_CONFIG_NOSYSTEM': '1',
        'PATH': f'{repo.parent / "bin"}{os.pathsep}{os.environ["PATH"]}',
        'LINKS': str(repo.parent / 'links'),
        **variables,
    }
    return subprocess.run(
        ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com',
         '-c', 'hook.trailers.event=prepare-commit-msg', '-c', f'hook.trailers.command={TRAILER_HOOK}',
         '-c', 'hook.link.event=post-commit', '-c', f'hook.link.command={LINK_HOOK}', *args],
        cwd=repo, env=env, check=True, capture_output=True, text=True,
    )  # fmt: skip


def commit(repo: Path, *args: str, **variables: str) -> subprocess.CompletedProcess[str]:
    return git(repo, 'commit', '-q', '--allow-empty', *args, **variables)


def trailers(repo: Path) -> list[str]:
    return subprocess.run(['git', 'log', '--format=%(trailers)%x00'], cwd=repo, capture_output=True, text=True, check=True).stdout.split(
        '\0'
    )[:-1]


def links(repo: Path) -> list[str]:
    recorded = repo.parent / 'links'
    return recorded.read_text().splitlines() if recorded.exists() else []


def head(repo: Path) -> str:
    return git(repo, 'rev-parse', 'HEAD').stdout.strip()


def test_a_session_commit_is_stamped_once_and_a_persons_commit_never(repo: Path) -> None:
    commit(repo, '-m', 'chore: typed by a person', WORKLOG='2083.1')
    commit(
        repo, '-m', 'fix: made by a scheduled job', CLAUDE_CODE_SESSION_ID='s-1', SLATE_ACTOR='inbox-fix@build-box', FLEET_RUN_ID='run-8'
    )
    commit(repo, '--amend', '--no-edit', CLAUDE_CODE_SESSION_ID='s-2')

    amended, typed = trailers(repo)
    assert amended.strip().splitlines() == ['Agent-Name: claude-code-unattended/inbox-fix', 'Agent-Session: s-1', 'Agent-Run: run-8']
    assert typed.strip() == ''
    assert links(repo) == []


def test_a_second_session_rebasing_leaves_each_commit_with_the_worklog_and_session_that_wrote_it(repo: Path) -> None:
    commit(repo, '-m', 'chore: base')
    git(repo, 'switch', '-q', '-c', 'work')
    commit(repo, '-m', 'chore: typed by a person')
    commit(repo, '-m', 'feat: first go', CLAUDE_CODE_SESSION_ID='s-1', WORKLOG='2083.1')
    git(repo, 'switch', '-q', 'main')
    commit(repo, '-m', 'chore: main moves')

    git(repo, 'rebase', '-q', 'main', 'work', CLAUDE_CODE_SESSION_ID='s-2', WORKLOG='2099.4')

    written, typed, *_ = trailers(repo)
    assert written.strip().splitlines()[-2:] == ['Agent-Session: s-1', 'Worklog: 2083.1']
    assert typed.strip() == ''
    assert len(links(repo)) == 2
    assert links(repo)[-1] == f'worklogs link 2083.1 --commit {head(repo)} --repo some-repo --session s-1'


@pytest.mark.parametrize('fixture_origin', [None, '/elsewhere/fixture.git', 'file:///elsewhere/fixture.git'])
def test_a_session_committing_in_a_tests_fixture_repo_reaches_no_worklog(repo: Path, fixture_origin: str | None) -> None:
    git(repo, 'remote', 'remove', 'origin')
    if fixture_origin:
        git(repo, 'remote', 'add', 'origin', fixture_origin)

    commit(repo, '-m', 'test: a fixture', CLAUDE_CODE_SESSION_ID='s-1', WORKLOG='2083.1')

    assert 'Worklog' not in trailers(repo)[0]
    assert links(repo) == []


@pytest.mark.parametrize(
    ('failing', 'reason', 'stamped'),
    [
        ({'CURRENT_FAILS': '1'}, 'error: not logged in', False),
        ({'LINK_FAILS': '1'}, 'error: no such worklog', True),
    ],
)
def test_a_slate_that_fails_leaves_the_commit_and_says_so_once(repo: Path, failing: dict[str, str], reason: str, stamped: bool) -> None:
    done = commit(repo, '-m', 'fix: still lands', CLAUDE_CODE_SESSION_ID='s-1', WORKLOG='2083.1', **failing)

    assert len(done.stderr.splitlines()) == 1
    assert reason in done.stderr
    assert 'Agent-Session: s-1' in trailers(repo)[0]
    assert ('Worklog: 2083.1' in trailers(repo)[0]) is stamped
    assert links(repo) == []
