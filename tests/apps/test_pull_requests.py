"""`pull-requests` is the one query behind `prs` and doit's PRS lane.

The seam is the provider CLI, shadowed on PATH, because nothing else here is
worth asserting: the mapping is short and the interesting failures are all about
a *response shape*. Three of them are real and none would show up as an error.

GitHub's is asked for over GraphQL rather than `gh search prs`, whose field set
has no `headRefName` — so the response arrives under `.data.search.nodes` and a
`type: ISSUE` search can hand back a node the PullRequest fragment did not match.
Bitbucket's arrives from a Server API that spells a branch `fromRef.displayId`,
which shares no key with GitHub's. Both are mapped to one provider-neutral field
here so no consumer sees either spelling, and that mapping is what these pin.

Run with: pytest tests/apps/test_pull_requests.py
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
PULL_REQUESTS = REPO / 'apps' / 'common' / 'pull-requests'

# The stub gh and bbkt behind `with-demo`, first on PATH. Both forges answer from
# here, so one listing covers both spellings of a row.
DEMO = Path(__file__).resolve().parent / 'fixtures' / 'demo'

# Read at import, while HOME is still the real one. See the `run` fixture.
UV_CACHE = os.environ.get('UV_CACHE_DIR') or str(Path.home() / '.cache' / 'uv')


def stub(directory: Path, name: str, script: str) -> None:
    """A binary that shadows the real one, first on PATH."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)


def registry(provider: str, *repos: tuple[str, str], owner: str = 'datapointchris') -> dict[str, Any]:
    """A registry with an explicit status and owner on every entry, as a real one has.

    Both are required rather than defaulted, and defaulting either here would test
    a shape the file cannot take — the registry repo rejects an entry without one
    at commit time, and each reader matches it plainly for the same reason.
    """
    return {
        'owner': owner,
        'provider': provider,
        'repos': [{'name': name, 'owner': owner, 'path': path, 'status': 'active'} for name, path in repos],
    }


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
        # Every field the query asks for, present on every node, because GitHub
        # answers a request for a field. Leaving one out here models a response
        # the API does not send, and reading it back leniently would hide a query
        # that had stopped asking.
        'body': f'what {repo} #{number} changes',
        'additions': 12,
        'deletions': 4,
        'changedFiles': 2,
        'reviewDecision': None,
        'reviews': {'totalCount': 0},
        'commits': {'nodes': [{'commit': {'statusCheckRollup': None}}]},
        'repository': {'name': repo, 'nameWithOwner': f'datapointchris/{repo}'},
    }
    return node | overrides


@pytest.fixture
def run(tmp_path: Path):
    """Invoke pull-requests against a synthetic registry and a stubbed provider CLI.

    The real PATH stays behind the stub dir so the shell can still find `uv`,
    which the shebang runs the script under.

    UV_CACHE_DIR is passed through because HOME is a throwaway here. uv hangs its
    cache off HOME, so without this every test resolves dependencies again — and
    on a machine with no network, fails.
    """
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    def _run(repos: dict[str, Any], **stubs: str) -> subprocess.CompletedProcess[str]:
        for name, script in stubs.items():
            stub(bin_dir, name, script)
        path = tmp_path / 'repos.json'
        path.write_text(json.dumps(repos))
        return subprocess.run(
            [str(PULL_REQUESTS), '--registry', str(path)],
            capture_output=True,
            text=True,
            env={
                'HOME': str(tmp_path),
                'PATH': f'{bin_dir}:{os.environ["PATH"]}',
                'UV_CACHE_DIR': UV_CACHE,
            },
        )

    return _run


def github_stub(*nodes: dict[str, Any]) -> str:
    payload = json.dumps({'data': {'search': {'nodes': list(nodes)}}})
    return f"#!/bin/sh\ncat <<'JSON'\n{payload}\nJSON\n"


def test_a_github_pr_carries_the_branch_it_would_be_typed_as(run) -> None:
    result = run(
        registry('github', ('dotfiles', '~/dotfiles')),
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
        registry('github', ('dotfiles', '~/dotfiles')),
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
        registry('github', ('dotfiles', '~/dotfiles')),
        gh=github_stub(graphql_node('dotfiles', 1, 'a-branch'), {}),
    )
    assert result.returncode == 0, result.stderr
    assert [pr['number'] for pr in json.loads(result.stdout)] == [1]


def test_a_reviewed_pr_is_counted_though_the_forge_decided_nothing(run) -> None:
    """A review setting no decision leaves `reviewDecision` null, and reporting
    that alone said `no review` on dotfiles #23 with three reviews on it."""
    result = run(
        registry('github', ('dotfiles', '~/dotfiles')),
        gh=github_stub(graphql_node('dotfiles', 1, 'a-branch', reviews={'totalCount': 3})),
    )
    assert result.returncode == 0, result.stderr
    (pr,) = json.loads(result.stdout)
    assert pr['reviews'] == 3
    assert pr['review'] == ''


def test_a_repo_the_registry_does_not_name_is_left_out(run) -> None:
    """Searching by author is what makes this one call for any registry size; the
    filter afterwards is the only thing keeping it honest about scope."""
    result = run(
        registry('github', ('dotfiles', '~/dotfiles')),
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
        registry('bitbucket', ('service', str(checkout))),
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
        registry('github', ('dotfiles', '~/dotfiles')),
        gh='#!/bin/sh\necho "gh: You are not logged into any GitHub hosts" >&2\nexit 1\n',
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []
    assert 'gh auth status' in result.stderr


def test_a_pr_against_an_upstream_of_the_same_name_is_not_listed(run) -> None:
    """The search covers all of GitHub, so being a contributor to any project that
    shares a name with one of yours was enough to be admitted — `crate-ci/typos`
    against the registry's `typos`. The row was mislabelled, and worse, the same
    basename lookup fed `path`, so `prs` fetched a pull ref from the wrong origin."""
    result = run(
        registry('github', ('typos', '~/code/typos')),
        gh=github_stub(
            graphql_node('typos', 4, 'mine'),
            graphql_node(
                'typos',
                1188,
                'theirs',
                repository={'name': 'typos', 'nameWithOwner': 'crate-ci/typos'},
            ),
        ),
    )
    assert result.returncode == 0, result.stderr
    listed = json.loads(result.stdout)
    assert [pr['slug'] for pr in listed] == ['datapointchris/typos']
    assert [pr['number'] for pr in listed] == [4]


def test_an_entrys_own_owner_decides_it_rather_than_the_file_level_one(run) -> None:
    """`owner` is read per entry, never inherited from the file-level key of that
    name. A reader that defaults a field it filters on is wrong even when it
    defaults correctly, and this is the assertion that keeps the field earning its
    place — without it every entry holds the same value and the field reads as
    redundant."""
    repos = {
        'owner': 'datapointchris',
        'provider': 'github',
        'repos': [{'name': 'thing', 'owner': 'someone-else', 'path': '~/code/thing', 'status': 'active'}],
    }
    result = run(
        repos,
        gh=github_stub(
            graphql_node(
                'thing',
                9,
                'theirs',
                repository={'name': 'thing', 'nameWithOwner': 'someone-else/thing'},
            ),
            graphql_node('thing', 10, 'mine'),
        ),
    )
    assert result.returncode == 0, result.stderr
    listed = json.loads(result.stdout)
    assert [pr['slug'] for pr in listed] == ['someone-else/thing']


def help_example(screen: str) -> dict[str, Any]:
    """The document out of the OUTPUT block, parsed as the JSON it claims to be.

    Parsing rather than pattern-matching is half the assertion — a screen showing
    a field reference in something that is not JSON is showing a shape no
    consumer will meet.
    """
    start = screen.index('\n  [\n')
    end = screen.index('\n  ]\n', start) + len('\n  ]')
    (row,) = json.loads(screen[start:end])
    return row


def test_the_help_screens_example_carries_every_field_a_row_does() -> None:
    """The example object in `--help` is the field reference, and measuring its
    keys against a real row is the only thing that keeps it one. A field added to
    the mapping and not to the example is simply unsaid — no consumer breaks, no
    test fails, and the screen reads as complete while it is not."""
    shown = subprocess.run(
        [str(PULL_REQUESTS), '--help'],
        capture_output=True,
        text=True,
        env={**os.environ, 'NO_COLOR': '1', 'UV_CACHE_DIR': UV_CACHE},
    )
    assert shown.returncode == 0, shown.stderr

    listed = subprocess.run(
        [str(PULL_REQUESTS)],
        capture_output=True,
        text=True,
        env={**os.environ, 'PATH': f'{DEMO}:{os.environ["PATH"]}', 'UV_CACHE_DIR': UV_CACHE},
    )
    assert listed.returncode == 0, listed.stderr
    rows = json.loads(listed.stdout)

    # Order too, not just membership. The example reads as the emitted document,
    # so a field arriving in a different place makes it a drawing of one.
    assert [list(help_example(shown.stdout))] * len(rows) == [list(row) for row in rows]


# What doit's dashboard reads out of a row, in `prs_adapter`. Named here because
# that adapter is in another repo and reaches every field through `.get()` with a
# default, so a rename empties the PRS lane instead of failing it — every PR
# renders as `0d` with a blank repo and no title, and the dashboard still draws.
#
# The test above cannot catch that. It measures the emitted row against the help
# screen's example, and a rename made in both places agrees with itself.
DOIT_DASHBOARD_READS = ('repo', 'title', 'age_days', 'draft')


def test_the_fields_doits_prs_lane_reads_are_emitted_under_those_names(run) -> None:
    """Renaming one of these is a change to another repo's dashboard, so it fails
    here rather than going quiet there."""
    result = run(
        registry('github', ('dotfiles', '~/dotfiles')),
        gh=github_stub(graphql_node('dotfiles', 1, 'split-plan-check-verbs')),
    )
    assert result.returncode == 0, result.stderr
    (pr,) = json.loads(result.stdout)

    assert set(DOIT_DASHBOARD_READS) <= set(pr)
    assert isinstance(pr['age_days'], int)
    assert isinstance(pr['draft'], bool)


def test_it_runs_with_the_network_down() -> None:
    """The pytermstyle dependency is pinned to a commit rather than to a tag, and
    a tag would take this offline without failing any other test here.

    uv re-resolves a mutable ref against the remote on every single run. That is
    a socket per invocation — 1.3s each, and an outright failure on a plane or
    behind the work firewall. A commit is already resolved, so uv reads its cache
    and never opens one. Nothing about the screen looks different either way,
    which is what makes this worth asserting rather than noticing.

    Warmed first, because an empty cache is a fair reason to need the network and
    is not the failure being guarded against.
    """
    warm = subprocess.run(
        [str(PULL_REQUESTS), '--help'],
        capture_output=True,
        text=True,
        env={**os.environ, 'NO_COLOR': '1', 'UV_CACHE_DIR': UV_CACHE},
    )
    assert warm.returncode == 0, warm.stderr

    offline = subprocess.run(
        [str(PULL_REQUESTS), '--help'],
        capture_output=True,
        text=True,
        env={**os.environ, 'NO_COLOR': '1', 'UV_CACHE_DIR': UV_CACHE, 'UV_OFFLINE': '1'},
    )
    assert offline.returncode == 0, offline.stderr
    assert offline.stdout == warm.stdout
