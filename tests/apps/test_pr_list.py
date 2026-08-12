"""`pr-list` is the one query behind `prs`, `fleet prs` and doit's PRS lane.

The seam is the provider CLI, shadowed on PATH, because nothing else here is
worth asserting: the jq is short and the interesting failures are all about a
*response shape*. Three of them are real and none would show up as an error.

GitHub's is asked for over GraphQL rather than `gh search prs`, whose field set
has no `headRefName` — so the response arrives under `.data.search.nodes` and a
`type: ISSUE` search can hand back a node the PullRequest fragment did not match.
Bitbucket's arrives from a Server API that spells a branch `fromRef.displayId`,
which shares no key with GitHub's. Both are mapped to one provider-neutral field
here so no consumer sees either spelling, and that mapping is what these pin.

Run with: pytest tests/apps/test_pr_list.py
"""

from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
PR_LIST = REPO / 'apps' / 'common' / 'pr-list'


def stub(directory: Path, name: str, script: str) -> None:
    """A binary that shadows the real one, first on PATH."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)


def graphql_node(repo: str, number: int, branch: str, base: str = 'main', **overrides: Any) -> dict[str, Any]:
    """One node as GitHub's GraphQL search returns it, in GitHub's own spelling."""
    node = {
        'number': number,
        'title': f'a change in {repo}',
        'url': f'https://github.com/datapointchris/{repo}/pull/{number}',
        'headRefName': branch,
        'baseRefName': base,
        'isDraft': False,
        'createdAt': '2026-08-01T10:00:00Z',
        'repository': {'name': repo, 'nameWithOwner': f'datapointchris/{repo}'},
    }
    return node | overrides


@pytest.fixture
def run(tmp_path: Path):
    """Invoke pr-list against a synthetic registry and a stubbed provider CLI.

    `/usr/bin:/bin` stays behind the stub dir so jq is the real one — the jq is
    most of what is under test, and a fake would assert nothing about it.
    """
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    def _run(registry: dict[str, Any], **stubs: str) -> subprocess.CompletedProcess[str]:
        for name, script in stubs.items():
            stub(bin_dir, name, script)
        path = tmp_path / 'repos.json'
        path.write_text(json.dumps(registry))
        return subprocess.run(
            [str(PR_LIST), '--registry', str(path)],
            capture_output=True,
            text=True,
            env={'HOME': str(tmp_path), 'PATH': f'{bin_dir}:/usr/bin:/bin'},
        )

    return _run


def github_stub(*nodes: dict[str, Any]) -> str:
    payload = json.dumps({'data': {'search': {'nodes': list(nodes)}}})
    return f"#!/bin/sh\ncat <<'JSON'\n{payload}\nJSON\n"


def test_a_github_pr_carries_the_branch_it_would_be_typed_as(run) -> None:
    result = run(
        {'provider': 'github', 'repos': [{'name': 'dotfiles', 'path': '~/dotfiles'}]},
        gh=github_stub(graphql_node('dotfiles', 1, 'split-plan-check-verbs')),
    )
    assert result.returncode == 0, result.stderr
    (pr,) = json.loads(result.stdout)
    assert pr['branch'] == 'split-plan-check-verbs'
    assert pr['base'] == 'main'


def test_a_stacked_pr_names_its_parent_rather_than_the_default_branch(run) -> None:
    """The reason `base` is carried at all: two PRs render as peer rows, and the
    only thing distinguishing a stack from two independent branches is that one's
    base is the other's head."""
    result = run(
        {'provider': 'github', 'repos': [{'name': 'dotfiles', 'path': '~/dotfiles'}]},
        gh=github_stub(
            graphql_node('dotfiles', 1, 'split-plan-check-verbs'),
            graphql_node('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
        ),
    )
    assert result.returncode == 0, result.stderr
    bases = {pr['number']: pr['base'] for pr in json.loads(result.stdout)}
    assert bases == {1: 'main', 2: 'split-plan-check-verbs'}


def test_a_search_node_that_is_not_a_pull_request_is_dropped(run) -> None:
    """`type: ISSUE` searches issues and PRs from one index, so a node the inline
    fragment does not match arrives as `{}`. Emitting it would be a row whose
    number is null, which fleet cannot unmarshal into an int — the listing fails
    wholesale rather than showing one empty line."""
    result = run(
        {'provider': 'github', 'repos': [{'name': 'dotfiles', 'path': '~/dotfiles'}]},
        gh=github_stub(graphql_node('dotfiles', 1, 'a-branch'), {}),
    )
    assert result.returncode == 0, result.stderr
    assert [pr['number'] for pr in json.loads(result.stdout)] == [1]


def test_a_repo_the_registry_does_not_name_is_left_out(run) -> None:
    """Searching by author is what makes this one call for any registry size; the
    filter afterwards is the only thing keeping it honest about scope."""
    result = run(
        {'provider': 'github', 'repos': [{'name': 'dotfiles', 'path': '~/dotfiles'}]},
        gh=github_stub(
            graphql_node('dotfiles', 1, 'mine'),
            graphql_node('someone-elses', 4, 'theirs'),
        ),
    )
    assert result.returncode == 0, result.stderr
    assert [pr['repo'] for pr in json.loads(result.stdout)] == ['dotfiles']


def test_a_bitbucket_pr_reports_its_branch_under_the_same_key(run, tmp_path: Path) -> None:
    """Bitbucket Server spells it `fromRef.displayId` and GitHub `headRefName`.
    A consumer choosing a column must not have to know which forge answered."""
    checkout = tmp_path / 'service'
    checkout.mkdir()
    payload = json.dumps(
        [
            {
                'id': 42,
                'title': 'a change in service',
                'createdDate': 1754042400000,
                'fromRef': {'displayId': 'feature/PROJ-1'},
                'toRef': {'displayId': 'develop'},
                'links': {'self': [{'href': 'https://bitbucket.example/pr/42'}]},
            }
        ]
    )
    result = run(
        {'provider': 'bitbucket', 'repos': [{'name': 'service', 'path': str(checkout)}]},
        bbkt=f"#!/bin/sh\ncat <<'JSON'\n{payload}\nJSON\n",
    )
    assert result.returncode == 0, result.stderr
    (pr,) = json.loads(result.stdout)
    assert pr['branch'] == 'feature/PROJ-1'
    assert pr['base'] == 'develop'


def test_an_unauthenticated_gh_skips_github_rather_than_failing_the_run(run) -> None:
    """A registry can span forges, so one provider being unreachable must not take
    the whole listing with it — and the message has to name the fix."""
    result = run(
        {'provider': 'github', 'repos': [{'name': 'dotfiles', 'path': '~/dotfiles'}]},
        gh='#!/bin/sh\necho "gh: You are not logged into any GitHub hosts" >&2\nexit 1\n',
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []
    assert 'gh auth status' in result.stderr
